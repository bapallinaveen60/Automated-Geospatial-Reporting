"""Dagster definitions: the site-screening asset graph, one dynamic partition per project.

Drop an ``AOIRequest`` JSON into ``<data_root>/incoming/<project_id>.json``; the sensor
registers the partition and materialises the graph through to the draft PDF:

    aoi_request → aoi_validated ─┬─ site_location ─────┐
                                 ├─ s2_imagery ────────┤
                                 ├─ land_cover ────────┼─ screening_metrics
                                 └─ proximity_results ─┘        ↓
                                                   map_plates → report_draft

Assets return ``(value, StageResult)`` so lineage, warnings and file paths travel with the
data. Run locally (DAGSTER_HOME keeps run history between restarts):

    uv run --extra orchestration dagster dev
"""

import shutil
from pathlib import Path
from typing import Any

import dagster as dg

from geovision import __version__
from geovision.carto.plates import render_screening_plates
from geovision.contracts import AOIRequest, ClassShare, MetricsPayload, ProximityResult
from geovision.core.config import get_settings
from geovision.core.storage import ProjectStorage
from geovision.ingest.admin import AdminLocation
from geovision.ingest.aoi import ValidatedAOI
from geovision.modules import load_module
from geovision.pipeline import (
    ImageryMetrics,
    StageResult,
    assemble_metrics,
    stage_aoi,
    stage_imagery,
    stage_landcover,
    stage_location,
    stage_proximity,
)
from geovision.reporting.build_payload import build_payload
from geovision.reporting.charts import render_charts
from geovision.reporting.compile import compile_report

projects = dg.DynamicPartitionsDefinition(name="projects")
# External APIs (STAC, Planetary Computer, Overpass) fail transiently; retry with backoff.
NETWORK_RETRY = dg.RetryPolicy(max_retries=2, delay=30, backoff=dg.Backoff.EXPONENTIAL)
ASSET_ARGS: dict[str, Any] = {
    "partitions_def": projects,
    "code_version": __version__,
    "group_name": "site_screening",
}


def _root() -> Path:
    return Path(get_settings().data_root)


def _incoming_dir() -> Path:
    return _root() / "incoming"


def _work_dir(project_id: str) -> Path:
    return _root() / project_id / "analysis"


def _record(context: dg.AssetExecutionContext, side: StageResult, **extra: Any) -> None:
    """Surface lineage, warnings and output files as Dagster metadata."""
    for w in side.warnings:
        context.log.warning(w)
    meta: dict[str, Any] = {
        "code_version": side.lineage[0].code_version if side.lineage else "n/a",
        "inputs": dg.MetadataValue.json(
            [
                i.model_dump(mode="json", include={"kind", "id", "collection"})
                for rec in side.lineage
                for i in rec.inputs
            ]
        ),
        "parameters": dg.MetadataValue.json(
            {rec.asset_key: rec.parameters for rec in side.lineage}
        ),
        "warnings": len(side.warnings),
        **{f"file:{k}": dg.MetadataValue.path(str(v)) for k, v in side.files.items()},
        **extra,
    }
    context.add_output_metadata(meta)


@dg.asset(**ASSET_ARGS)
def aoi_request(context: dg.AssetExecutionContext) -> AOIRequest:
    """The submitted request, archived next to the project's outputs."""
    pid = context.partition_key
    src = _incoming_dir() / f"{pid}.json"
    request = AOIRequest.model_validate_json(src.read_text(encoding="utf-8"))
    if request.project_id != pid:
        raise dg.Failure(f"File name {src.name} does not match project_id {request.project_id!r}")
    dest = _root() / pid / "request.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    context.add_output_metadata({"site": request.site_name, "module": request.module})
    return request


@dg.asset(**ASSET_ARGS)
def aoi_validated(
    context: dg.AssetExecutionContext, aoi_request: AOIRequest
) -> tuple[ValidatedAOI, StageResult]:
    module = load_module(aoi_request.module)
    aoi, side = stage_aoi(aoi_request, module, _work_dir(aoi_request.project_id))
    _record(context, side, area_ha=round(aoi.area_ha, 4), utm_crs=aoi.utm_crs.to_string())
    return aoi, side


