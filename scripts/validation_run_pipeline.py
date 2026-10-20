"""Run the screening analysis for every validation site (no plates or PDF).

    uv run python scripts/validation_run_pipeline.py            # all sites
    uv run python scripts/validation_run_pipeline.py val-vashi-creek

Outputs go to <data_root>/<site_id>/analysis/ (metrics.json, lineage.json, rasters, layers),
which is what the QGIS cross-check and the comparison report read. Calls the pipeline
directly, so a running `dagster dev` does not pick these up.
"""

import sys
import time
from pathlib import Path

from geovision.core.config import get_settings
from geovision.core.logging import configure_logging, get_logger
from geovision.core.storage import ProjectStorage
from geovision.pipeline import run_screening
from geovision.validation.sites import export_boundaries, site_requests

log = get_logger("validation")


def main(argv: list[str]) -> int:
    configure_logging()
    export_boundaries()
    wanted = set(argv)
    failures = 0
    for req in site_requests():
        if wanted and req.project_id not in wanted:
            continue
        t = time.perf_counter()
        work = Path(get_settings().data_root) / req.project_id / "analysis"
        try:
            result = run_screening(req, work)
        except Exception:
            log.exception("%s failed", req.project_id)
            failures += 1
            continue
        store = ProjectStorage(req.project_id)
        store.write_json(req, "request.json")
        store.write_json(result.metrics, "analysis", "metrics.json")
        store.write_json(
            {
                "records": [r.model_dump(mode="json") for r in result.lineage],
                "warnings": result.warnings,
            },
            "analysis",
            "lineage.json",
        )
        log.info(
            "%s: %.0f s, %d flag(s), %d warning(s)",
            req.project_id,
            time.perf_counter() - t,
            len(result.metrics.flags),
            len(result.warnings),
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
