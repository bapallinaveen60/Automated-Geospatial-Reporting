"""Project listing and plain-language progress, combining Dagster run state with files on disk."""

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import requests

# Pipeline steps in display order, with wording for non-technical users.
STEPS: list[tuple[str, str]] = [
    ("aoi_request", "Request received"),
    ("aoi_validated", "Checking the site boundary"),
    ("site_location", "Finding the location"),
    ("s2_imagery", "Analysing satellite imagery"),
    ("land_cover", "Mapping land cover"),
    ("proximity_results", "Checking nearby sensitive areas"),
    ("screening_metrics", "Applying screening rules"),
    ("map_plates", "Drawing maps"),
    ("report_draft", "Writing the report"),
]
STEP_STATUS = {
    "SUCCESS": "done",
    "FAILURE": "failed",
    "IN_PROGRESS": "running",
    "SKIPPED": "skipped",
}
RUN_STATE = {
    "QUEUED": "queued",
    "NOT_STARTED": "queued",
    "STARTING": "running",
    "STARTED": "running",
    "SUCCESS": "ready",
    "FAILURE": "failed",
    "CANCELING": "failed",
    "CANCELED": "failed",
}
# Known failure causes → what a non-engineer should be told.
FRIENDLY_ERRORS = [
    ("Typst CLI not found", "The report software (Typst) is not installed on the server."),
    ("Renderer failed", "The map drawing software (QGIS) failed. Check the QGIS setup."),
    ("No Sentinel-2 scenes", "No cloud-free satellite images were found for the chosen dates."),
    ("exceeds the", "The site is larger than the allowed maximum area."),
    ("ConnectionError", "A data service could not be reached. Try again in a few minutes."),
]

State = Literal["queued", "running", "ready", "failed"]

RUN_QUERY = """
query ($pid: String!) {
  runsOrError(filter: {tags: [{key: "dagster/partition", value: $pid}]}, limit: 1) {
    __typename
    ... on Runs { results { runId status startTime endTime stepStats { stepKey status } } }
  }
}"""
FAILURE_QUERY = """
query ($runId: ID!) {
  logsForRun(runId: $runId) {
    ... on EventConnection {
      events { __typename ... on ExecutionStepFailureEvent { error { message cause { message } } } }
    }
  }
}"""


@dataclass
class Step:
    key: str
    label: str
    status: str = "pending"  # pending | running | done | failed | skipped


@dataclass
class ProjectStatus:
    state: State
    label: str
    steps: list[Step] = field(default_factory=list)
    completed: int = 0
    total: int = len(STEPS)
    error: str | None = None
    engine_online: bool = True
    run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _graphql(url: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
    resp = requests.post(
        f"{url.rstrip('/')}/graphql",
        json={"query": query, "variables": variables},
        timeout=5,
    )
    resp.raise_for_status()
    return dict(resp.json().get("data") or {})


def latest_run(project_id: str, dagster_url: str) -> dict[str, Any] | None:
    data = _graphql(dagster_url, RUN_QUERY, {"pid": project_id})
    runs = data.get("runsOrError", {}).get("results") or []
    return runs[0] if runs else None


def failure_message(run_id: str, dagster_url: str) -> str:
    data = _graphql(dagster_url, FAILURE_QUERY, {"runId": run_id})
    events = data.get("logsForRun", {}).get("events") or []
    for ev in events:
        if ev.get("__typename") == "ExecutionStepFailureEvent":
            err = ev.get("error") or {}
            return str((err.get("cause") or {}).get("message") or err.get("message") or "")
    return ""


def friendly_error(raw: str) -> str:
    for needle, message in FRIENDLY_ERRORS:
        if needle in raw:
            return message
    first = raw.strip().splitlines()[0] if raw.strip() else "Unknown error"
    return f"Processing failed: {first[:200]}"


def status_from_run(run: dict[str, Any] | None, report_exists: bool) -> ProjectStatus:
    """Pure mapping from a Dagster run (or none) to user-facing status."""
    steps = [Step(key, label) for key, label in STEPS]
    if run is None:
        if report_exists:
            for s in steps:
                s.status = "done"
            return ProjectStatus("ready", "Report ready", steps, completed=len(steps))
        return ProjectStatus("queued", "Waiting to start", steps)

    by_key = {s["stepKey"]: STEP_STATUS.get(s["status"], "pending") for s in run["stepStats"]}
    for s in steps:
        s.status = by_key.get(s.key, "pending")
    done = sum(s.status == "done" for s in steps)
    state: State = RUN_STATE.get(run["status"], "running")  # type: ignore[assignment]
    if state == "ready":
        label = "Report ready"
    elif state == "failed":
        failed = next((s.label for s in steps if s.status == "failed"), None)
        label = f"Failed while {failed[0].lower() + failed[1:]}" if failed else "Failed"
    elif state == "queued":
        label = "Waiting to start"
    else:
        current = next((s.label for s in steps if s.status == "running"), None)
        current = current or next((s.label for s in steps if s.status == "pending"), "Processing")
        label = f"{current}…"
    return ProjectStatus(state, label, steps, completed=done, run_id=run["runId"])


def project_status(project_id: str, root: Path, dagster_url: str) -> ProjectStatus:
    report_exists = report_path(root, project_id).exists()
    try:
        run = latest_run(project_id, dagster_url)
    except requests.RequestException:
        status = status_from_run(None, report_exists)
        status.engine_online = False
        if status.state == "queued":
            status.label = "Waiting: processing engine is offline"
        return status
    status = status_from_run(run, report_exists)
    if status.state == "failed" and status.run_id:
        try:
            status.error = friendly_error(failure_message(status.run_id, dagster_url))
        except requests.RequestException:
            status.error = "Processing failed."
    return status


def report_path(root: Path, project_id: str) -> Path:
    return root / project_id / "report" / f"{project_id}_draft.pdf"


def list_project_ids(root: Path) -> list[str]:
    ids = {p.stem for p in (root / "incoming").glob("*.json")}
    ids |= {p.parent.name for p in root.glob("*/request.json")}
    return sorted(ids)


def load_request(root: Path, project_id: str) -> tuple[dict[str, Any], datetime] | None:
    for path in (root / "incoming" / f"{project_id}.json", root / project_id / "request.json"):
        if path.exists():
            submitted = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            return json.loads(path.read_text(encoding="utf-8")), submitted
    return None
