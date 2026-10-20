from datetime import datetime

import numpy as np
import pandas as pd
import pystac
import xarray as xr

from geovision.analysis.masking import median_composite, to_reflectance
from geovision.ingest.stac import dn_offsets, item_dn_offset, publicly_readable


def _cube(dates, red, scl):
    return xr.Dataset(
        {"red": (("time", "x"), np.array(red, float)), "scl": (("time", "x"), np.array(scl))},
        coords={"time": pd.to_datetime(dates), "x": [0, 1]},
    )


def test_offset_applied_by_baseline_and_date():
    ds = _cube(["2021-06-01", "2023-06-01"], [[1500, 0], [2500, 2500]], [[4, 4], [4, 4]])
    out = to_reflectance(ds, ["red"], {"2023-06-01": 1000})
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


def test_non_positive_reflectance_is_masked_not_clipped():
    ds = _cube(["2023-06-01"], [[900, 1500]], [[4, 4]])
    out = to_reflectance(ds, ["red"], {"2023-06-01": 1000})
    assert np.isnan(out["red"].values[0, 0])  # 900 - 1000 < 0


def test_already_harmonised_dates_are_not_offset_twice():
    ds = _cube(["2025-12-13"], [[1500, 440]], [[4, 5]])
    out = to_reflectance(ds, ["red"], {"2025-12-13": 0})
    np.testing.assert_allclose(out["red"].values[0], [0.15, 0.044])


def _item(item_id, date, baseline, applied=None):
    props = {"s2:processing_baseline": baseline}
    if applied is not None:
        props["earthsearch:boa_offset_applied"] = applied
    return pystac.Item(item_id, None, None, datetime.fromisoformat(date), props)


def test_item_dn_offset_respects_catalogue_flag():
    assert item_dn_offset(_item("a", "2025-12-13", "05.11", applied=True)) == 0
    assert item_dn_offset(_item("b", "2022-02-02", "04.00", applied=False)) == 1000
    assert item_dn_offset(_item("c", "2021-12-19", "03.01")) == 0


def test_dn_offsets_flags_mixed_dates():
    items = pystac.ItemCollection(
        [
            _item("a", "2022-02-02", "04.00", applied=True),
            _item("b", "2022-02-02", "04.00", applied=False),
            _item("c", "2025-12-13", "05.11", applied=True),
        ]
    )
    offsets, mixed = dn_offsets(items)
    assert offsets == {"2025-12-13": 0}
    assert mixed == {"2022-02-02"}


def test_requester_pays_items_are_not_public():
    item = _item("a", "2021-11-27", "03.01")
    for band in ("red", "green", "nir", "swir16", "scl"):
        item.add_asset(band, pystac.Asset(f"https://sentinel-cogs.example/{band}.tif"))
    assert publicly_readable(item)
    item.assets["scl"] = pystac.Asset("s3://sentinel-s2-l2a/tiles/46/R/CP/SCL.jp2")
    assert not publicly_readable(item)
