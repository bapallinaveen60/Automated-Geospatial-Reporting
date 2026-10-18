import numpy as np
import xarray as xr

from geovision.analysis.change import change_summary
from geovision.analysis.indices import index_stats, ndvi, normalized_difference


def test_normalized_difference_numpy():
    out = normalized_difference(np.array([0.5, 0.0, 0.3]), np.array([0.1, 0.0, 0.3]))
    np.testing.assert_allclose(out[0], 0.4 / 0.6)
    assert np.isnan(out[1])
    assert out[2] == 0


def test_ndvi_dataset():
    ds = xr.Dataset({"nir": ("x", [0.4, 0.2]), "red": ("x", [0.1, 0.2])})
    np.testing.assert_allclose(ndvi(ds).values, [0.6, 0.0])


def test_index_stats_ignores_nan():
    s = index_stats(np.array([0.1, 0.2, np.nan, 0.3]))
    assert s.valid_fraction == 0.75
    assert abs(s.mean - 0.2) < 1e-9


def test_index_stats_all_nan():
    s = index_stats(np.full(4, np.nan))
    assert s.mean is None
    assert s.valid_fraction == 0


def test_change_summary_areas():
    base = np.array([[0.8, 0.8], [0.3, np.nan]])
    cur = np.array([[0.2, 0.8], [0.6, 0.5]])
    ch = change_summary(base, cur, "ndvi", threshold=0.15, pixel_area_m2=100)
    assert ch.loss_ha == 0.01  # one 10 m pixel
    assert ch.gain_ha == 0.01
