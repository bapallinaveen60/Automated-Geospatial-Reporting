"""Two-period change detection on index rasters."""

import numpy as np
import xarray as xr

from geovision.contracts.metrics import ChangeSummary


def index_delta(baseline: xr.DataArray, current: xr.DataArray) -> xr.DataArray:
    return (current - baseline).rename("delta")


def change_summary(
    baseline: np.ndarray | xr.DataArray,
    current: np.ndarray | xr.DataArray,
    index: str,
    threshold: float,
    pixel_area_m2: float,
) -> ChangeSummary:
    """Loss/gain area where |delta| exceeds ``threshold``.

    Pixels missing in either period are ignored.
    """
    delta = np.asarray(current, dtype="float64") - np.asarray(baseline, dtype="float64")
    finite = delta[np.isfinite(delta)]
    to_ha = pixel_area_m2 / 10_000
    return ChangeSummary(
        index=index,
        threshold=threshold,
        loss_ha=float((finite < -threshold).sum() * to_ha),
        gain_ha=float((finite > threshold).sum() * to_ha),
        net_change_mean=float(finite.mean()) if finite.size else None,
    )
