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


def publicly_readable(item: pystac.Item, bands: Sequence[str] = S2_BANDS) -> bool:
    """True if every needed band is an anonymous HTTPS COG.

    A few Earth Search items still point at the requester-pays ``s3://sentinel-s2-l2a`` JP2
    archive, which needs paid AWS credentials.
    """
    return all(b in item.assets and item.assets[b].href.startswith("https://") for b in bands)


def item_dn_offset(item: pystac.Item) -> int:
    """DN offset still present in an item's pixel values.

    Baseline ≥ 04.00 products carry +1000, but Earth Search v1 removes it during COG
    conversion when ``earthsearch:boa_offset_applied`` is true. Subtracting it twice biases
    reflectance by -0.1 and inflates NDVI.
    """
    if item.properties.get("earthsearch:boa_offset_applied"):
        return 0
    baseline = str(item.properties.get("s2:processing_baseline", ""))
    if baseline:
        return 1000 if baseline >= "04.00" else 0
    return 1000 if item.datetime and item.datetime.date().isoformat() >= "2022-01-25" else 0


def dn_offsets(items: pystac.ItemCollection) -> tuple[dict[str, int], set[str]]:
    """Per-date DN offsets (scenes are merged per solar day) and dates whose scenes disagree."""
    by_date: dict[str, set[int]] = {}
    for it in items:
        if it.datetime is not None:
            by_date.setdefault(it.datetime.date().isoformat(), set()).add(item_dn_offset(it))
    offsets = {d: next(iter(v)) for d, v in by_date.items() if len(v) == 1}
    return offsets, {d for d, v in by_date.items() if len(v) > 1}


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
