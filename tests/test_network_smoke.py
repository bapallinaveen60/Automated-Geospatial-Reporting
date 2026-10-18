"""Live endpoint checks, deselected by default. Run with:  uv run pytest -m network"""

import pytest

from geovision.ingest.aoi import read_aoi, validate_aoi

pytestmark = pytest.mark.network


def test_stac_search_finds_sentinel2(fixtures_dir):
    from geovision.ingest.stac import search_s2

    aoi = validate_aoi(read_aoi(fixtures_dir / "aoi_ameenpur.geojson"))
    items = search_s2(aoi.bbox, "2024-11-01/2024-12-31", max_cloud=30)
    assert len(items) > 0


def test_osm_water_near_ameenpur(fixtures_dir):
    from geovision.ingest.vector_sources import OSMSource

    aoi = validate_aoi(read_aoi(fixtures_dir / "aoi_ameenpur.geojson"))
    src = OSMSource("wetlands_water", {"natural": ["water", "wetland"]})
    assert len(src.fetch(aoi.buffered_bbox(2000))) > 0
