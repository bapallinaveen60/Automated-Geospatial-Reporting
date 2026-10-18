"""Thematic rasters (land cover, surface water, DEM) from Microsoft Planetary Computer STAC."""

from collections.abc import Sequence
from dataclasses import dataclass

import odc.stac
import planetary_computer
import pystac_client
import xarray as xr

from geovision.contracts.lineage import InputRef
from geovision.core.config import get_settings


@dataclass(frozen=True)
class ThematicSource:
    key: str
    collection: str
    asset: str
    resolution: float
    licence: str


ESA_WORLDCOVER = ThematicSource("worldcover", "esa-worldcover", "map", 10, "CC BY 4.0 (ESA)")
JRC_GSW_OCCURRENCE = ThematicSource(
    "water_occurrence", "jrc-gsw", "occurrence", 30, "Copernicus/JRC, free and open"
)
COP_DEM = ThematicSource("dem", "cop-dem-glo-30", "data", 30, "Copernicus DEM licence (free)")

SOURCES = {s.key: s for s in (ESA_WORLDCOVER, JRC_GSW_OCCURRENCE, COP_DEM)}


def load_thematic(
    source: ThematicSource,
    bbox: Sequence[float],
    crs: str,
    resolution: float | None = None,
    stac_url: str | None = None,
) -> tuple[xr.DataArray, list[InputRef]]:
    catalog = pystac_client.Client.open(
        stac_url or get_settings().pc_stac_url, modifier=planetary_computer.sign_inplace
    )
    items = catalog.search(collections=[source.collection], bbox=list(bbox)).item_collection()
    if not items:
        raise LookupError(f"No {source.collection} items intersect {bbox}")
    ds = odc.stac.load(
        items,
        bands=[source.asset],
        bbox=(bbox[0], bbox[1], bbox[2], bbox[3]),
        crs=crs,
        resolution=resolution or source.resolution,
        resampling="nearest",
    )
    # Take the most recent product where several versions/years overlap.
    da = ds[source.asset].isel(time=-1) if "time" in ds.dims else ds[source.asset]
    refs = [
        InputRef(
            kind="raster_source",
            id=it.id,
            collection=source.collection,
            acquired=it.datetime,
            licence=source.licence,
        )
        for it in items
    ]
    return da, refs
