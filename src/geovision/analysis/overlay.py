"""Raster/vector overlays: masking to the site, class breakdowns, proximity and overlap."""

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import xarray as xr
from pyproj import CRS
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

from geovision.contracts.metrics import ClassShare, ProximityResult


def pixel_area_m2(da: xr.DataArray) -> float:
    dx = float(abs(da["x"].values[1] - da["x"].values[0]))
    dy = float(abs(da["y"].values[1] - da["y"].values[0]))
    return dx * dy


def mask_to_geometry(da: xr.DataArray, geom: BaseGeometry, crs: CRS | str) -> xr.DataArray:
    """Float copy of ``da`` with NaN outside ``geom`` (pixel-centre rule)."""
    import rioxarray  # noqa: F401  (registers the .rio accessor)

    return (
        da.astype("float32")
        .rio.write_crs(crs)
        .rio.write_nodata(np.nan)
        .rio.clip([mapping(geom)], all_touched=False, drop=False)
    )


def class_breakdown(
    values: np.ndarray | xr.DataArray,
    labels: dict[int, str],
    pixel_area_m2: float,
) -> list[ClassShare]:
    arr = np.asarray(values, dtype="float64").ravel()
    arr = arr[np.isfinite(arr)].astype("int64")
    if arr.size == 0:
        return []
    codes, counts = np.unique(arr, return_counts=True)
    total = counts.sum()
    shares = [
        ClassShare(
            code=int(code),
            label=labels.get(int(code), f"Class {code}"),
            area_ha=float(n * pixel_area_m2 / 10_000),
            percent=float(100 * n / total),
        )
        for code, n in zip(codes, counts, strict=True)
    ]
    return sorted(shares, key=lambda s: s.percent, reverse=True)


def proximity(
    site_utm: BaseGeometry,
    features: gpd.GeoDataFrame,
    utm_crs: CRS,
    layer: str,
    search_radius_m: float,
) -> ProximityResult:
    """Nearest feature to the site boundary and the area of features overlapping the site."""
    if features.empty:
        return ProximityResult(
            layer=layer, nearest_name=None, distance_m=None, search_radius_m=search_radius_m
        )
    f = features.to_crs(utm_crs)
    dist = f.distance(site_utm)
    i = int(dist.values.argmin())
    nearest = float(dist.iloc[i])
    if nearest > search_radius_m:
        return ProximityResult(
            layer=layer, nearest_name=None, distance_m=None, search_radius_m=search_radius_m
        )
    overlap = shapely.intersection(site_utm, shapely.union_all(f.geometry.values)).area
    name = f["name"].iloc[i] if "name" in f.columns else None
    if name is not None and pd.isna(name):
        name = None
    return ProximityResult(
        layer=layer,
        nearest_name=None if name is None else str(name),
        distance_m=nearest,
        overlap_ha=float(overlap / 10_000),
        search_radius_m=search_radius_m,
    )


def area_within_ha(features: gpd.GeoDataFrame, zone_utm: BaseGeometry, utm_crs: CRS) -> float:
    """Area of (dissolved) features inside a zone, e.g. wetlands within the site's buffer."""
    if features.empty:
        return 0.0
    merged = shapely.union_all(features.to_crs(utm_crs).geometry.values)
    return float(shapely.intersection(merged, zone_utm).area / 10_000)
