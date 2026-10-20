# ruff: noqa: E501  (Markdown report text)
"""Build the Phase 7 validation report from pipeline outputs, the QGIS cross-check and the
analyst's manual baselines.

    uv run python scripts/validation_report.py

Reads   <data_root>/<site>/analysis/metrics.json
        <data_root>/<site>/validation/qgis_crosscheck.json
        validation/baselines/manual_baseline.csv   (filled in by the GIS/EIA analyst)
Writes  validation/REPORT.md and validation/results.json
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from geovision.contracts import MetricsPayload
from geovision.core.config import get_settings
from geovision.validation.compare import (
    TOLERANCES,
    compare_site,
    pipeline_values,
    read_manual_baselines,
    rows_as_dicts,
    summarise,
)
from geovision.validation.sites import VALIDATION_DIR, load_site_config

LABELS = {
    "site.area_ha": "Site area (ha)",
    "site.perimeter_m": "Perimeter (m)",
    "indices.ndvi.median": "NDVI median",
    "indices.mndwi.median": "MNDWI median",
    "change.ndvi.loss_ha": "Vegetation loss (ha)",
    "change.ndvi.gain_ha": "Vegetation gain (ha)",
}
LULC = {
    "10": "Tree cover",
    "20": "Shrubland",
    "30": "Grassland",
    "40": "Cropland",
    "50": "Built-up",
    "60": "Bare / sparse",
    "70": "Snow / ice",
    "80": "Permanent water",
    "90": "Herbaceous wetland",
    "95": "Mangroves",
    "100": "Moss / lichen",
}
LAYERS = {
    "protected_areas": "protected area",
    "wetlands_water": "water / wetland",
    "forest": "forest",
    "coastline": "coastline",
}


def label(metric: str) -> str:
    if metric in LABELS:
        return LABELS[metric]
    parts = metric.split(".")
    if parts[0] == "lulc":
        return f"Land cover: {LULC.get(parts[1], parts[1])} (%)"
    if parts[0] == "proximity":
        what = "distance (m)" if parts[2] == "distance_m" else "overlap (ha)"
        return f"Nearest {LAYERS.get(parts[1], parts[1])}, {what}"
    return metric


def fmt(v: float | None, metric: str) -> str:
    if v is None:
        return "none" if metric.startswith("proximity") else "—"
    if abs(v) >= 100:
        return f"{v:,.0f}"
    return f"{v:.3f}" if metric.startswith("indices") else f"{v:.2f}"


def mark(ok: bool | None) -> str:
    return {True: "✅", False: "❌", None: "·"}[ok]


def main() -> None:
    root = Path(get_settings().data_root)
    cfg = load_site_config()
    manual = read_manual_baselines(VALIDATION_DIR / "baselines" / "manual_baseline.csv")
    all_rows = []
    site_sections = []
    flag_rows = []
    for site in cfg["sites"]:
        sid = site["id"]
        metrics_path = root / sid / "analysis" / "metrics.json"
        if not metrics_path.exists():
            site_sections.append(
                f"### {site['name']}\n\nPipeline output missing; run the pipeline first.\n"
            )
            continue
        metrics = MetricsPayload.model_validate_json(metrics_path.read_text(encoding="utf-8"))
        qgis_path = root / sid / "validation" / "qgis_crosscheck.json"
        qgis = (
            json.loads(qgis_path.read_text(encoding="utf-8"))["values"]
            if qgis_path.exists()
            else None
        )
        site_manual = manual.get(sid)
        rows = compare_site(sid, pipeline_values(metrics.flat()), qgis, site_manual)
        all_rows += rows

        lines = [
            f"### {site['name']} (`{sid}`)",
            "",
            f"*Purpose:* {site['purpose']}",
            "",
            "| Metric | Pipeline | QGIS cross-check | | Manual baseline | | Tolerance |",
            "|---|---:|---:|:-:|---:|:-:|---|",
        ]
        for r in rows:
            lines.append(
                f"| {label(r.metric)} | {fmt(r.pipeline, r.metric)} | {fmt(r.qgis, r.metric)} | "
                f"{mark(r.qgis_ok)} | {fmt(r.manual, r.metric) if r.manual_ok is not None else 'pending'} | "
                f"{mark(r.manual_ok)} | {r.tolerance} |"
            )
        raised = {f.rule_id for f in metrics.flags}
        lines += [
            "",
            "**Flags raised by the pipeline:** "
            + (", ".join(f"`{f.rule_id}`" for f in metrics.flags) or "none"),
        ]
        for key, val in (site_manual or {}).items():
            if key.startswith("flag."):
                rule = key[5:]
                analyst = val.strip().lower() in ("yes", "y", "true", "1")
                flag_rows.append((sid, rule, rule in raised, analyst))
        site_sections.append("\n".join(lines) + "\n")

    summary = summarise(all_rows)
    measured = sum(len(v) for v in manual.values())
    flag_agree = sum(p == a for _, _, p, a in flag_rows)
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    report = [
        "# Phase 7 validation report",
        "",
        f"Generated {now} by `scripts/validation_report.py`. Do not edit by hand.",
        "",
        "## Summary",
        "",
        "| Check | Compared | Passed | Failed |",
        "|---|---:|---:|---:|",
        f"| Pipeline vs automated QGIS cross-check | {summary['qgis']['compared']} | {summary['qgis']['passed']} | {summary['qgis']['failed']} |",
        f"| Pipeline vs manual analyst baseline | {summary['manual']['compared']} | {summary['manual']['passed']} | {summary['manual']['failed']} |",
        f"| Analyst agrees with pipeline flags | {len(flag_rows)} | {flag_agree} | {len(flag_rows) - flag_agree} |",
        "",
        (
            "**Manual baselines are pending.** The pipeline is not yet validated for client use. "
            "The analyst follows `validation/MANUAL_PROTOCOL.md` and fills in "
            "`validation/baselines/manual_baseline.csv`; then re-run this script."
            if measured == 0
            else f"{measured} manual measurements received."
        ),
        "",
        "## What each check proves",
        "",
        "- **Automated QGIS cross-check** recomputes every metric from the pipeline's own saved inputs "
        "with QGIS algorithms (ellipsoidal area/length, zonal histogram, zonal statistics, reclassify). "
        "It catches computation errors (projection, pixel inclusion, unit, masking bugs). It cannot catch "
        "wrong or incomplete *input* data.",
        "- **Manual baseline** is an analyst's independent workflow in QGIS Desktop from the source "
        "datasets, plus their judgement on whether each flag is right for the site. It is the evidence "
        "that the reports are fit for client use.",
        "",
        "## Tolerances",
        "",
        "| Metric | Absolute | Relative | Rationale |",
        "|---|---:|---:|---|",
        *[f"| `{p}` | {a:g} | {r:.1%} | {why} |" for p, a, r, why in TOLERANCES],
        "",
        "## Results by site",
        "",
        *site_sections,
    ]
    if flag_rows:
        report += [
            "## Flag agreement",
            "",
            "| Site | Rule | Pipeline raised | Analyst says should be raised | |",
            "|---|---|:-:|:-:|:-:|",
            *[
                f"| `{s}` | `{r}` | {'yes' if p else 'no'} | {'yes' if a else 'no'} | {mark(p == a)} |"
                for s, r, p, a in flag_rows
            ],
            "",
        ]

    (VALIDATION_DIR / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    (VALIDATION_DIR / "results.json").write_text(
        json.dumps(
            {"generated": now, "summary": summary, "rows": rows_as_dicts(all_rows)}, indent=2
        ),
        encoding="utf-8",
    )
    print(f"QGIS: {summary['qgis']}  manual: {summary['manual']}")


if __name__ == "__main__":
    main()
