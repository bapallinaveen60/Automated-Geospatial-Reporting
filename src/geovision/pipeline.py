"""Screening analysis stages for one AOI request (no cartography or document steps).

Each ``stage_*`` function backs one Dagster asset (see orchestration/definitions.py);
``run_screening`` chains them in-process for scripts and tests.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pystac
import rioxarray  # noqa: F401  (registers the .rio accessor)
import xarray as xr

from geovision.analysis.change import change_summary
from geovision.analysis.indices import index_stats, mndwi, ndvi
from geovision.analysis.masking import median_composite, to_reflectance
from geovision.analysis.overlay import class_breakdown, mask_to_geometry, pixel_area_m2, proximity
from geovision.analysis.rules import evaluate
from geovision.contracts import (
    AOIRequest,
    ChangeSummary,
    ClassShare,
    DateRange,
    IndexStats,
    InputRef,
    LineageRecord,
    MetricsPayload,
    ProximityResult,
    SiteSummary,
)
from geovision.core.logging import get_logger
from geovision.core.provenance import git_sha, package_versions, utcnow
from geovision.ingest.aoi import ValidatedAOI, read_aoi, validate_aoi
from geovision.ingest.raster_sources import ESA_WORLDCOVER, load_thematic
from geovision.ingest.stac import item_refs, load_s2, processing_baselines, search_s2
from geovision.ingest.vector_sources import build_source
from geovision.modules import ModuleConfig, load_module

log = get_logger(__name__)

REFLECTANCE_BANDS = ("red", "green", "nir", "swir16")
# Imagery is loaded over the site plus this margin so map plates have context around it.
DISPLAY_MARGIN_M = 500


@dataclass
class StageResult:
    """Side outputs every stage produces alongside its value."""

    lineage: list[LineageRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    files: dict[str, Path] = field(default_factory=dict)

    def merge(self, other: "StageResult") -> "StageResult":
        self.lineage += other.lineage
        self.warnings += other.warnings
        self.files.update(other.files)
        return self


@dataclass
class ImageryMetrics:
    indices: dict[str, IndexStats] = field(default_factory=dict)
    change: list[ChangeSummary] = field(default_factory=list)


@dataclass
class ScreeningResult:
    request: AOIRequest
    module: ModuleConfig
    aoi: ValidatedAOI
    metrics: MetricsPayload
    lineage: list[LineageRecord] = field(default_factory=list)
    rasters: dict[str, Path] = field(default_factory=dict)
    layers: dict[str, Path] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _lineage(
    asset_key: str,
    project_id: str,
    inputs: list[InputRef],
    parameters: dict[str, Any],
    started: Any,
) -> LineageRecord:
    return LineageRecord(
        asset_key=asset_key,
        project_id=project_id,
        inputs=inputs,
        parameters=parameters,
        code_version=git_sha(),
        package_versions=package_versions(),
        started_at=started,
        finished_at=utcnow(),
    )


def _least_cloudy(items: pystac.ItemCollection, n: int) -> pystac.ItemCollection:
    ranked = sorted(items, key=lambda it: it.properties.get("eo:cloud_cover", 100))
    return pystac.ItemCollection(ranked[:n])


def _s2_indices(
    aoi: ValidatedAOI,
    period: DateRange,
    max_cloud: float,
    max_scenes: int,
    resolution: float,
) -> tuple[dict[str, xr.DataArray], list[InputRef]]:
    """Cloud-masked median composite for a period, returned as unmasked NDVI/MNDWI grids."""
    bbox = aoi.buffered_bbox(DISPLAY_MARGIN_M)
    found = search_s2(bbox, period.to_stac(), max_cloud=max_cloud)
    if not found:
        raise LookupError(f"No Sentinel-2 scenes below {max_cloud}% cloud for {period.to_stac()}")
    items = _least_cloudy(found, max_scenes)
    log.info("Sentinel-2 %s: using %d of %d scenes", period.to_stac(), len(items), len(found))
    ds = load_s2(items, bbox, aoi.utm_crs.to_string(), resolution=resolution)
    refl = to_reflectance(ds, REFLECTANCE_BANDS, processing_baselines(items))
    comp = median_composite(refl, REFLECTANCE_BANDS).compute()
    return {"ndvi": ndvi(comp), "mndwi": mndwi(comp)}, item_refs(items)


def stage_aoi(
    request: AOIRequest, module: ModuleConfig, work_dir: Path
) -> tuple[ValidatedAOI, StageResult]:
    t0 = utcnow()
    aoi = validate_aoi(
        read_aoi(request.geometry),
        min_area_ha=module.aoi.get("min_area_ha", 0.01),
        max_area_ha=module.aoi.get("max_area_ha", 50_000),
    )
    crs = aoi.utm_crs.to_string()
    aoi_path = work_dir / "layers" / "aoi.gpkg"
    aoi_path.parent.mkdir(parents=True, exist_ok=True)
    aoi.to_gdf(utm=True).to_file(aoi_path, driver="GPKG")
    rec = _lineage(
        "aoi_validated",
        request.project_id,
        [InputRef(kind="file", id=f"{request.project_id}/request.json")],
        {"utm_crs": crs, "area_ha": round(aoi.area_ha, 4)},
        t0,
    )
    return aoi, StageResult([rec], list(aoi.warnings), {"aoi": aoi_path})


def stage_imagery(
    request: AOIRequest,
    module: ModuleConfig,
    aoi: ValidatedAOI,
    work_dir: Path,
    max_scenes: int = 12,
) -> tuple[ImageryMetrics, StageResult]:
    """Sentinel-2 composites for both periods: current-period index stats and change."""
    out = StageResult()
    crs = aoi.utm_crs.to_string()
    max_cloud = float(module.imagery.get("max_cloud", 20))
    res = float(module.imagery.get("resolution_m", 10))
    (work_dir / "rasters").mkdir(parents=True, exist_ok=True)
    grids: dict[str, dict[str, xr.DataArray]] = {}
    for label, period in (
        ("baseline", request.baseline_period),
        ("current", request.current_period),
    ):
        t0 = utcnow()
        try:
            grids[label], refs = _s2_indices(aoi, period, max_cloud, max_scenes, res)
        except LookupError as e:
            out.warnings.append(str(e))
            continue
        out.lineage.append(
            _lineage(
                f"s2_composite_{label}",
                request.project_id,
                refs,
                {
                    "period": period.to_stac(),
                    "max_cloud": max_cloud,
                    "max_scenes": max_scenes,
                    "resolution_m": res,
                    "scl_masked": [0, 1, 3, 8, 9, 10],
                    "composite": "median",
                },
                t0,
            )
        )
        path = work_dir / "rasters" / f"ndvi_{label}.tif"
        grids[label]["ndvi"].astype("float32").rio.write_crs(crs).rio.to_raster(path)
        out.files[f"ndvi_{label}"] = path

    result = ImageryMetrics()
    masked = {
        label: {k: mask_to_geometry(v, aoi.geometry_utm, crs) for k, v in g.items()}
        for label, g in grids.items()
    }
    if "current" in masked:
        grid = next(iter(grids["current"].values()))
        inside = np.isfinite(mask_to_geometry(xr.ones_like(grid), aoi.geometry_utm, crs).values)
        result.indices = {
            k: index_stats(v.values, within=inside) for k, v in masked["current"].items()
        }
    if {"baseline", "current"} <= set(masked):
        for name in ("ndvi", "mndwi"):
            thr = module.indices.get(name, {}).get("change_threshold", 0.15)
            result.change.append(
                change_summary(
                    masked["baseline"][name].values,
                    masked["current"][name].values,
                    name,
                    thr,
                    res * res,
                )
            )
    return result, out


def stage_landcover(
    request: AOIRequest, module: ModuleConfig, aoi: ValidatedAOI
) -> tuple[list[ClassShare], StageResult]:
    t0 = utcnow()
    crs = aoi.utm_crs.to_string()
    try:
        wc, refs = load_thematic(ESA_WORLDCOVER, aoi.buffered_bbox(DISPLAY_MARGIN_M), crs)
        wc_masked = mask_to_geometry(wc, aoi.geometry_utm, crs).compute()
        lulc = class_breakdown(wc_masked.values, module.lulc_labels(), pixel_area_m2(wc))
    except Exception as e:  # noqa: BLE001 - a missing optional layer must not stop the report
        return [], StageResult(warnings=[f"Land cover unavailable: {e}"])
    rec = _lineage("lulc_worldcover", request.project_id, refs, {"resolution_m": 10}, t0)
    return lulc, StageResult([rec])


def stage_proximity(
    request: AOIRequest, module: ModuleConfig, aoi: ValidatedAOI, work_dir: Path
) -> tuple[list[ProximityResult], StageResult]:
    t0 = utcnow()
    out = StageResult()
    prox: list[ProximityResult] = []
    refs = []
    (work_dir / "layers").mkdir(parents=True, exist_ok=True)
    for key, spec in module.layers.items():
        source = build_source(key, spec.model_dump())
        try:
            feats = source.fetch(aoi.buffered_bbox(spec.search_radius_m))
        except Exception as e:  # noqa: BLE001
            out.warnings.append(f"Layer '{key}' unavailable ({e}); manual check required")
            continue
        refs.append(source.ref())
        prox.append(proximity(aoi.geometry_utm, feats, aoi.utm_crs, key, spec.search_radius_m))
        if not feats.empty:
            path = work_dir / "layers" / f"{key}.gpkg"
            feats.to_crs(aoi.utm_crs).to_file(path, driver="GPKG")
            out.files[key] = path
        log.info("%s: %d features within %.0f m", key, len(feats), spec.search_radius_m)
    out.lineage.append(
        _lineage(
            "proximity",
            request.project_id,
            refs,
            {k: v.search_radius_m for k, v in module.layers.items()},
            t0,
        )
    )
    return prox, out


def assemble_metrics(
    request: AOIRequest,
    module: ModuleConfig,
    aoi: ValidatedAOI,
    imagery: ImageryMetrics,
    lulc: list[ClassShare],
    prox: list[ProximityResult],
) -> MetricsPayload:
    c = aoi.geometry.centroid
    metrics = MetricsPayload(
        project_id=request.project_id,
        site=SiteSummary(
            area_ha=aoi.area_ha,
            perimeter_m=aoi.perimeter_m,
            centroid_lon=c.x,
            centroid_lat=c.y,
            analysis_crs=aoi.utm_crs.to_string(),
        ),
        lulc=lulc,
        indices=imagery.indices,
        change=imagery.change,
        proximity=prox,
    )
    metrics.flags = evaluate(module.rules, metrics.flat())
    return metrics


def run_screening(
    request: AOIRequest,
    work_dir: Path,
    max_scenes: int = 12,
) -> ScreeningResult:
    module = load_module(request.module)
    aoi, side = stage_aoi(request, module, work_dir)
    imagery, s = stage_imagery(request, module, aoi, work_dir, max_scenes)
    side.merge(s)
    lulc, s = stage_landcover(request, module, aoi)
    side.merge(s)
    prox, s = stage_proximity(request, module, aoi, work_dir)
    side.merge(s)
    metrics = assemble_metrics(request, module, aoi, imagery, lulc, prox)
    return ScreeningResult(
        request=request,
        module=module,
        aoi=aoi,
        metrics=metrics,
        lineage=side.lineage,
        rasters={k: v for k, v in side.files.items() if k.startswith("ndvi_")},
        layers={k: v for k, v in side.files.items() if not k.startswith("ndvi_")},
        warnings=side.warnings,
    )
