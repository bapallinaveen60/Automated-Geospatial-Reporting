import json

import pytest
from pydantic import ValidationError

from geovision.contracts import AOIRequest, export_schemas


def _request(fixtures_dir):
    return json.loads((fixtures_dir / "request_ameenpur.json").read_text(encoding="utf-8"))


def test_fixture_request_valid(fixtures_dir):
    req = AOIRequest.model_validate(_request(fixtures_dir))
    assert req.baseline_period.to_stac() == "2021-10-01/2022-03-31"


def test_periods_must_not_overlap(fixtures_dir):
    data = _request(fixtures_dir)
    data["baseline_period"]["end"] = "2026-01-01"
    with pytest.raises(ValidationError, match="baseline_period"):
        AOIRequest.model_validate(data)


def test_bad_project_id(fixtures_dir):
    data = _request(fixtures_dir)
    data["project_id"] = "Bad ID!"
    with pytest.raises(ValidationError):
        AOIRequest.model_validate(data)


def test_export_schemas(tmp_path):
    names = {p.name for p in export_schemas(tmp_path)}
    assert names == {
        "AOIRequest.schema.json",
        "MetricsPayload.schema.json",
        "LineageRecord.schema.json",
    }
