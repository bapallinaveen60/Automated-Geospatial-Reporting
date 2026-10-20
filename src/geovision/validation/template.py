"""Manual baseline spreadsheet for the analyst (validation/baselines/manual_baseline.csv)."""

import csv
from pathlib import Path

from geovision.validation.sites import VALIDATION_DIR, load_site_config

LULC_CLASSES = [
    (10, "Tree cover"),
    (20, "Shrubland"),
    (30, "Grassland"),
    (40, "Cropland"),
    (50, "Built-up"),
    (60, "Bare / sparse vegetation"),
    (70, "Snow and ice"),
    (80, "Permanent water bodies"),
    (90, "Herbaceous wetland"),
    (95, "Mangroves"),
    (100, "Moss and lichen"),
]
RECEPTORS = [
    ("protected_areas", "protected area (NP, WLS, reserve)", 10000),
    ("wetlands_water", "water body or wetland", 2000),
    ("forest", "forest", 1000),
    ("coastline", "coastline", 5000),
]
FLAGS = [
    ("pa_within_10km", "A protected area lies within 10 km (EIA General Condition)"),
    ("pa_overlap", "The site overlaps a protected area"),
    ("wetland_overlap", "A wetland/water body lies inside the site"),
    ("wetland_within_buffer", "A wetland/water body lies within 500 m"),
    ("forest_adjacent", "Forest lies within 500 m"),
    ("coast_crz", "Coastline within 500 m (CRZ likely applies)"),
    ("mangrove_present", "Mangroves present on site"),
    ("vegetation_loss", "More than 0.5 ha of vegetation loss between the periods"),
]
COLUMNS = ["site_id", "metric", "description", "units", "value", "analyst", "date", "method_notes"]


def template_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for site in load_site_config()["sites"]:
        sid = site["id"]

        def add(metric: str, description: str, units: str, _sid: str = sid) -> None:
            rows.append(
                {"site_id": _sid, "metric": metric, "description": description, "units": units}
            )

        add("site.area_ha", "Site area (ellipsoidal)", "ha")
        add("site.perimeter_m", "Site perimeter (ellipsoidal)", "m")
        for code, name in LULC_CLASSES:
            add(f"lulc.{code}.percent", f"WorldCover 2021: {name} share of site (0 if absent)", "%")
        add(
            "indices.ndvi.median",
            "Median NDVI inside site, one clear current-period scene",
            "index",
        )
        add("indices.mndwi.median", "Median MNDWI inside site, same scene", "index")
        add(
            "change.ndvi.loss_ha",
            "Area where NDVI fell by more than 0.15 (baseline → current scene)",
            "ha",
        )
        add("change.ndvi.gain_ha", "Area where NDVI rose by more than 0.15", "ha")
        for key, noun, radius in RECEPTORS:
            add(
                f"proximity.{key}.distance_m",
                f"Shortest distance from site boundary to nearest {noun}; "
                f"'none' if none within {radius / 1000:g} km; 0 if overlapping",
                "m",
            )
            add(f"proximity.{key}.overlap_ha", f"Area of {noun} inside the site", "ha")
        for rule, text in FLAGS:
            add(f"flag.{rule}", f"Should this be flagged? {text}", "yes/no")
    return rows


def write_template(path: Path | None = None, overwrite: bool = False) -> Path:
    out = path or VALIDATION_DIR / "baselines" / "manual_baseline.csv"
    if out.exists() and not overwrite:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for row in template_rows():
            writer.writerow({c: row.get(c, "") for c in COLUMNS})
    return out
