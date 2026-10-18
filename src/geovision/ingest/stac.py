"""Sentinel-2 discovery and lazy windowed loading via STAC + odc-stac (COG range requests)."""

from collections.abc import Sequence

import odc.stac
import pystac
import pystac_client
import xarray as xr

from geovision.contracts.lineage import InputRef
from geovision.core.config import get_settings

S2_COLLECTION = "sentinel-2-l2a"
# Earth Search v1 common band names.
S2_BANDS = ("red", "green", "nir", "swir16", "scl")


def search_s2(
    bbox: Sequence[float],
    datetime: str,
    max_cloud: float = 20.0,
    collection: str = S2_COLLECTION,
    stac_url: str | None = None,
    max_items: int = 200,
) -> pystac.ItemCollection:
    catalog = pystac_client.Client.open(stac_url or get_settings().stac_url)
    search = catalog.search(
        collections=[collection],
        bbox=list(bbox),
        datetime=datetime,
        query={"eo:cloud_cover": {"lt": max_cloud}},
        max_items=max_items,
    )
    return search.item_collection()


def load_s2(
    items: pystac.ItemCollection,
    bbox: Sequence[float],
    crs: str,
    resolution: float = 10,
    bands: Sequence[str] = S2_BANDS,
    chunk: int = 2048,
) -> xr.Dataset:
    """Lazy Dask-backed cube, one time slice per solar day, clipped to ``bbox``."""
    return odc.stac.load(
        items,
        bands=list(bands),
        bbox=(bbox[0], bbox[1], bbox[2], bbox[3]),
        crs=crs,
        resolution=resolution,
        groupby="solar_day",
        chunks={"x": chunk, "y": chunk},
    )


def processing_baselines(items: pystac.ItemCollection) -> dict[str, str]:
    """Map acquisition date (YYYY-MM-DD) to the S2 processing baseline, used for DN offsets."""
    out: dict[str, str] = {}
    for it in items:
        if it.datetime is not None:
            baseline = it.properties.get("s2:processing_baseline", "")
            out[it.datetime.date().isoformat()] = str(baseline)
    return out


def item_refs(items: pystac.ItemCollection) -> list[InputRef]:
    return [
        InputRef(
            kind="stac_item",
            id=it.id,
            href=it.get_self_href(),
            collection=it.collection_id,
            acquired=it.datetime,
            licence="Copernicus Sentinel data (free, full and open)",
            extra={"eo:cloud_cover": it.properties.get("eo:cloud_cover")},
        )
        for it in items
    ]
