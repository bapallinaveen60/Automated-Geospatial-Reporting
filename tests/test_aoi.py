import pytest
from shapely.geometry import Polygon, mapping

from geovision.ingest.aoi import AOIValidationError, read_aoi, utm_crs_for, validate_aoi


def test_fixture_aoi_area_and_crs(fixtures_dir):
    aoi = validate_aoi(read_aoi(fixtures_dir / "aoi_ameenpur.geojson"))
    assert aoi.utm_crs.to_epsg() == 32644  # Hyderabad region is UTM 44N
    # 0.007° x 0.005° at ~17.5° N ≈ 743 m x 553 m ≈ 41 ha
    assert 38 < aoi.area_ha < 44
    assert aoi.warnings == ()


@pytest.mark.parametrize(
    ("lon", "lat", "epsg"),
    [(72.88, 19.07, 32643), (77.59, 12.97, 32643), (88.36, 22.57, 32645), (-0.1, -10, 32730)],
)
def test_utm_zone(lon, lat, epsg):
    assert utm_crs_for(lon, lat).to_epsg() == epsg


def test_bowtie_is_repaired():
    bowtie = Polygon([(78.0, 17.0), (78.01, 17.01), (78.01, 17.0), (78.0, 17.01), (78.0, 17.0)])
    aoi = validate_aoi(read_aoi(mapping(bowtie)))
    assert aoi.geometry.is_valid
    assert any("repaired" in w for w in aoi.warnings)


def test_outside_india_warns():
    square = Polygon([(2.0, 48.0), (2.01, 48.0), (2.01, 48.01), (2.0, 48.01)])
    aoi = validate_aoi(read_aoi(mapping(square)))
    assert any("outside" in w for w in aoi.warnings)


def test_too_large_rejected():
    big = Polygon([(75, 15), (78, 15), (78, 18), (75, 18)])
    with pytest.raises(AOIValidationError, match="exceeds"):
        validate_aoi(read_aoi(mapping(big)))


def test_buffered_bbox_grows(fixtures_dir):
    aoi = validate_aoi(read_aoi(fixtures_dir / "aoi_ameenpur.geojson"))
    minx, _, _, maxy = aoi.buffered_bbox(10_000)
    assert minx < aoi.bbox[0] - 0.08
    assert maxy > aoi.bbox[3] + 0.08
