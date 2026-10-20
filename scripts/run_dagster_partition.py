"""Submit an AOI request and run the Dagster screening job for it in-process (no UI needed).

    uv run --extra orchestration python scripts/run_dagster_partition.py REQUEST.json

Uses the persistent instance in DAGSTER_HOME when set (runs then show in `dagster dev`),
otherwise an ephemeral one.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

import dagster as dg

from geovision.contracts import AOIRequest
from geovision.core.config import get_settings
from geovision.orchestration.definitions import defs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("request", help="AOIRequest JSON file")
    args = ap.parse_args()

    request = AOIRequest.model_validate_json(Path(args.request).read_text(encoding="utf-8"))
    incoming = Path(get_settings().data_root) / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.request, incoming / f"{request.project_id}.json")

    instance = (
        dg.DagsterInstance.get()
        if os.environ.get("DAGSTER_HOME")
        else dg.DagsterInstance.ephemeral()
    )
    instance.add_dynamic_partitions("projects", [request.project_id])
    result = defs.resolve_job_def("site_screening").execute_in_process(
        partition_key=request.project_id, instance=instance
    )
    report = result.output_for_node("report_draft") if result.success else None
    print(f"success={result.success} report={report}")
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