@dg.asset(**ASSET_ARGS, retry_policy=NETWORK_RETRY)
def s2_imagery(
    context: dg.AssetExecutionContext,
    aoi_request: AOIRequest,
    aoi_validated: tuple[ValidatedAOI, StageResult],
) -> tuple[ImageryMetrics, StageResult]:
    """Sentinel-2 composites for both periods: NDVI/MNDWI stats and change."""
    module = load_module(aoi_request.module)
    result, side = stage_imagery(
        aoi_request, module, aoi_validated[0], _work_dir(aoi_request.project_id)
    )
    ndvi = result.indices.get("ndvi")
    _record(
        context,
        side,
        scenes=sum(len(r.inputs) for r in side.lineage),
        ndvi_mean=ndvi.mean if ndvi and ndvi.mean is not None else float("nan"),
    )
    return result, side


@dg.asset(**ASSET_ARGS, retry_policy=NETWORK_RETRY)
def site_location(
    context: dg.AssetExecutionContext,
    aoi_request: AOIRequest,
    aoi_validated: tuple[ValidatedAOI, StageResult],
) -> tuple[AdminLocation | None, StageResult]:
    """State / district / locality of the site (OSM Nominatim), for the report text."""
    loc, side = stage_location(aoi_request, aoi_validated[0])
    _record(
        context,
        side,
        state=str(loc.state if loc else None),
        district=str(loc.district if loc else None),
    )
    return loc, side


@dg.asset(**ASSET_ARGS, retry_policy=NETWORK_RETRY)
def land_cover(
    context: dg.AssetExecutionContext,
    aoi_request: AOIRequest,
    aoi_validated: tuple[ValidatedAOI, StageResult],
) -> tuple[list[ClassShare], StageResult]:
    """ESA WorldCover class breakdown inside the site."""
    module = load_module(aoi_request.module)
    lulc, side = stage_landcover(
        aoi_request, module, aoi_validated[0], _work_dir(aoi_request.project_id)
    )
    _record(
        context,
        side,
        classes=dg.MetadataValue.json({c.label: round(c.percent, 1) for c in lulc}),
    )
    return lulc, side


@dg.asset(**ASSET_ARGS, retry_policy=NETWORK_RETRY)
def proximity_results(
    context: dg.AssetExecutionContext,
    aoi_request: AOIRequest,
    aoi_validated: tuple[ValidatedAOI, StageResult],
) -> tuple[list[ProximityResult], StageResult]:
    """Distance/overlap to protected areas, wetlands, forest and coast."""
    module = load_module(aoi_request.module)
    prox, side = stage_proximity(
        aoi_request, module, aoi_validated[0], _work_dir(aoi_request.project_id)
    )
    _record(
        context,
        side,
        nearest_m=dg.MetadataValue.json({p.layer: p.distance_m for p in prox}),
    )
    return prox, side


@dg.asset(**ASSET_ARGS)
def screening_metrics(
    context: dg.AssetExecutionContext,
    aoi_request: AOIRequest,
    aoi_validated: tuple[ValidatedAOI, StageResult],
    site_location: tuple[AdminLocation | None, StageResult],
    s2_imagery: tuple[ImageryMetrics, StageResult],
    land_cover: tuple[list[ClassShare], StageResult],
    proximity_results: tuple[list[ProximityResult], StageResult],
) -> MetricsPayload:
    """All metrics plus rule-based exceedance flags; written to metrics.json and lineage.json."""
    module = load_module(aoi_request.module)
    metrics = assemble_metrics(
        aoi_request,
        module,
        aoi_validated[0],
        s2_imagery[0],
        land_cover[0],
        proximity_results[0],
        site_location[0],
    )
    side = StageResult()
    for _, s in (aoi_validated, site_location, s2_imagery, land_cover, proximity_results):
        side.merge(s)
    store = ProjectStorage(aoi_request.project_id)
    metrics_path = store.write_json(metrics, "analysis", "metrics.json")
    store.write_json(
        {
            "records": [r.model_dump(mode="json") for r in side.lineage],
            "warnings": side.warnings,
        },
        "analysis",
        "lineage.json",
    )
    context.add_output_metadata(
        {
            "flags": dg.MetadataValue.json(
                [{"severity": f.severity, "message": f.message} for f in metrics.flags]
            ),
            "critical": sum(f.severity == "critical" for f in metrics.flags),
            "metrics_json": dg.MetadataValue.path(metrics_path),
        }
    )
    return metrics


