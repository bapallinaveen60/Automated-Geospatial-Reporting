"""Dagster definitions (Phase 5 scaffold).

One dynamic partition per project. A sensor watches ``<data_root>/incoming/*.json`` for
``AOIRequest`` files. The asset graph mirrors IMPLEMENTATION_PLAN.md §3. Carto and report
assets are added in Phases 3–4.

Run locally:  uv run --extra orchestration dagster dev
"""

from pathlib import Path

import dagster as dg

from geovision.analysis.overlay import proximity
from geovision.analysis.rules import evaluate
from geovision.contracts import AOIRequest, MetricsPayload, ProximityResult, SiteSummary
from geovision.core.config import get_settings
from geovision.core.provenance import git_sha
from geovision.core.storage import ProjectStorage
from geovision.ingest.aoi import ValidatedAOI, read_aoi, validate_aoi
from geovision.ingest.vector_sources import build_source
from geovision.modules import load_module

projects = dg.DynamicPartitionsDefinition(name="projects")


def _incoming_dir() -> Path:
    return Path(get_settings().data_root) / "incoming"


@dg.asset(partitions_def=projects)
def aoi_request(context: dg.AssetExecutionContext) -> AOIRequest:
    pid = context.partition_key
    path = _incoming_dir() / f"{pid}.json"
    return AOIRequest.model_validate_json(path.read_text(encoding="utf-8"))


@dg.asset(partitions_def=projects)
def aoi_validated(context: dg.AssetExecutionContext, aoi_request: AOIRequest) -> ValidatedAOI:
    limits = load_module(aoi_request.module).aoi
    aoi = validate_aoi(
        read_aoi(aoi_request.geometry),
        min_area_ha=limits.get("min_area_ha", 0.01),
        max_area_ha=limits.get("max_area_ha", 50_000),
    )
    for w in aoi.warnings:
        context.log.warning(w)
    context.add_output_metadata(
        {"area_ha": aoi.area_ha, "utm_crs": aoi.utm_crs.to_string(), "code_version": git_sha()}
    )
    return aoi


@dg.asset(partitions_def=projects)
def proximity_results(
    context: dg.AssetExecutionContext, aoi_request: AOIRequest, aoi_validated: ValidatedAOI
) -> list[dict]:
    module = load_module(aoi_request.module)
    results = []
    for key, spec in module.layers.items():
        source = build_source(key, spec.model_dump())
        bbox = aoi_validated.buffered_bbox(spec.search_radius_m)
        features = source.fetch(bbox)
        res = proximity(
            aoi_validated.geometry_utm, features, aoi_validated.utm_crs, key, spec.search_radius_m
        )
        context.log.info(f"{key}: {len(features)} features, nearest={res.distance_m}")
        results.append(res.model_dump())
    return results


@dg.asset(partitions_def=projects)
def metrics(
    context: dg.AssetExecutionContext,
    aoi_request: AOIRequest,
    aoi_validated: ValidatedAOI,
    proximity_results: list[dict],
) -> MetricsPayload:
    # TODO(Phase 2): add LULC, indices and change assets as upstream inputs.
    c = aoi_validated.geometry.centroid
    payload = MetricsPayload(
        project_id=aoi_request.project_id,
        site=SiteSummary(
            area_ha=aoi_validated.area_ha,
            perimeter_m=aoi_validated.perimeter_m,
            centroid_lon=c.x,
            centroid_lat=c.y,
            analysis_crs=aoi_validated.utm_crs.to_string(),
        ),
        proximity=[ProximityResult.model_validate(p) for p in proximity_results],
    )
    payload.flags = evaluate(load_module(aoi_request.module).rules, payload.flat())
    ProjectStorage(aoi_request.project_id).write_json(payload, "metrics", "metrics.json")
    context.add_output_metadata({"flags": len(payload.flags)})
    return payload


screening_job = dg.define_asset_job("site_screening", selection="*metrics", partitions_def=projects)


@dg.sensor(job=screening_job, minimum_interval_seconds=60)
def incoming_aoi_sensor(context: dg.SensorEvaluationContext) -> dg.SensorResult:
    incoming = _incoming_dir()
    found = sorted(p.stem for p in incoming.glob("*.json")) if incoming.exists() else []
    new = [pid for pid in found if not context.instance.has_dynamic_partition("projects", pid)]
    return dg.SensorResult(
        run_requests=[dg.RunRequest(partition_key=pid, run_key=pid) for pid in new],
        dynamic_partitions_requests=[projects.build_add_request(new)] if new else [],
    )


defs = dg.Definitions(
    assets=[aoi_request, aoi_validated, proximity_results, metrics],
    jobs=[screening_job],
    sensors=[incoming_aoi_sensor],
)
