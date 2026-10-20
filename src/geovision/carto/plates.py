"""Standard plate set for the site screening module."""

from pathlib import Path

import geopandas as gpd

from geovision.carto.jobs import PlateJob, PlateLayer, run_plate
from geovision.ingest.aoi import ValidatedAOI

OSM_NOTE = "© OpenStreetMap contributors (ODbL)"

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

    # Plate 2 — current-period NDVI.
    if "ndvi_current" in rasters:
        title = "Plate 2 — Vegetation index (NDVI), current period"
        job = PlateJob(
            title=title,
            subtitle=subtitle,
            extent=aoi.buffered_utm(250).bounds,
            extent_crs=crs,
            layers=[
                site,
                PlateLayer("NDVI", rasters["ndvi_current"], kind="raster", style="ndvi.qml"),
            ],
            output_pdf=plates_dir / "plate2_ndvi.pdf",
            output_png=plates_dir / "plate2_ndvi.png",
            notes=(
                "NDVI from a cloud-masked median composite of Copernicus Sentinel-2 L2A "
                f"imagery (10 m). Basemap: {OSM_NOTE}."
            ),
            padding=0.05,
        )
        run_plate(job, work_dir)
        plates.append({"title": title, "path": str(job.output_png)})

    return plates
