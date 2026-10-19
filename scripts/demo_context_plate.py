"""Render a site-context plate for an AOI: boundary, 2 km buffer, OSM water/wetlands and
protected areas on an OSM basemap.

    uv run python scripts/demo_context_plate.py data/fixtures/aoi_ameenpur.geojson demo-ameenpur-001

Uses local QGIS when GEOVISION_QGIS_PYTHON is set, otherwise the geovision-qgis Docker image.
"""

import argparse
from pathlib import Path

import geopandas as gpd

from geovision.carto.jobs import PlateJob, PlateLayer, run_plate
from geovision.core.config import get_settings
from geovision.core.logging import configure_logging, get_logger
from geovision.ingest.aoi import read_aoi, validate_aoi
from geovision.ingest.vector_sources import OSMSource

log = get_logger("demo")
BUFFER_M = 2000


def main() -> None:
    configure_logging()
    ap = argparse.ArgumentParser()
    ap.add_argument("aoi")
    ap.add_argument("project_id")
    args = ap.parse_args()

    aoi = validate_aoi(read_aoi(args.aoi))
    utm = aoi.utm_crs
    work = Path(get_settings().data_root) / args.project_id / "carto"
    (work / "layers").mkdir(parents=True, exist_ok=True)
    (work / "plates").mkdir(parents=True, exist_ok=True)

    aoi_path = work / "layers" / "aoi.gpkg"
    aoi.to_gdf(utm=True).to_file(aoi_path, driver="GPKG")
    buffer_path = work / "layers" / "buffer.gpkg"
    gpd.GeoDataFrame(geometry=[aoi.buffered_utm(BUFFER_M)], crs=utm).to_file(buffer_path)

    layers = [PlateLayer("Site boundary", aoi_path, style="aoi.qml")]
    layers.append(PlateLayer(f"{BUFFER_M / 1000:g} km buffer", buffer_path, style="buffer.qml"))
    fetch_bbox = aoi.buffered_bbox(BUFFER_M * 1.5)
    for key, label, tags in [
        ("wetlands_water", "Water bodies / wetlands", {"natural": ["water", "wetland"]}),
        ("protected_areas", "Protected areas", {"boundary": ["protected_area", "national_park"]}),
    ]:
        feats = OSMSource(key, tags).fetch(fetch_bbox)
        log.info("%s: %d features", key, len(feats))
        if feats.empty:
            continue
        path = work / "layers" / f"{key}.gpkg"
        feats.to_crs(utm).to_file(path, driver="GPKG")
        layers.append(PlateLayer(label, path, style=f"{key}.qml"))

    extent = aoi.buffered_utm(BUFFER_M).bounds
    job = PlateJob(
        title="Plate 1 — Site context",
        subtitle=f"{args.project_id} · {aoi.area_ha:.2f} ha · {utm.to_string()}",
        extent=extent,
        extent_crs=utm.to_string(),
        layers=layers,
        output_pdf=work / "plates" / "plate1_context.pdf",
        output_png=work / "plates" / "plate1_context.png",
        notes=(
            "Water bodies, wetlands and protected areas: © OpenStreetMap contributors (ODbL).\n"
            "Basemap: © OpenStreetMap contributors.\n"
            "Screening only, not a survey-grade map."
        ),
        padding=0.05,
    )
    pdf = run_plate(job, work)
    log.info("Rendered %s", pdf)


if __name__ == "__main__":
    main()
