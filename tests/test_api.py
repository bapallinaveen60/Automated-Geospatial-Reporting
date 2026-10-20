"""Web API tests. Dagster is pointed at a closed port, exercising the 'engine offline' path."""

import json
import shutil
from datetime import date

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from geovision.api.main import app, default_periods, new_project_id  # noqa: E402
from geovision.api.status import friendly_error, status_from_run  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    from geovision.core.config import get_settings

    monkeypatch.setenv("GEOVISION_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("GEOVISION_DAGSTER_URL", "http://127.0.0.1:9")
    get_settings.cache_clear()
    yield TestClient(app)
    get_settings.cache_clear()


def _new_project_body(fixtures_dir):
    req = json.loads((fixtures_dir / "request_ameenpur.json").read_text(encoding="utf-8"))
    return {
        "client": "Acme",
        "site_name": "Plot 42, Ameenpur",
        "geometry": req["geometry"],
        "baseline_period": req["baseline_period"],
        "current_period": req["current_period"],
    }


def test_preview_valid_geojson(client, fixtures_dir):
    with open(fixtures_dir / "aoi_ameenpur.geojson", "rb") as f:
        res = client.post("/api/aoi/preview", files={"file": ("site.geojson", f)})
    assert res.status_code == 200
    body = res.json()
    assert 38 < body["area_ha"] < 44
    assert body["geometry"]["type"] == "Polygon"


def test_preview_rejects_unknown_format(client):
    res = client.post("/api/aoi/preview", files={"file": ("site.txt", b"hello")})
    assert res.status_code == 422
    assert "GeoJSON" in res.json()["detail"]


def test_create_list_and_detail_offline(client, tmp_path, fixtures_dir):
    res = client.post("/api/projects", json=_new_project_body(fixtures_dir))
    assert res.status_code == 201
    pid = res.json()["id"]
    assert pid.startswith("plot-42-ameenpur-")
    assert (tmp_path / "incoming" / f"{pid}.json").exists()

    listing = client.get("/api/projects").json()
    assert [p["id"] for p in listing] == [pid]
    assert listing[0]["status"]["state"] == "queued"
    assert listing[0]["status"]["engine_online"] is False

    detail = client.get(f"/api/projects/{pid}").json()
    assert detail["site_name"] == "Plot 42, Ameenpur"
    assert detail["report_url"] is None
    assert len(detail["status"]["steps"]) == 9


def test_create_rejects_overlapping_periods(client, fixtures_dir):
    body = _new_project_body(fixtures_dir)
    body["baseline_period"]["end"] = "2026-01-01"
    assert client.post("/api/projects", json=body).status_code == 422


def test_detail_with_finished_outputs(client, tmp_path, fixtures_dir):
    pid = "demo-ameenpur-001"
    (tmp_path / pid / "analysis" / "plates").mkdir(parents=True)
    (tmp_path / pid / "report").mkdir(parents=True)
    shutil.copy(fixtures_dir / "request_ameenpur.json", tmp_path / pid / "request.json")
    (tmp_path / pid / "report" / f"{pid}_draft.pdf").write_bytes(b"%PDF-1.7")
    (tmp_path / pid / "analysis" / "plates" / "plate1_context.png").write_bytes(b"png")

    detail = client.get(f"/api/projects/{pid}").json()
    assert detail["status"]["state"] == "ready"
    assert detail["report_url"] == f"/api/projects/{pid}/report"
    assert detail["plates"] == [
        {"title": "Site context", "url": f"/api/projects/{pid}/plates/plate1_context.png"}
    ]
    assert client.get(detail["report_url"]).headers["content-type"] == "application/pdf"
    assert client.get(detail["plates"][0]["url"]).status_code == 200


def test_path_traversal_blocked(client):
    assert client.get("/api/projects/..%2F..%2Fetc").status_code == 404
    assert client.get("/api/projects/demo-ameenpur-001/plates/..%2Frequest.json").status_code == 404


def test_status_from_run_maps_steps():
    run = {
        "runId": "r1",
        "status": "STARTED",
        "stepStats": [
            {"stepKey": "aoi_request", "status": "SUCCESS"},
            {"stepKey": "aoi_validated", "status": "SUCCESS"},
            {"stepKey": "s2_imagery", "status": "IN_PROGRESS"},
        ],
    }
    status = status_from_run(run, report_exists=False)
    assert status.state == "running"
    assert status.completed == 2
    assert status.label == "Analysing satellite imagery…"

    failed = status_from_run(
        {
            **run,
            "status": "FAILURE",
            "stepStats": [{"stepKey": "report_draft", "status": "FAILURE"}],
        },
        report_exists=False,
    )
    assert failed.state == "failed"
    assert failed.label == "Failed while writing the report"


def test_friendly_errors_and_defaults():
    assert "Typst" in friendly_error("TypstError: Typst CLI not found ('typst')")
    assert friendly_error("Boom\nstack").startswith("Processing failed: Boom")
    periods = default_periods(date(2026, 10, 20))
    assert periods["current"].to_stac() == "2025-10-01/2026-03-31"
    assert periods["baseline"].to_stac() == "2021-10-01/2022-03-31"
    assert new_project_id("Plot 42!", date(2026, 1, 2)).startswith("plot-42-20260102-")
