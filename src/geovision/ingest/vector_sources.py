"""Pluggable vector connectors. Each returns features clipped to a lon/lat bbox in EPSG:4326.

India's authoritative layers (NWIA wetlands, ESZ notifications, CZMP HTL) are rarely
available as open vector services, so the defaults use OpenStreetMap and clients can
supply their own files through ``FileSource``.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import geopandas as gpd
import requests
import shapely

from geovision.contracts.lineage import InputRef

WGS84 = "EPSG:4326"
# Public Overpass instances, tried in order when one is overloaded or unreachable.
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api",
    "https://overpass.private.coffee/api",
    "https://maps.mail.ru/osm/tools/overpass/api",
)


class VectorSource(Protocol):
    key: str

    def fetch(self, bbox: Sequence[float]) -> gpd.GeoDataFrame: ...

    def ref(self) -> InputRef: ...


@dataclass
class FileSource:
    """A local/remote vector file (GPKG, SHP, GeoJSON, GeoParquet), e.g. client-supplied ESZ."""

    key: str
    path: str
    layer: str | None = None
    name_field: str | None = None
    licence: str | None = None

    def fetch(self, bbox: Sequence[float]) -> gpd.GeoDataFrame:
        if Path(self.path).suffix.lower() == ".parquet":
            gdf = gpd.read_parquet(self.path, bbox=tuple(bbox))
        else:
            gdf = gpd.read_file(self.path, layer=self.layer, bbox=tuple(bbox))
        gdf = gdf.to_crs(WGS84) if gdf.crs else gdf.set_crs(WGS84)
        return _normalise(gdf, self.name_field)

    def ref(self) -> InputRef:
        return InputRef(kind="vector_source", id=self.key, href=self.path, licence=self.licence)


@dataclass
class OSMSource:
    """OpenStreetMap features via the Overpass API (osmnx). Licence: ODbL."""

    key: str
    tags: dict[str, Any]
    name_field: str = "name"
    geom_types: tuple[str, ...] = ("Polygon", "MultiPolygon")
    _retrieved: str | None = field(default=None, init=False, repr=False)

    def fetch(self, bbox: Sequence[float]) -> gpd.GeoDataFrame:
        import osmnx as ox

        west, south, east, north = bbox
        last_error: Exception | None = None
        for endpoint in OVERPASS_ENDPOINTS:
            ox.settings.overpass_url = endpoint
            ox.settings.requests_timeout = 90
            try:
                gdf = ox.features.features_from_bbox(
                    bbox=(west, south, east, north), tags=self.tags
                )
                break
            except ox._errors.InsufficientResponseError:
                gdf = gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=WGS84)
                break
            except (requests.RequestException, ox._errors.ResponseStatusCodeError) as e:
                last_error = e  # try the next mirror
        else:
            raise RuntimeError(f"All Overpass endpoints failed: {last_error}") from last_error
        self._retrieved = ox.settings.overpass_url
        gdf = gdf.reset_index()
        gdf = gdf[gdf.geometry.geom_type.isin(self.geom_types)]
        return _normalise(gdf, self.name_field)

    def ref(self) -> InputRef:
        return InputRef(
            kind="vector_source",
            id=self.key,
            href=self._retrieved or OVERPASS_ENDPOINTS[0],
            licence="ODbL 1.0 (© OpenStreetMap contributors)",
            extra={"tags": self.tags},
        )


def _normalise(gdf: gpd.GeoDataFrame, name_field: str | None) -> gpd.GeoDataFrame:
    names = (
        gdf[name_field].astype("string")
        if name_field and name_field in gdf.columns
        else [None] * len(gdf)
    )
    out = gpd.GeoDataFrame({"name": names}, geometry=gdf.geometry.values, crs=gdf.crs or WGS84)
    out = out[~out.geometry.is_empty & out.geometry.notna()]
    out["geometry"] = shapely.make_valid(out.geometry.values)
    return out.reset_index(drop=True)


def build_source(key: str, spec: dict[str, Any]) -> VectorSource:
    """Instantiate a connector from a ``module.yaml`` layer entry."""
    kind = spec.get("source")
    if kind == "osm":
        return OSMSource(
            key=key,
            tags=spec["tags"],
            name_field=spec.get("name_field", "name"),
            geom_types=tuple(spec.get("geom_types", ("Polygon", "MultiPolygon"))),
        )
    if kind == "file":
        return FileSource(
            key=key,
            path=spec["path"],
            layer=spec.get("layer"),
            name_field=spec.get("name_field"),
            licence=spec.get("licence"),
        )
    raise ValueError(f"Unknown vector source type {kind!r} for layer {key!r}")
