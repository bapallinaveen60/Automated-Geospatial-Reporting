"""Run the full vertical slice for one AOI request: analysis → map plates → draft PDF report.

    uv run python scripts/demo_report.py data/fixtures/request_ameenpur.json

Needs GEOVISION_QGIS_PYTHON (or the Docker renderer image) and Typst on PATH
(or GEOVISION_TYPST_BIN).
"""

import argparse
import time
from pathlib import Path

from geovision.carto.plates import render_screening_plates
from geovision.contracts import AOIRequest
from geovision.core.config import get_settings
from geovision.core.logging import configure_logging, get_logger
from geovision.core.storage import ProjectStorage
from geovision.pipeline import run_screening
from geovision.reporting.build_payload import build_payload
from geovision.reporting.charts import render_charts
from geovision.reporting.compile import compile_report

log = get_logger("demo")


def main() -> None:
    configure_logging()
    ap = argparse.ArgumentParser()
    ap.add_argument("request", help="AOIRequest JSON file")
    ap.add_argument("--max-scenes", type=int, default=12)
    args = ap.parse_args()

    request = AOIRequest.model_validate_json(Path(args.request).read_text(encoding="utf-8"))
    work = Path(get_settings().data_root) / request.project_id
    store = ProjectStorage(request.project_id)
    t = time.perf_counter()

    result = run_screening(request, work / "analysis", max_scenes=args.max_scenes)
    store.write_json(result.metrics, "analysis", "metrics.json")
    store.write_json(
        {"records": [r.model_dump(mode="json") for r in result.lineage]}, "analysis", "lineage.json"
    )
    log.info(
        "Analysis done in %.0f s, %d flag(s)", time.perf_counter() - t, len(result.metrics.flags)
    )

    plates = render_screening_plates(
        result.aoi,
        result.layers,
        result.rasters,
        request.project_id,
        work / "analysis",
        periods=(request.baseline_period.to_stac(), request.current_period.to_stac()),
    )
    log.info("Plates rendered: %d", len(plates))

    payload = build_payload(
        request,
        result.metrics,
        result.module.model_dump(),
        lineage=result.lineage,
        plates=plates,
        charts=render_charts(result.metrics, work / "analysis" / "charts"),
        warnings=result.warnings,
    )
    pdf = compile_report(payload, work / "report" / f"{request.project_id}_draft.pdf")
    log.info("Draft report: %s (total %.0f s)", pdf, time.perf_counter() - t)


if __name__ == "__main__":
    main()
