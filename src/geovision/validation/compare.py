"""Compare pipeline metrics with independent results (QGIS cross-check, manual baselines).

Metric keys follow ``MetricsPayload.flat()``, e.g. ``site.area_ha``, ``lulc.50.percent``,
``proximity.wetlands_water.distance_m``. A reference value of ``None`` for a distance means
"nothing within the search radius" and matches a pipeline ``None``.
"""

import csv
import fnmatch
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# Metrics under validation, with acceptance tolerances. A value passes if it is within
# EITHER the absolute or the relative tolerance of the reference.
TOLERANCES: list[tuple[str, float, float, str]] = [
    # pattern, absolute, relative, why
    ("site.area_ha", 0.0, 0.005, "0.5%: planar UTM vs ellipsoidal area"),
    ("site.perimeter_m", 0.0, 0.005, "0.5%: planar UTM vs ellipsoidal length"),
    ("lulc.*.percent", 1.0, 0.0, "1 percentage point of site area"),
    # Manual checks use a single clear scene rather than a 12-scene median composite.
    ("indices.ndvi.median", 0.05, 0.0, "0.05 NDVI: single-scene manual vs median composite"),
    ("indices.mndwi.median", 0.05, 0.0, "0.05 MNDWI: single-scene manual vs median composite"),
    ("change.ndvi.loss_ha", 0.5, 0.25, "0.5 ha or 25%: two-scene manual vs composites"),
    ("change.ndvi.gain_ha", 0.5, 0.25, "0.5 ha or 25%: two-scene manual vs composites"),
    ("proximity.*.distance_m", 15.0, 0.0, "15 m: one to two 10 m pixels"),
    ("proximity.*.overlap_ha", 0.05, 0.05, "0.05 ha or 5%"),
]
VALIDATED = [t[0] for t in TOLERANCES]


def tolerance_for(metric: str) -> tuple[float, float, str] | None:
    for pattern, abs_tol, rel_tol, why in TOLERANCES:
        if fnmatch.fnmatchcase(metric, pattern):
            return abs_tol, rel_tol, why
    return None


def within(value: float | None, reference: float | None, metric: str) -> bool | None:
    """True/False against tolerance; None when there is nothing to compare."""
    tol = tolerance_for(metric)
    if tol is None:
        return None
    if reference is None and value is None:
        return True
    if reference is None or value is None:
        return False
    abs_tol, rel_tol, _ = tol
    diff = abs(value - reference)
    return diff <= abs_tol + 1e-9 or diff <= rel_tol * abs(reference) + 1e-9


@dataclass
class Row:
    site_id: str
    metric: str
    pipeline: float | None
    qgis: float | None
    qgis_ok: bool | None
    manual: float | None
    manual_ok: bool | None
    tolerance: str


def pipeline_values(metrics_flat: dict[str, float | None]) -> dict[str, float | None]:
    return {
        k: v for k, v in metrics_flat.items() if any(fnmatch.fnmatchcase(k, p) for p in VALIDATED)
    }


def _reports(values: dict[str, Any] | None, metric: str) -> bool:
    """Whether a reference measured this metric (land cover: any reported class counts)."""
    if values is None:
        return False
    if fnmatch.fnmatchcase(metric, "lulc.*.percent"):
        return any(fnmatch.fnmatchcase(k, "lulc.*.percent") for k in values)
    return metric in values


def _value(values: dict[str, Any], metric: str) -> float | None:
    if metric in values:
        v = values[metric]
        return None if v is None or v == "" else float(v)
    # A land-cover class one side did not report covers 0% of the site.
    return 0.0 if fnmatch.fnmatchcase(metric, "lulc.*.percent") else None


def compare_site(
    site_id: str,
    pipeline: dict[str, float | None],
    qgis: dict[str, Any] | None,
    manual: dict[str, Any] | None,
) -> list[Row]:
    keys = set(pipeline) | set(qgis or {}) | set(manual or {})
    rows = []
    order = ("site.", "lulc.", "indices.", "change.", "proximity.")
    rank = {m: next((i for i, pre in enumerate(order) if m.startswith(pre)), 9) for m in keys}

    def sort_key(m: str) -> tuple[int, int, str]:
        code = m.split(".")[1]
        return (rank[m], int(code) if m.startswith("lulc.") and code.isdigit() else 0, m)

    for metric in sorted((k for k in keys if tolerance_for(k)), key=sort_key):
        p = _value(pipeline, metric)
        q = _value(qgis, metric) if _reports(qgis, metric) else None  # type: ignore[arg-type]
        m = _value(manual, metric) if manual is not None and metric in manual else None
        # Skip land-cover classes absent everywhere (0 vs 0 adds noise).
        if fnmatch.fnmatchcase(metric, "lulc.*.percent") and not any([p, q, m]):
            continue
        tol = tolerance_for(metric)
        rows.append(
            Row(
                site_id=site_id,
                metric=metric,
                pipeline=p,
                qgis=q,
                qgis_ok=within(p, q, metric) if _reports(qgis, metric) else None,
                manual=m,
                manual_ok=within(p, m, metric) if manual is not None and metric in manual else None,
                tolerance=tol[2] if tol else "",
            )
        )
    return rows


def read_manual_baselines(path: Path) -> dict[str, dict[str, str]]:
    """Analyst CSV (validation/baselines/manual_baseline.csv) → {site_id: {metric: value}}.

    Rows with an empty value are treated as not yet measured; the literal ``none`` means
    "nothing within the search radius".
    """
    out: dict[str, dict[str, str]] = {}
    if not path.exists():
        return out
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            value = (row.get("value") or "").strip()
            if not value or row["site_id"].startswith("#"):
                continue
            out.setdefault(row["site_id"], {})[row["metric"]] = (
                "" if value.lower() == "none" else value
            )
    return out


def summarise(rows: list[Row]) -> dict[str, Any]:
    def count(key: str) -> dict[str, int]:
        vals = [getattr(r, key) for r in rows]
        return {
            "compared": sum(v is not None for v in vals),
            "passed": sum(v is True for v in vals),
            "failed": sum(v is False for v in vals),
        }

    return {"qgis": count("qgis_ok"), "manual": count("manual_ok")}


def rows_as_dicts(rows: list[Row]) -> list[dict[str, Any]]:
    return [asdict(r) for r in rows]
