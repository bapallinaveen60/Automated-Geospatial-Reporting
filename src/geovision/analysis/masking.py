"""Sentinel-2 L2A cloud masking, DN-to-reflectance conversion and compositing."""

from collections.abc import Sequence

import xarray as xr

# Scene Classification Layer classes treated as unusable:
# 0 no data, 1 saturated/defective, 3 cloud shadow, 8/9 cloud medium/high, 10 thin cirrus.
SCL_INVALID = (0, 1, 3, 8, 9, 10)
# From processing baseline 04.00 (25 Jan 2022) L2A DNs carry a +1000 offset.
BOA_OFFSET_DN = 1000
OFFSET_START_DATE = "2022-01-25"
REFLECTANCE_SCALE = 1e-4


def scl_valid_mask(scl: xr.DataArray) -> xr.DataArray:
    return ~scl.isin(SCL_INVALID)


def _offset_for(date: str, baseline: str | None) -> int:
    if baseline:
        return BOA_OFFSET_DN if baseline >= "04.00" else 0
    return BOA_OFFSET_DN if date >= OFFSET_START_DATE else 0


def to_reflectance(
    ds: xr.Dataset, bands: Sequence[str], baselines: dict[str, str] | None = None
) -> xr.Dataset:
    """Convert DNs to surface reflectance per time slice.

    DN 0 (no data) and non-positive reflectance after the offset become NaN; clipping them
    to 0 instead would push NDVI/MNDWI to exactly ±1.
    """
    baselines = baselines or {}
    dates = [str(d)[:10] for d in ds["time"].values]
    offsets = xr.DataArray(
        [_offset_for(d, baselines.get(d)) for d in dates], coords={"time": ds["time"]}, dims="time"
    )
    out = ds.copy()
    for b in bands:
        dn = ds[b].where(ds[b] != 0)
        refl = (dn - offsets) * REFLECTANCE_SCALE
        out[b] = refl.where(refl > 0)
    return out


def median_composite(ds: xr.Dataset, bands: Sequence[str], scl_band: str = "scl") -> xr.Dataset:
    """Cloud-masked per-pixel median across time."""
    valid = scl_valid_mask(ds[scl_band])
    masked = ds[list(bands)].where(valid)
    return masked.median("time", skipna=True)
