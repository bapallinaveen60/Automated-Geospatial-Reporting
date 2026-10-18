import numpy as np
import pandas as pd
import xarray as xr

from geovision.analysis.masking import median_composite, to_reflectance


def _cube(dates, red, scl):
    return xr.Dataset(
        {"red": (("time", "x"), np.array(red, float)), "scl": (("time", "x"), np.array(scl))},
        coords={"time": pd.to_datetime(dates), "x": [0, 1]},
    )


def test_offset_applied_by_baseline_and_date():
    ds = _cube(["2021-06-01", "2023-06-01"], [[1500, 0], [2500, 2500]], [[4, 4], [4, 4]])
    out = to_reflectance(ds, ["red"], {"2023-06-01": "05.09"})
    np.testing.assert_allclose(out["red"].values[0, 0], 0.15)  # pre-2022: no offset
    assert np.isnan(out["red"].values[0, 1])  # DN 0 = no data
    np.testing.assert_allclose(out["red"].values[1, 0], 0.15)  # 2500 - 1000 offset


def test_median_composite_masks_clouds():
    ds = _cube(
        ["2023-01-01", "2023-01-06", "2023-01-11"],
        [[0.1, 0.9], [0.2, 0.9], [0.9, 0.3]],
        [[4, 9], [4, 9], [8, 4]],
    )
    comp = median_composite(ds, ["red"])
    np.testing.assert_allclose(comp["red"].values, [0.15, 0.3])
