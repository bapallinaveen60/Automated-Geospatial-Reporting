"""End-to-end screening analysis for one AOI request (no cartography or document steps).

The Dagster assets will wrap these stages individually; this module runs them in-process so
the vertical slice can be exercised from a script or test.
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
    DateRange,
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


def run_screening(
    request: AOIRequest,
    work_dir: Path,
    max_scenes: int = 12,
) -> ScreeningResult:
    module = load_module(request.module)
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "rasters").mkdir(exist_ok=True)
    (work_dir / "layers").mkdir(exist_ok=True)
    pid = request.project_id
    warnings: list[str] = []
    lineage: list[LineageRecord] = []

    # --- AOI -----------------------------------------------------------------------------
    t0 = utcnow()
    aoi = validate_aoi(
        read_aoi(request.geometry),
        min_area_ha=module.aoi.get("min_area_ha", 0.01),
        max_area_ha=module.aoi.get("max_area_ha", 50_000),
    )
    warnings.extend(aoi.warnings)
    crs = aoi.utm_crs.to_string()
    aoi_path = work_dir / "layers" / "aoi.gpkg"
    aoi.to_gdf(utm=True).to_file(aoi_path, driver="GPKG")
    lineage.append(
        _lineage(
            "aoi_validated",
            pid,
            [InputRef(kind="file", id=f"{pid}/request.json")],
            {"utm_crs": crs, "area_ha": round(aoi.area_ha, 4)},
            t0,
        )
    )

    # --- Sentinel-2 indices and change -----------------------------------------------------
    img = module.imagery
    max_cloud = float(img.get("max_cloud", 20))
    res = float(img.get("resolution_m", 10))
    indices: dict[str, Any] = {}
    change = []
    rasters: dict[str, Path] = {}
    grids: dict[str, dict[str, xr.DataArray]] = {}
    for label, period in (
        ("baseline", request.baseline_period),
        ("current", request.current_period),
    ):
        t0 = utcnow()
        try:
            grids[label], refs = _s2_indices(aoi, period, max_cloud, max_scenes, res)
        except LookupError as e:
            warnings.append(str(e))
            continue
        lineage.append(
            _lineage(
                f"s2_composite_{label}",
                pid,
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
        out = work_dir / "rasters" / f"ndvi_{label}.tif"
        grids[label]["ndvi"].astype("float32").rio.write_crs(crs).rio.to_raster(out)
        rasters[f"ndvi_{label}"] = out

    masked = {
        label: {k: mask_to_geometry(v, aoi.geometry_utm, crs) for k, v in g.items()}
        for label, g in grids.items()
    }
    if "current" in masked:
        grid = next(iter(grids["current"].values()))
        inside = np.isfinite(mask_to_geometry(xr.ones_like(grid), aoi.geometry_utm, crs).values)
        indices = {k: index_stats(v.values, within=inside) for k, v in masked["current"].items()}
    if {"baseline", "current"} <= set(masked):
        for name in ("ndvi", "mndwi"):
            thr = module.indices.get(name, {}).get("change_threshold", 0.15)
            change.append(
                change_summary(
                    masked["baseline"][name].values,
                    masked["current"][name].values,
                    name,
                    thr,
                    res * res,
                )
            )

    # --- Land cover ----------------------------------------------------------------------
    lulc = []
    t0 = utcnow()
    try:
        wc, wc_refs = load_thematic(ESA_WORLDCOVER, aoi.buffered_bbox(DISPLAY_MARGIN_M), crs)
        wc_masked = mask_to_geometry(wc, aoi.geometry_utm, crs).compute()
        lulc = class_breakdown(wc_masked.values, module.lulc_labels(), pixel_area_m2(wc))
        lineage.append(_lineage("lulc_worldcover", pid, wc_refs, {"resolution_m": 10}, t0))
    except Exception as e:  # noqa: BLE001 - a missing optional layer must not stop the report
        warnings.append(f"Land cover unavailable: {e}")

    # --- Vector proximity ----------------------------------------------------------------
    prox: list[ProximityResult] = []
    layers: dict[str, Path] = {"aoi": aoi_path}
    t0 = utcnow()
    vec_refs = []
    for key, spec in module.layers.items():
        source = build_source(key, spec.model_dump())
        try:
            feats = source.fetch(aoi.buffered_bbox(spec.search_radius_m))
        except Exception as e:  # noqa: BLE001
            warnings.append(f"Layer '{key}' unavailable ({e}); manual check required")
            continue
        vec_refs.append(source.ref())
        prox.append(proximity(aoi.geometry_utm, feats, aoi.utm_crs, key, spec.search_radius_m))
        if not feats.empty:
            path = work_dir / "layers" / f"{key}.gpkg"
            feats.to_crs(aoi.utm_crs).to_file(path, driver="GPKG")
            layers[key] = path
        log.info("%s: %d features within %.0f m", key, len(feats), spec.search_radius_m)
    lineage.append(
        _lineage(
            "proximity",
            pid,
            vec_refs,
            {k: v.search_radius_m for k, v in module.layers.items()},
            t0,
        )
    )

    # --- Metrics + rules -------------------------------------------------------------------
    c = aoi.geometry.centroid
    metrics = MetricsPayload(
        project_id=pid,
        site=SiteSummary(
            area_ha=aoi.area_ha,
            perimeter_m=aoi.perimeter_m,
            centroid_lon=c.x,
            centroid_lat=c.y,
            analysis_crs=crs,
        ),
        lulc=lulc,
        indices=indices,
        change=change,
        proximity=prox,
    )
    metrics.flags = evaluate(module.rules, metrics.flat())
    return ScreeningResult(
        request=request,
        module=module,
        aoi=aoi,
        metrics=metrics,
        lineage=lineage,
        rasters=rasters,
        layers=layers,
        warnings=warnings,
    )
