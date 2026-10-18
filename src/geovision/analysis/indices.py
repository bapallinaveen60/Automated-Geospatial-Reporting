"""Spectral indices and their summary statistics."""

from typing import TypeVar

import numpy as np
import xarray as xr

from geovision.contracts.metrics import IndexStats

ArrayT = TypeVar("ArrayT", np.ndarray, xr.DataArray)


def normalized_difference(a: ArrayT, b: ArrayT) -> ArrayT:
    """(a - b) / (a + b), NaN where the denominator is zero or inputs are missing."""
    with np.errstate(divide="ignore", invalid="ignore"):
        nd = (a - b) / (a + b)
    if isinstance(nd, xr.DataArray):
        return nd.where(np.isfinite(nd))  # type: ignore[return-value]
    return np.where(np.isfinite(nd), nd, np.nan)


def ndvi(ds: xr.Dataset) -> xr.DataArray:
    return normalized_difference(ds["nir"], ds["red"]).rename("ndvi")


def mndwi(ds: xr.Dataset) -> xr.DataArray:
    return normalized_difference(ds["green"], ds["swir16"]).rename("mndwi")


def index_stats(values: np.ndarray | xr.DataArray) -> IndexStats:
    arr = np.asarray(values, dtype="float64").ravel()
    total = arr.size
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return IndexStats(mean=None, median=None, p10=None, p90=None, valid_fraction=0.0)
    p10, p50, p90 = np.percentile(finite, [10, 50, 90])
    return IndexStats(
        mean=float(finite.mean()),
        median=float(p50),
        p10=float(p10),
        p90=float(p90),
        valid_fraction=float(finite.size / total),
    )
