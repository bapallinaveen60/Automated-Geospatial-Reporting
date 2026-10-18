from geovision.analysis.rules import Rule, evaluate
from geovision.contracts import MetricsPayload, ProximityResult, SiteSummary
from geovision.modules import load_module


def _payload(pa_distance):
    return MetricsPayload(
        project_id="test-001",
        site=SiteSummary(
            area_ha=40,
            perimeter_m=2600,
            centroid_lon=78.3,
            centroid_lat=17.5,
            analysis_crs="EPSG:32644",
        ),
        proximity=[
            ProximityResult(
                layer="protected_areas",
                nearest_name="X",
                distance_m=pa_distance,
                search_radius_m=10000,
            )
        ],
    )


def test_module_loads_and_rules_parse():
    mod = load_module("site_screening_in")
    assert mod.name == "site_screening_in"
    assert mod.lulc_labels()[95] == "Mangroves"
    assert {"protected_areas", "wetlands_water", "coastline"} <= set(mod.layers)
    assert any(r.id == "pa_within_10km" for r in mod.rules)


def test_pa_rule_triggers_within_10km():
    flags = evaluate(load_module("site_screening_in").rules, _payload(4200).flat())
    pa = next(f for f in flags if f.rule_id == "pa_within_10km")
    assert pa.severity == "critical"
    assert "4,200 m" in pa.message


def test_pa_rule_silent_when_none_found():
    flags = evaluate(load_module("site_screening_in").rules, _payload(None).flat())
    assert not any(f.rule_id.startswith("pa_") for f in flags)


def test_missing_metric_skip_vs_info():
    rules = [
        Rule(id="a", metric="nope", op=">", threshold=1, severity="warning", message="x"),
        Rule(
            id="b",
            metric="nope",
            op=">",
            threshold=1,
            severity="warning",
            message="x",
            when_missing="info",
        ),
    ]
    flags = evaluate(rules, {})
    assert [f.rule_id for f in flags] == ["b"]
    assert flags[0].severity == "info"


def test_flags_sorted_by_severity():
    rules = [
        Rule(id="i", metric="v", op=">", threshold=0, severity="info", message="i"),
        Rule(id="c", metric="v", op=">", threshold=0, severity="critical", message="c"),
    ]
    assert [f.rule_id for f in evaluate(rules, {"v": 1})] == ["c", "i"]
