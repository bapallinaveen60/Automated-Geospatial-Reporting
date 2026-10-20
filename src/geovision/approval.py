"""Professional review and sign-off of draft reports.

A review is tied to the exact draft it was made on (SHA-256 of the draft PDF). If the pipeline
re-runs and produces a different draft, the earlier decision no longer applies and the project
needs review again. Every decision is appended to an audit log that is never rewritten.

Files per project:
    <root>/<id>/review/review.json   latest decision
    <root>/<id>/review/audit.jsonl   append-only event log
    <root>/<id>/report/<id>_final.pdf  issued report (approved drafts only)

Note: reviewer identity is self-declared until the app has user accounts.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from geovision.reporting.compile import compile_report, payload_path

Decision = Literal["approved", "changes_requested"]
Disposition = Literal["confirmed", "dismissed", "site_visit"]
DISPOSITION_TEXT: dict[str, str] = {
    "confirmed": "Confirmed",
    "dismissed": "Not applicable",
    "site_visit": "Site visit required",
}


class ApprovalError(ValueError):
    pass


class Reviewer(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    qualification: str = Field(min_length=2, max_length=160)
    registration_no: str = Field(min_length=1, max_length=80)
    organisation: str | None = Field(default=None, max_length=160)


class FlagReview(BaseModel):
    disposition: Disposition
    note: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def _dismissal_needs_reason(self) -> "FlagReview":
        if self.disposition == "dismissed" and not self.note.strip():
            raise ValueError("A finding marked not applicable needs a justification")
        return self


class ReviewSubmission(BaseModel):
    decision: Decision
    reviewer: Reviewer
    comments: str = Field(default="", max_length=4000)
    flag_reviews: dict[str, FlagReview] = Field(default_factory=dict)


class ReviewRecord(ReviewSubmission):
    decided_at: datetime
    draft_sha256: str
    final_sha256: str | None = None


def _dir(root: Path, project_id: str) -> Path:
    return root / project_id / "review"


def draft_pdf(root: Path, project_id: str) -> Path:
    return root / project_id / "report" / f"{project_id}_draft.pdf"


def final_pdf(root: Path, project_id: str) -> Path:
    return root / project_id / "report" / f"{project_id}_final.pdf"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_review(root: Path, project_id: str) -> ReviewRecord | None:
    path = _dir(root, project_id) / "review.json"
    if not path.exists():
        return None
    return ReviewRecord.model_validate_json(path.read_text(encoding="utf-8"))


def current_review(root: Path, project_id: str) -> ReviewRecord | None:
    """The latest decision, but only if it was made on the draft that exists now."""
    record = load_review(root, project_id)
    draft = draft_pdf(root, project_id)
    if record is None or not draft.exists() or record.draft_sha256 != sha256(draft):
        return None
    return record


def append_audit(root: Path, project_id: str, event: str, **details: Any) -> None:
    path = _dir(root, project_id) / "audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"at": datetime.now(UTC).isoformat(), "event": event, **details}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def read_audit(root: Path, project_id: str) -> list[dict[str, Any]]:
    path = _dir(root, project_id) / "audit.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def submit_review(root: Path, project_id: str, submission: ReviewSubmission) -> ReviewRecord:
    """Record a decision on the current draft; on approval, issue the final PDF."""
    draft = draft_pdf(root, project_id)
    source = payload_path(draft)
    if not draft.exists() or not source.exists():
        raise ApprovalError("There is no draft report to review yet.")
    payload = json.loads(source.read_text(encoding="utf-8"))
    flags = payload.get("metrics", {}).get("flags", [])

    if submission.decision == "approved":
        missing = [
            f["message"]
            for f in flags
            if f["severity"] in ("critical", "warning")
            and f["rule_id"] not in submission.flag_reviews
        ]
        if missing:
            raise ApprovalError(
                f"Give a disposition for every finding before approving ({len(missing)} missing)."
            )

    record = ReviewRecord(
        **submission.model_dump(),
        decided_at=datetime.now(UTC),
        draft_sha256=sha256(draft),
    )

    if submission.decision == "approved":
        final = final_pdf(root, project_id)
        compile_report(
            {
                **payload,
                "draft": False,
                "reviewer": {
                    **submission.reviewer.model_dump(),
                    "date": record.decided_at.date().isoformat(),
                    "comments": submission.comments,
                },
                "flag_reviews": {
                    k: {"disposition": DISPOSITION_TEXT[v.disposition], "note": v.note}
                    for k, v in submission.flag_reviews.items()
                },
            },
            final,
        )
        record.final_sha256 = sha256(final)
    else:
        final_pdf(root, project_id).unlink(missing_ok=True)

    path = _dir(root, project_id) / "review.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    append_audit(
        root,
        project_id,
        submission.decision,
        reviewer=submission.reviewer.name,
        registration_no=submission.reviewer.registration_no,
        draft_sha256=record.draft_sha256,
        final_sha256=record.final_sha256,
        comments=submission.comments,
    )
    return record
