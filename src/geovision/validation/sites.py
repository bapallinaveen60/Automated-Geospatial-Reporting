"""Validation site set (validation/sites.json) → pipeline requests and analyst boundary files."""

import json
from pathlib import Path
from typing import Any

from geovision.contracts import AOIRequest

VALIDATION_DIR = Path(__file__).resolve().parents[3] / "validation"
HALF_WIDTH_DEG = 0.0035
HALF_HEIGHT_DEG = 0.0025


def _box(lon: float, lat: float) -> dict[str, Any]:
    x0, x1 = round(lon - HALF_WIDTH_DEG, 6), round(lon + HALF_WIDTH_DEG, 6)
    y0, y1 = round(lat - HALF_HEIGHT_DEG, 6), round(lat + HALF_HEIGHT_DEG, 6)
    return {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


def load_site_config(path: Path | None = None) -> dict[str, Any]:
    return dict(json.loads((path or VALIDATION_DIR / "sites.json").read_text(encoding="utf-8")))


def site_requests(path: Path | None = None) -> list[AOIRequest]:
    cfg = load_site_config(path)
    return [
        AOIRequest(
            project_id=s["id"],
            client="GeoVision validation",
            site_name=s["name"],
            geometry=_box(*s["centre"]),
            baseline_period=cfg["baseline_period"],
            current_period=cfg["current_period"],
            notes=s["purpose"],
        )
        for s in cfg["sites"]
    ]


def export_boundaries(out_dir: Path | None = None) -> list[Path]:
    """Write one GeoJSON per site (EPSG:4326) for the analyst to load into QGIS."""
    out = out_dir or VALIDATION_DIR / "boundaries"
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for req in site_requests():
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"site_id": req.project_id, "name": req.site_name},
                    "geometry": req.geometry,
                }
            ],
        }
        path = out / f"{req.project_id}.geojson"
        path.write_text(json.dumps(fc, indent=2) + "\n", encoding="utf-8")
        paths.append(path)
    return paths
