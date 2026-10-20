"""Dagster wiring checks (no network). Skipped unless the orchestration extra is installed."""

import shutil

import pytest

dg = pytest.importorskip("dagster")


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    from geovision.core.config import get_settings

    monkeypatch.setenv("GEOVISION_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_definitions_load_and_graph_shape():
    from geovision.orchestration.definitions import defs

    graph = defs.resolve_asset_graph()
    keys = {k.to_user_string() for k in graph.get_all_asset_keys()}
    assert keys == {
        "aoi_request",
        "aoi_validated",
        "s2_imagery",
        "land_cover",
        "proximity_results",
        "screening_metrics",
        "map_plates",
        "report_draft",
    }
    upstream = {k.to_user_string() for k in graph.get(dg.AssetKey("report_draft")).parent_keys}
    assert {"screening_metrics", "map_plates", "s2_imagery"} <= upstream
    assert defs.resolve_job_def("site_screening") is not None


def test_sensor_registers_partition_and_requests_run(data_root, fixtures_dir):
    from geovision.orchestration.definitions import incoming_aoi_sensor

    incoming = data_root / "incoming"
    incoming.mkdir()
    shutil.copy(fixtures_dir / "request_ameenpur.json", incoming / "demo-ameenpur-001.json")

    with dg.instance_for_test() as instance:
        result = incoming_aoi_sensor(dg.build_sensor_context(instance=instance))
    assert [r.partition_key for r in result.run_requests] == ["demo-ameenpur-001"]
    assert result.run_requests[0].run_key.startswith("demo-ameenpur-001:")
    assert result.dynamic_partitions_requests[0].partition_keys == ["demo-ameenpur-001"]


def test_aoi_request_rejects_mismatched_file_name(data_root, fixtures_dir):
    from geovision.orchestration.definitions import aoi_request

    incoming = data_root / "incoming"
    incoming.mkdir()
    shutil.copy(fixtures_dir / "request_ameenpur.json", incoming / "wrong-name.json")
    with pytest.raises(dg.Failure, match="does not match"):
        aoi_request(dg.build_asset_context(partition_key="wrong-name"))


def test_aoi_request_archives_request(data_root, fixtures_dir):
    from geovision.orchestration.definitions import aoi_request

    incoming = data_root / "incoming"
    incoming.mkdir()
    shutil.copy(fixtures_dir / "request_ameenpur.json", incoming / "demo-ameenpur-001.json")
    req = aoi_request(dg.build_asset_context(partition_key="demo-ameenpur-001"))
    assert req.project_id == "demo-ameenpur-001"
    assert (data_root / "demo-ameenpur-001" / "request.json").exists()
