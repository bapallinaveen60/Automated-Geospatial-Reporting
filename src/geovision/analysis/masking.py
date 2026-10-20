"""Sentinel-2 L2A cloud masking, DN-to-reflectance conversion and compositing."""

from collections.abc import Sequence

import xarray as xr

# Scene Classification Layer classes treated as unusable:
# 0 no data, 1 saturated/defective, 3 cloud shadow, 8/9 cloud medium/high, 10 thin cirrus.
SCL_INVALID = (0, 1, 3, 8, 9, 10)
# From processing baseline 04.00 (25 Jan 2022) L2A DNs carry a +1000 offset, unless the
# catalogue already removed it (see geovision.ingest.stac.dn_offsets).
BOA_OFFSET_DN = 1000
OFFSET_START_DATE = "2022-01-25"
REFLECTANCE_SCALE = 1e-4


def scl_valid_mask(scl: xr.DataArray) -> xr.DataArray:
    return ~scl.isin(SCL_INVALID)


def to_reflectance(
    ds: xr.Dataset, bands: Sequence[str], offsets: dict[str, int] | None = None
) -> xr.Dataset:
    """Convert DNs to surface reflectance per time slice.

    ``offsets`` maps acquisition date (YYYY-MM-DD) to the DN offset to subtract; dates not
    listed fall back to the processing-baseline start date. DN 0 (no data) and non-positive
    reflectance become NaN; clipping them to 0 instead would push NDVI/MNDWI to exactly ±1.
    """
    offsets = offsets or {}
    dates = [str(d)[:10] for d in ds["time"].values]
    per_time = [offsets.get(d, BOA_OFFSET_DN if d >= OFFSET_START_DATE else 0) for d in dates]
    offset_da = xr.DataArray(per_time, coords={"time": ds["time"]}, dims="time")
    out = ds.copy()
    for b in bands:
        dn = ds[b].where(ds[b] != 0)
        refl = (dn - offset_da) * REFLECTANCE_SCALE
        out[b] = refl.where(refl > 0)
    return out


def median_composite(ds: xr.Dataset, bands: Sequence[str], scl_band: str = "scl") -> xr.Dataset:
    """Cloud-masked per-pixel median across time."""
    valid = scl_valid_mask(ds[scl_band])
    masked = ds[list(bands)].where(valid)
    return masked.median("time", skipna=True)
