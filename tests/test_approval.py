"""Approval workflow: compiles real PDFs, so it needs Typst (skipped when unavailable)."""

import json

import pytest
from pydantic import ValidationError

from geovision.approval import (
    ApprovalError,
    FlagReview,
    ReviewSubmission,
    current_review,
    draft_pdf,
    final_pdf,
    read_audit,
    submit_review,
)
from geovision.contracts import AOIRequest, ExceedanceFlag
from geovision.reporting.build_payload import build_payload
from geovision.reporting.compile import TypstError, compile_report, find_typst
from tests.test_reporting import _metrics

try:
    find_typst()
except TypstError:
    pytest.skip("Typst not installed", allow_module_level=True)

PID = "demo-ameenpur-001"
REVIEWER = {
    "name": "A. Rao",
    "qualification": "QCI-NABET EIA Coordinator",
    "registration_no": "NABET/EIA/1234",
}


@pytest.fixture
def root(tmp_path, fixtures_dir):
    request = AOIRequest.model_validate_json((fixtures_dir / "request_ameenpur.json").read_text())
    metrics = _metrics(project_id=PID)
    metrics.flags = [
        ExceedanceFlag(
            rule_id="wetland_within_buffer",
            severity="warning",
            message="A wetland lies 49 m from the site.",
            metric="proximity.wetlands_water.distance_m",
            value=49,
            threshold=500,
        )
    ]
    payload = build_payload(request, metrics, {"name": "site_screening_in", "title": "Screening"})
    compile_report(payload, draft_pdf(tmp_path, PID))
    return tmp_path


def _submit(decision="approved", flag_reviews=None):
    return ReviewSubmission.model_validate(
        {
            "decision": decision,
            "reviewer": REVIEWER,
            "comments": "Checked against site photos.",
            "flag_reviews": flag_reviews
            if flag_reviews is not None
            else {
                "wetland_within_buffer": {"disposition": "site_visit", "note": "Verify lake edge"}
            },
        }
    )


def test_approval_requires_every_finding_reviewed(root):
    with pytest.raises(ApprovalError, match="1 missing"):
        submit_review(root, PID, _submit(flag_reviews={}))


def test_dismissal_needs_justification():
    with pytest.raises(ValidationError, match="justification"):
        FlagReview(disposition="dismissed", note=" ")


def test_approve_issues_final_pdf_and_audit(root):
    record = submit_review(root, PID, _submit())
    final = final_pdf(root, PID)
    assert final.exists() and record.final_sha256
    assert current_review(root, PID).decision == "approved"
    audit = read_audit(root, PID)
    assert audit[-1]["event"] == "approved"
    assert audit[-1]["registration_no"] == "NABET/EIA/1234"


def test_changes_requested_removes_final(root):
    submit_review(root, PID, _submit())
    submit_review(root, PID, _submit(decision="changes_requested", flag_reviews={}))
    assert not final_pdf(root, PID).exists()
    assert [e["event"] for e in read_audit(root, PID)] == ["approved", "changes_requested"]


def test_review_goes_stale_when_draft_changes(root):
    submit_review(root, PID, _submit())
    draft = draft_pdf(root, PID)
    payload = json.loads(draft.with_name(f"{draft.stem}.payload.json").read_text())
    payload["generated"] = "2099-01-01"
    compile_report(payload, draft)
    assert current_review(root, PID) is None
