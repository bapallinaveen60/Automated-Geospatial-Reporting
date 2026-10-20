"""Independent recomputation of screening metrics with QGIS algorithms (Phase 7 cross-check).

Runs in QGIS's Python (stdlib + qgis only), on the inputs the pipeline saved:

    "C:\\Program Files\\QGIS 3.44.15\\bin\\python-qgis-ltr.bat" ^
        scripts\\validation_qgis_crosscheck.py data\\runs val-ameenpur val-vashi-creek ...

For each site it writes <root>/<site>/validation/qgis_crosscheck.json with the same metric
keys as the manual baseline template. Methods deliberately differ from the pipeline where
possible: ellipsoidal (WGS84) area, perimeter and distances instead of planar UTM, and QGIS
zonal histogram / zonal statistics / reclassify instead of rasterio + numpy.
"""

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import (  # noqa: E402
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsDistanceArea,
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
)

WGS84 = QgsCoordinateReferenceSystem("EPSG:4326")
LAYERS = ("protected_areas", "wetlands_water", "forest", "coastline")
CHANGE_THRESHOLD = 0.15  # module.yaml indices.ndvi.change_threshold


def _init():
    qgs = QgsApplication([], False)
    qgs.initQgis()
    sys.path.append(os.path.join(QgsApplication.pkgDataPath(), "python", "plugins"))
    from processing.core.Processing import Processing

    Processing.initialize()
    import processing

    return qgs, processing


def _vector(path: Path, name: str) -> QgsVectorLayer:
    layer = QgsVectorLayer(str(path), name, "ogr")
    if not layer.isValid():
        raise RuntimeError(f"Cannot open {path}")
    return layer


def _single_geometry(layer: QgsVectorLayer):
    geoms = [f.geometry() for f in layer.getFeatures()]
    geom = geoms[0]
    for g in geoms[1:]:
        geom = geom.combine(g)
    return geom


def _ellipsoid() -> QgsDistanceArea:
    da = QgsDistanceArea()
    da.setSourceCrs(WGS84, QgsProject.instance().transformContext())
    da.setEllipsoid("WGS84")
    return da


def _to_wgs84(geom, crs):
    g = type(geom)(geom)
    g.transform(QgsCoordinateTransform(crs, WGS84, QgsProject.instance()))
    return g


