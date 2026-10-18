"""Read, repair and validate an AOI, and pick a metric CRS for area/distance work."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import geopandas as gpd
import shapely
from pyproj import CRS, Transformer
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.geometry.base import BaseGeometry

WGS84 = CRS.from_epsg(4326)
# Loose lon/lat envelope of India; AOIs outside it only produce a warning.
INDIA_BBOX = (68.0, 6.0, 97.5, 37.5)


class AOIValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedAOI:
    geometry: BaseGeometry  # EPSG:4326
    geometry_utm: BaseGeometry
    utm_crs: CRS
    area_ha: float
    perimeter_m: float
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return self.geometry.bounds

    def buffered_utm(self, distance_m: float) -> BaseGeometry:
        return self.geometry_utm.buffer(distance_m)

    def buffered_bbox(self, distance_m: float) -> tuple[float, float, float, float]:
        """Lon/lat bounds of the AOI grown by ``distance_m`` metres."""
        to_wgs = Transformer.from_crs(self.utm_crs, WGS84, always_xy=True).transform
        return shapely.transform(self.buffered_utm(distance_m), to_wgs, interleaved=False).bounds

    def to_gdf(self, utm: bool = False) -> gpd.GeoDataFrame:
        if utm:
            return gpd.GeoDataFrame(geometry=[self.geometry_utm], crs=self.utm_crs)
        return gpd.GeoDataFrame(geometry=[self.geometry], crs=WGS84)


def read_aoi(source: str | Path | dict[str, Any]) -> gpd.GeoDataFrame:
    """Load an AOI from a file (GeoJSON, Shapefile/.zip, GPKG, KML) or a GeoJSON dict."""
    if isinstance(source, dict):
        if source.get("type") == "FeatureCollection":
            gdf = gpd.GeoDataFrame.from_features(source["features"], crs=WGS84)
        elif source.get("type") == "Feature":
            gdf = gpd.GeoDataFrame.from_features([source], crs=WGS84)
        else:
            gdf = gpd.GeoDataFrame(geometry=[shape(source)], crs=WGS84)
    else:
        gdf = gpd.read_file(source)
    if gdf.empty:
        raise AOIValidationError("AOI contains no features")
    if gdf.crs is None:
        gdf = gdf.set_crs(WGS84)
    return gdf.to_crs(WGS84)


def utm_crs_for(lon: float, lat: float) -> CRS:
    zone = int((lon + 180) // 6) + 1
    return CRS.from_epsg((32600 if lat >= 0 else 32700) + zone)


def _polygonal(geom: BaseGeometry) -> BaseGeometry:
    parts = [g for g in shapely.get_parts(geom) if isinstance(g, Polygon) and not g.is_empty]
    if not parts:
        return Polygon()
    return parts[0] if len(parts) == 1 else MultiPolygon(parts)


def validate_aoi(
    gdf: gpd.GeoDataFrame,
    min_area_ha: float = 0.01,
    max_area_ha: float = 50_000.0,
    expected_bbox: tuple[float, float, float, float] | None = INDIA_BBOX,
) -> ValidatedAOI:
    warnings: list[str] = []

    geoms = [g for g in gdf.geometry if g is not None and not g.is_empty]
    if not geoms:
        raise AOIValidationError("AOI has no non-empty geometries")
    invalid = sum(not g.is_valid for g in geoms)
    if invalid:
        warnings.append(f"{invalid} invalid geometr{'y' if invalid == 1 else 'ies'} repaired")
    merged = _polygonal(shapely.union_all([shapely.make_valid(g) for g in geoms]))
    if merged.is_empty:
        raise AOIValidationError("AOI must contain at least one polygon")
    if len(geoms) > 1:
        warnings.append(f"{len(geoms)} features dissolved into one site boundary")

    c = merged.centroid
    utm = utm_crs_for(c.x, c.y)
    minx, _, maxx, _ = merged.bounds
    if utm_crs_for(minx, c.y) != utm_crs_for(maxx, c.y):
        warnings.append("AOI spans more than one UTM zone; areas use the centroid zone")

    to_utm = Transformer.from_crs(WGS84, utm, always_xy=True).transform
    geom_utm = shapely.transform(merged, to_utm, interleaved=False)
    area_ha = geom_utm.area / 10_000
    if area_ha < min_area_ha:
        raise AOIValidationError(f"AOI area {area_ha:.4f} ha is below the {min_area_ha} ha minimum")
    if area_ha > max_area_ha:
        raise AOIValidationError(
            f"AOI area {area_ha:,.0f} ha exceeds the {max_area_ha:,.0f} ha limit"
        )

    if expected_bbox is not None:
        ex = shapely.box(*expected_bbox)
        if not ex.contains(merged):
            warnings.append("AOI lies partly or wholly outside the expected region (India)")

    return ValidatedAOI(
        geometry=merged,
        geometry_utm=geom_utm,
        utm_crs=utm,
        area_ha=area_ha,
        perimeter_m=geom_utm.length,
        warnings=tuple(warnings),
    )