@dg.asset(**ASSET_ARGS, deps=[screening_metrics])
def map_plates(
    context: dg.AssetExecutionContext,
    aoi_request: AOIRequest,
    aoi_validated: tuple[ValidatedAOI, StageResult],
    s2_imagery: tuple[ImageryMetrics, StageResult],
    land_cover: tuple[list[ClassShare], StageResult],
    proximity_results: tuple[list[ProximityResult], StageResult],
) -> list[dict[str, str]]:
    """Headless PyQGIS plates (local QGIS or the Docker renderer)."""
    aoi, aoi_side = aoi_validated
    files = {**aoi_side.files, **proximity_results[1].files}
    rasters = {**s2_imagery[1].files, **land_cover[1].files}
    plates = render_screening_plates(
        aoi,
        files,
        rasters,
        aoi_request.project_id,
        _work_dir(aoi_request.project_id),
        periods=(aoi_request.baseline_period.to_stac(), aoi_request.current_period.to_stac()),
    )
    context.add_output_metadata({p["title"]: dg.MetadataValue.path(p["path"]) for p in plates})
    return plates


@dg.asset(**ASSET_ARGS)
def report_draft(
    context: dg.AssetExecutionContext,
    aoi_request: AOIRequest,
    aoi_validated: tuple[ValidatedAOI, StageResult],
    site_location: tuple[AdminLocation | None, StageResult],
    s2_imagery: tuple[ImageryMetrics, StageResult],
    land_cover: tuple[list[ClassShare], StageResult],
    proximity_results: tuple[list[ProximityResult], StageResult],
    screening_metrics: MetricsPayload,
    map_plates: list[dict[str, str]],
) -> str:
    """Draft PDF/A report awaiting human review (watermarked DRAFT)."""
    side = StageResult()
    for _, s in (aoi_validated, site_location, s2_imagery, land_cover, proximity_results):
        side.merge(s)
    pid = aoi_request.project_id
    payload = build_payload(
        aoi_request,
        screening_metrics,
        load_module(aoi_request.module).model_dump(),
        lineage=side.lineage,
        plates=map_plates,
        charts=render_charts(screening_metrics, _work_dir(pid) / "charts"),
        warnings=side.warnings,
    )
    pdf = compile_report(payload, _root() / pid / "report" / f"{pid}_draft.pdf")
    context.add_output_metadata(
        {"pdf": dg.MetadataValue.path(str(pdf)), "status": "awaiting review"}
    )
    return str(pdf)


screening_job = dg.define_asset_job(
    "site_screening", selection=dg.AssetSelection.groups("site_screening")
)


@dg.sensor(
    job=screening_job,
    minimum_interval_seconds=30,
    default_status=dg.DefaultSensorStatus.RUNNING,
)
def incoming_aoi_sensor(context: dg.SensorEvaluationContext) -> dg.SensorResult:
    """New or edited request files trigger a run (run_key includes the file's mtime)."""
    incoming = _incoming_dir()
    files = sorted(incoming.glob("*.json")) if incoming.exists() else []
    new = [p.stem for p in files if not context.instance.has_dynamic_partition("projects", p.stem)]
    return dg.SensorResult(
        run_requests=[
            dg.RunRequest(partition_key=p.stem, run_key=f"{p.stem}:{p.stat().st_mtime_ns}")
            for p in files
        ],
        dynamic_partitions_requests=[projects.build_add_request(new)] if new else [],
    )


defs = dg.Definitions(
    assets=[
        aoi_request,
        aoi_validated,
        site_location,
        s2_imagery,
        land_cover,
        proximity_results,
        screening_metrics,
        map_plates,
        report_draft,
    ],
    jobs=[screening_job],
    sensors=[incoming_aoi_sensor],
)
