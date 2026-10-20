import csv

from geovision.validation.compare import compare_site, read_manual_baselines, summarise, within
from geovision.validation.sites import site_requests
from geovision.validation.template import template_rows, write_template


def test_five_sites_with_valid_requests():
    reqs = site_requests()
    assert len(reqs) == 5
    assert len({r.project_id for r in reqs}) == 5
    assert all(r.geometry["type"] == "Polygon" for r in reqs)


def test_tolerances():
    assert within(41.13, 41.18, "site.area_ha")  # 0.12% < 0.5%
    assert not within(40.0, 41.18, "site.area_ha")
    assert within(48.5, 49.0, "proximity.wetlands_water.distance_m")
    assert not within(80.0, 49.0, "proximity.wetlands_water.distance_m")
    assert within(None, None, "proximity.forest.distance_m")  # none found by both
    assert not within(None, 300.0, "proximity.forest.distance_m")
    assert within(60.8, 60.3, "lulc.50.percent")
    assert within(None, None, "unknown.metric") is None


def test_compare_site_treats_missing_lulc_as_zero_and_skips_unmeasured():
    pipeline = {"site.area_ha": 41.18, "lulc.50.percent": 60.3, "proximity.forest.distance_m": None}
    qgis = {"site.area_ha": 41.13, "lulc.50.percent": 60.3, "lulc.95.percent": 0.4}
    manual = {"site.area_ha": "41.2", "proximity.forest.distance_m": ""}
    rows = {r.metric: r for r in compare_site("s", pipeline, qgis, manual)}
    assert rows["lulc.95.percent"].pipeline == 0.0 and rows["lulc.95.percent"].qgis_ok is True
    assert rows["site.area_ha"].manual_ok is True
    assert rows["proximity.forest.distance_m"].manual_ok is True  # 'none' vs None
    assert rows["lulc.50.percent"].manual_ok is None  # analyst has not measured it
    assert summarise(list(rows.values()))["manual"] == {"compared": 2, "passed": 2, "failed": 0}


def test_template_round_trip(tmp_path):
    path = write_template(tmp_path / "baseline.csv")
    assert len(template_rows()) == 5 * 33 + 0 * 1 or len(template_rows()) == 165
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    rows[0]["value"] = "41.2"
    rows[1]["value"] = "none"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    parsed = read_manual_baselines(path)
    sid = rows[0]["site_id"]
    assert parsed[sid] == {rows[0]["metric"]: "41.2", rows[1]["metric"]: ""}
