"""Standard plate set for the site screening module."""

from pathlib import Path

import geopandas as gpd

from geovision.carto.jobs import PlateJob, PlateLayer, run_plate
from geovision.ingest.aoi import ValidatedAOI

OSM_NOTE = "© OpenStreetMap contributors (ODbL)"

# WorldCover class labels as written in styles/worldcover.qml.
WORLDCOVER_LABELS = {
    10: "Tree cover",
    20: "Shrubland",
    30: "Grassland",
    40: "Cropland",
    50: "Built-up",
    60: "Bare / sparse vegetation",
    70: "Snow and ice",
    80: "Permanent water bodies",
    90: "Herbaceous wetland",
    95: "Mangroves",
    100: "Moss and lichen",
}


def _classes_present(raster: Path) -> list[str]:
    import numpy as np
    import rasterio

    with rasterio.open(raster) as src:
        values = np.unique(src.read(1))
    return [WORLDCOVER_LABELS[int(v)] for v in values if int(v) in WORLDCOVER_LABELS]


# Vector layers drawn on the context plate, top to bottom: key -> legend label.
CONTEXT_LAYERS = {
    "coastline": "Coastline",
    "wetlands_water": "Water bodies / wetlands",
    "forest": "Forest",
    "protected_areas": "Protected areas",
}


def render_screening_plates(
    aoi: ValidatedAOI,
    layers: dict[str, Path],
    rasters: dict[str, Path],
    project_id: str,
    work_dir: Path,
    context_buffer_m: float = 2000,
    periods: tuple[str, str] | None = None,
) -> list[dict[str, str]]:
    """Render the plates and return ``[{"title", "path"}]`` with PNG paths for the report."""
    crs = aoi.utm_crs.to_string()
    plates_dir = work_dir / "plates"
    plates_dir.mkdir(parents=True, exist_ok=True)
    subtitle = f"{project_id} · {aoi.area_ha:.2f} ha · {crs}"
    site = PlateLayer("Site boundary", layers["aoi"], style="aoi.qml")
    plates: list[dict[str, str]] = []

    # Plate 1 — site context with buffer and sensitive receptors.
    buffer_path = work_dir / "layers" / "buffer.gpkg"
    gpd.GeoDataFrame(geometry=[aoi.buffered_utm(context_buffer_m)], crs=aoi.utm_crs).to_file(
        buffer_path, driver="GPKG"
    )
    ctx_layers = [
        site,
        PlateLayer(f"{context_buffer_m / 1000:g} km buffer", buffer_path, style="buffer.qml"),
    ]
    for key, label in CONTEXT_LAYERS.items():
        if key in layers:
            ctx_layers.append(PlateLayer(label, layers[key], style=f"{key}.qml"))
    title = "Plate 1 — Site context and sensitive receptors"
    job = PlateJob(
        title=title,
        subtitle=subtitle,
        extent=aoi.buffered_utm(context_buffer_m).bounds,
        extent_crs=crs,
        layers=ctx_layers,
        output_pdf=plates_dir / "plate1_context.pdf",
        output_png=plates_dir / "plate1_context.png",
        notes=f"Receptor layers and basemap: {OSM_NOTE}.\nScreening only, not survey-grade.",
        padding=0.05,
    )
    run_plate(job, work_dir)
    plates.append({"title": title, "path": str(job.output_png)})

    s2_note = "Copernicus Sentinel-2 L2A, cloud-masked median composite (10 m)"
    baseline, current = periods or ("baseline period", "current period")
    # (raster key, file stem, title, legend name, style, notes)
    raster_plates = [
        (
            "ndvi_current",
            "ndvi",
            "Vegetation index (NDVI), current period",
            "NDVI",
            "ndvi.qml",
            f"NDVI for {current}. Source: {s2_note}.",
        ),
        (
            "worldcover",
            "landcover",
            "Land use / land cover",
            "ESA WorldCover",
            "worldcover.qml",
            "ESA WorldCover 10 m (CC BY 4.0, © ESA WorldCover project).",
        ),
        (
            "ndvi_change",
            "ndvi_change",
            "Vegetation change between periods (ΔNDVI)",
            "NDVI change",
            "ndvi_change.qml",
            f"ΔNDVI = current ({current}) − baseline ({baseline}). Source: {s2_note}. "
            f"Basemap: {OSM_NOTE}.",
        ),
    ]
    for key, stem, name, legend, style, notes in raster_plates:
        if key not in rasters:
            continue
        n = len(plates) + 1
        title = f"Plate {n} — {name}"
        job = PlateJob(
            title=title,
            subtitle=subtitle,
            extent=aoi.buffered_utm(250).bounds,
            extent_crs=crs,
            layers=[
                site,
                PlateLayer(
                    legend,
                    rasters[key],
                    kind="raster",
                    style=style,
                    legend_keep=_classes_present(rasters[key]) if key == "worldcover" else None,
                ),
            ],
            output_pdf=plates_dir / f"plate{n}_{stem}.pdf",
            output_png=plates_dir / f"plate{n}_{stem}.png",
            notes=notes,
            padding=0.05,
        )
        run_plate(job, work_dir)
        plates.append({"title": title, "path": str(job.output_png)})

    return plates
