import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import CRS
from shapely.geometry import box

from geovision.analysis.overlay import area_within_ha, class_breakdown, proximity

UTM = CRS.from_epsg(32644)
SITE = box(500000, 2000000, 500100, 2000100)  # 1 ha


def _features(geoms, names):
    return gpd.GeoDataFrame({"name": names}, geometry=geoms, crs=UTM).to_crs(4326)


def test_class_breakdown_percentages():
    arr = np.array([[10, 10, 40, np.nan], [40, 40, 80, 80]])
    shares = class_breakdown(arr, {10: "Tree", 40: "Crop", 80: "Water"}, pixel_area_m2=100)
    assert [s.label for s in shares] == ["Crop", "Tree", "Water"]
    assert abs(sum(s.percent for s in shares) - 100) < 1e-9
    assert shares[0].area_ha == 0.03


def test_proximity_nearest_and_overlap():
    feats = _features(
        [box(500050, 2000050, 500150, 2000150), box(503000, 2000000, 503100, 2000100)],
        ["Overlapping lake", "Far lake"],
    )
    res = proximity(SITE, feats, UTM, "wetlands_water", search_radius_m=2000)
    assert res.nearest_name == "Overlapping lake"
    assert res.distance_m == 0
    assert abs(res.overlap_ha - 0.25) < 1e-3


def test_proximity_outside_radius_is_none():
    feats = _features([box(505000, 2000000, 505100, 2000100)], ["PA"])
    res = proximity(SITE, feats, UTM, "protected_areas", search_radius_m=1000)
    assert res.distance_m is None
    assert res.overlap_ha == 0


def test_area_within_dissolves_overlaps():
    zone = box(500000, 2000000, 500200, 2000200)
    feats = _features(
        [box(500000, 2000000, 500100, 2000100), box(500050, 2000000, 500100, 2000100)], ["a", "b"]
    )
    assert abs(area_within_ha(feats, zone, UTM) - 1.0) < 1e-3


def test_proximity_missing_name_is_none():
    feats = gpd.GeoDataFrame(
        {"name": pd.array([None], dtype="string")},
        geometry=[box(500150, 2000000, 500200, 2000100)],
        crs=UTM,
    ).to_crs(4326)
    res = proximity(SITE, feats, UTM, "wetlands_water", search_radius_m=1000)
    assert res.nearest_name is None
