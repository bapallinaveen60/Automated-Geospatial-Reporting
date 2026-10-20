from pathlib import Path

from geovision.contracts import (
    ChangeSummary,
    ClassShare,
    IndexStats,
    MetricsPayload,
    ProximityResult,
    SiteSummary,
)
from geovision.ingest.admin import parse_address
from geovision.reporting.charts import render_charts
from geovision.reporting.narrative import summary_paragraphs, vegetation_class


def _metrics(**overrides):
    base = {
        "project_id": "t-001",
        "site": SiteSummary(
            area_ha=41.18,
            perimeter_m=2595,
            centroid_lon=78.3185,
            centroid_lat=17.5305,
            analysis_crs="EPSG:32644",
            state="Telangana",
            district="Sangareddy",
            locality="Ilapur",
        ),
        "lulc": [
            ClassShare(code=50, label="Built-up", area_ha=24.8, percent=60.3),
            ClassShare(code=30, label="Grassland", area_ha=9.6, percent=23.3),
        ],
        "indices": {
            "ndvi": IndexStats(mean=0.43, median=0.40, p10=0.15, p90=0.75, valid_fraction=0.97)
        },
        "change": [
            ChangeSummary(
                index="ndvi", threshold=0.15, loss_ha=4.29, gain_ha=16.65, net_change_mean=0.1
            )
        ],
        "proximity": [
            ProximityResult(
                layer="wetlands_water",
                nearest_name=None,
                distance_m=49,
                search_radius_m=2000,
            ),
            ProximityResult(
                layer="protected_areas",
                nearest_name=None,
                distance_m=None,
                search_radius_m=10000,
            ),
        ],
    }
    return MetricsPayload(**{**base, **overrides})


def test_narrative_mentions_location_cover_and_receptors():
    text = " ".join(summary_paragraphs(_metrics()))
    assert "Ilapur, Sangareddy, Telangana" in text
    assert "dominated by built-up (60%)" in text
    assert "fell by more than 0.15 over 4.29 ha" in text
    assert "water body or wetland lies 49 m" in text
    assert "No protected area is mapped within 10.0 km" in text
    assert "No screening rule was triggered." in text


def test_narrative_without_optional_sections():
    text = " ".join(summary_paragraphs(_metrics(lulc=[], indices={}, change=[], proximity=[])))
    assert text.startswith("The site covers 41.18 ha")


def test_vegetation_class_bands():
    assert vegetation_class(0.1).startswith("bare")
    assert vegetation_class(0.7) == "dense vegetation"


def test_parse_address_prefers_state_district():
    loc = parse_address(
        {"state": "Telangana", "state_district": "Sangareddy", "county": "x", "village": "Ilapur"}
    )
    assert (loc.state, loc.district, loc.village_or_town) == ("Telangana", "Sangareddy", "Ilapur")


def test_lulc_chart_is_svg(tmp_path):
    charts = render_charts(_metrics(), tmp_path)
    assert charts[0]["key"] == "lulc"
    svg = Path(charts[0]["path"]).read_text(encoding="utf-8")
    assert svg.lstrip().startswith("<?xml")
    assert render_charts(_metrics(lulc=[]), tmp_path) == []