def _histogram(processing, raster: str, aoi: str) -> dict[int, int]:
    out = processing.run(
        "native:zonalhistogram",
        {
            "INPUT_RASTER": raster,
            "RASTER_BAND": 1,
            "INPUT_VECTOR": aoi,
            "COLUMN_PREFIX": "H_",
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]
    counts: dict[int, int] = {}
    for feat in out.getFeatures():
        for field in feat.fields():
            name = field.name()
            if name.startswith("H_") and name[2:].lstrip("-").isdigit():
                counts[int(name[2:])] = counts.get(int(name[2:]), 0) + int(feat[name] or 0)
    return counts


def _pixel_area(raster: str) -> float:
    layer = QgsRasterLayer(raster, "r", "gdal")
    return abs(layer.rasterUnitsPerPixelX() * layer.rasterUnitsPerPixelY())


def crosscheck(processing, site_dir: Path) -> dict:
    analysis = site_dir / "analysis"
    metrics = json.loads((analysis / "metrics.json").read_text(encoding="utf-8"))
    aoi_path = analysis / "layers" / "aoi.gpkg"
    aoi_layer = _vector(aoi_path, "aoi")
    utm = aoi_layer.crs()
    aoi_utm = _single_geometry(aoi_layer)
    aoi_wgs = _to_wgs84(aoi_utm, utm)
    da = _ellipsoid()
    values: dict[str, float | None] = {}
    notes: list[str] = []

    # Area and perimeter on the WGS84 ellipsoid (pipeline: planar UTM).
    values["site.area_ha"] = da.measureArea(aoi_wgs) / 10_000
    values["site.perimeter_m"] = da.measurePerimeter(aoi_wgs)

    # Land cover: QGIS zonal histogram (pixel-centre rule) on the saved WorldCover grid.
    wc = analysis / "rasters" / "worldcover.tif"
    if wc.exists():
        counts = {k: v for k, v in _histogram(processing, str(wc), str(aoi_path)).items() if k > 0}
        total = sum(counts.values())
        for code, n in counts.items():
            values[f"lulc.{code}.percent"] = 100 * n / total if total else None
    else:
        notes.append("worldcover.tif missing")

    # Median NDVI / MNDWI: QGIS zonal statistics.
    for index in ("ndvi", "mndwi"):
        raster = analysis / "rasters" / f"{index}_current.tif"
        if not raster.exists():
            notes.append(f"{raster.name} missing")
            continue
        out = processing.run(
            "native:zonalstatisticsfb",
            {
                "INPUT": str(aoi_path),
                "INPUT_RASTER": str(raster),
                "RASTER_BAND": 1,
                "COLUMN_PREFIX": "z_",
                "STATISTICS": [3],  # median
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
        )["OUTPUT"]
        feat = next(out.getFeatures())
        values[f"indices.{index}.median"] = float(feat["z_median"])

    # Vegetation loss / gain: reclassify ΔNDVI, then zonal histogram.
    change = analysis / "rasters" / "ndvi_change.tif"
    if change.exists():
        t = CHANGE_THRESHOLD
        reclass = processing.run(
            "native:reclassifybytable",
            {
                "INPUT_RASTER": str(change),
                "RASTER_BAND": 1,
                "TABLE": [-1e9, -t, 1, -t, t, 3, t, 1e9, 2],
                "RANGE_BOUNDARIES": 1,  # min <= value < max
                "NO_DATA": 0,
                "DATA_TYPE": 1,  # Byte
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
        )["OUTPUT"]
        counts = _histogram(processing, reclass, str(aoi_path))
        px_ha = _pixel_area(str(change)) / 10_000
        values["change.ndvi.loss_ha"] = counts.get(1, 0) * px_ha
        values["change.ndvi.gain_ha"] = counts.get(2, 0) * px_ha
    else:
        notes.append("ndvi_change.tif missing")

    # Receptors: ellipsoidal length of the shortest line between site and nearest feature.
    radius = {p["layer"]: p["search_radius_m"] for p in metrics.get("proximity", [])}
    for key in LAYERS:
        if key not in radius:
            continue
        path = analysis / "layers" / f"{key}.gpkg"
        if not path.exists():
            values[f"proximity.{key}.distance_m"] = None
            values[f"proximity.{key}.overlap_ha"] = 0.0
            continue
        layer = _vector(path, key)
        best = None
        overlap_ha = 0.0
        union = None
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if layer.crs() != utm:
                geom.transform(QgsCoordinateTransform(layer.crs(), utm, QgsProject.instance()))
            line = aoi_utm.shortestLine(geom)
            d = 0.0 if aoi_utm.intersects(geom) else da.measureLength(_to_wgs84(line, utm))
            best = d if best is None else min(best, d)
            union = geom if union is None else union.combine(geom)
        if union is not None:
            inter = aoi_utm.intersection(union)
            if not inter.isEmpty():
                overlap_ha = da.measureArea(_to_wgs84(inter, utm)) / 10_000
        values[f"proximity.{key}.distance_m"] = (
            best if best is not None and best <= radius[key] else None
        )
        values[f"proximity.{key}.overlap_ha"] = overlap_ha

    return {
        "site_id": site_dir.name,
        "method": f"QGIS {Qgis.version()} automated cross-check",
        "computed_at": datetime.now(UTC).isoformat(),
        "values": values,
        "notes": notes,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    root = Path(argv[0])
    qgs, processing = _init()
    failures = 0
    try:
        for site in argv[1:]:
            try:
                result = crosscheck(processing, root / site)
            except Exception as e:  # noqa: BLE001
                print(f"{site}: FAILED {e}")
                failures += 1
                continue
            out = root / site / "validation" / "qgis_crosscheck.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(f"{site}: {len(result['values'])} metrics -> {out}")
    finally:
        qgs.exitQgis()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
