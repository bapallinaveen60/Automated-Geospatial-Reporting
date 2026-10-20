# Manual validation protocol (Phase 7)

**Who:** a GIS analyst or EIA professional who has *not* worked on the GeoVision code.
**Goal:** produce independent, hand-made measurements for five sites so we can show clients the automated reports match professional manual work.
**Effort:** about 1.5–2 hours per site, 8–10 hours in total.
**Output:** a completed `validation/baselines/manual_baseline.csv`.

Please work from the source datasets as described below. Do **not** open the pipeline's outputs (`data/runs/…`) or reports until you have finished: the value of this exercise is that your numbers are independent.

---

## 0. Setup

- QGIS 3.44 LTR (any 3.34+ is fine). Plugins: **QuickOSM**.
- Project → Properties → **General → Measurements**: Ellipsoid **WGS 84**, distance units **metres**, area units **hectares**.
- One QGIS project per site. Set the project CRS to the site's UTM zone:

| Site ID | Location | Boundary file | UTM CRS | WorldCover tile |
|---|---|---|---|---|
| `val-ameenpur` | Ameenpur, Sangareddy, TG | `validation/boundaries/val-ameenpur.geojson` | EPSG:32644 | N15E078 |
| `val-vashi-creek` | Vashi, Navi Mumbai, MH | `validation/boundaries/val-vashi-creek.geojson` | EPSG:32643 | N18E072 |
| `val-bannerghatta` | Kalkere, Bengaluru Urban, KA | `validation/boundaries/val-bannerghatta.geojson` | EPSG:32643 | N12E075 |
| `val-deepor-beel` | Deepor Beel, Guwahati, AS | `validation/boundaries/val-deepor-beel.geojson` | EPSG:32646 | N24E090 |
| `val-ludhiana-farm` | Mohi, Ludhiana, PB | `validation/boundaries/val-ludhiana-farm.geojson` | EPSG:32643 | N30E075 |

Comparison periods for every site: **baseline 1 Oct 2021 – 31 Mar 2022**, **current 1 Oct 2025 – 31 Mar 2026**.

In the CSV, fill `value`, `analyst` (your name), `date`, and in `method_notes` anything that deviated from this protocol (scene ID used, tool, difficulties). Leave a value blank only if you could not measure it.

---

## 1. Site area and perimeter

1. Load the boundary GeoJSON.
2. Open the attribute table → Field Calculator → `$area / 10000` (ha) and `$perimeter` (m). These use the WGS 84 ellipsoid you set in step 0.
3. Record `site.area_ha` and `site.perimeter_m`.

## 2. Land cover (ESA WorldCover 2021)

1. Download the tile for the site from ESA:
   `https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_<TILE>_Map.tif`
   (replace `<TILE>` with the tile in the table above).
2. Processing → **Zonal histogram** (raster = tile, vector = site boundary).
3. For each class, share = class count ÷ sum of all class counts × 100.
4. Record every `lulc.<code>.percent` row; enter **0** for classes not present.

Class codes: 10 Tree cover, 20 Shrubland, 30 Grassland, 40 Cropland, 50 Built-up, 60 Bare/sparse, 70 Snow/ice, 80 Permanent water, 90 Herbaceous wetland, 95 Mangroves, 100 Moss/lichen.

## 3. Vegetation and water indices (one current-period scene)

1. In the [Copernicus Browser](https://browser.dataspace.copernicus.eu), search Sentinel-2 **L2A** over the site within the **current** period. Choose the clearest date with no cloud or shadow over the site, and note its product ID in `method_notes`.
2. Download bands **B03, B04, B08, B11** and **SCL**.
3. Convert to reflectance. For products with processing baseline **04.00 or later** (all products from 25 Jan 2022), reflectance = (DN − 1000) / 10000. For earlier products, reflectance = DN / 10000. *This offset matters: forgetting it shifts NDVI noticeably.*
4. Raster Calculator:
   - NDVI = (B08 − B04) / (B08 + B04)
   - MNDWI = (B03 − B11) / (B03 + B11), with B11 resampled to 10 m.
   Mask out SCL classes 0, 1, 3, 8, 9, 10 (no data, saturated, cloud shadow, clouds, cirrus).
5. Processing → **Zonal statistics** (median) with the site boundary. Record `indices.ndvi.median` and `indices.mndwi.median`.

## 4. Vegetation change (baseline scene vs current scene)

1. Repeat step 3 for one clear **baseline**-period scene and compute its NDVI.
2. Raster Calculator: ΔNDVI = NDVI_current − NDVI_baseline.
3. Reclassify: ΔNDVI < −0.15 → 1 (loss), ΔNDVI > 0.15 → 2 (gain), else 0. Run a **Zonal histogram** with the site boundary.
4. Area = pixel count × 0.01 ha (10 m pixels). Record `change.ndvi.loss_ha` and `change.ndvi.gain_ha`.
5. In `method_notes`, say whether the loss areas correspond to visible real change (construction, clearing, harvest) in Google Earth / Esri historical imagery.

## 5. Sensitive receptors

Use **independent sources** where you can, not only OpenStreetMap: Bhuvan (NWIA wetlands, forest cover), PARIVESH / state notifications (ESZ, protected areas), Survey of India, CZMP maps (HTL / CRZ). OSM via QuickOSM is acceptable as a fallback; say which source you used in `method_notes`.

For each receptor type, measure the **shortest distance from the site boundary to the nearest feature** (Processing → *Shortest line between features*, then `$length`; or the Measure tool with ellipsoidal mode):

| Metric | What | Search radius |
|---|---|---|
| `proximity.protected_areas.distance_m` | National park, wildlife sanctuary, conservation/community reserve, notified ESZ | 10 km |
| `proximity.wetlands_water.distance_m` | Lake, pond, river, wetland | 2 km |
| `proximity.forest.distance_m` | Recorded / reserved forest, dense tree cover mapped as forest | 1 km |
| `proximity.coastline.distance_m` | Coastline / High Tide Line | 5 km |

Enter `none` if there is no such feature within the radius, and `0` if it touches or overlaps the site. For each `…overlap_ha` row, record the area of that receptor inside the site (Processing → *Intersection*, then `$area / 10000`), or 0.

## 6. Professional judgement on flags

For each `flag.<rule>` row, answer **yes** or **no**: *based on your knowledge and the authoritative sources, should a screening report for this site raise this item?* Explain borderline cases in `method_notes`. This is the most important part for clients, because it tests whether the automated findings are *right*, not just whether the arithmetic is.

---

## When you are done

Send back `validation/baselines/manual_baseline.csv`. The engineering team runs:

```bash
uv run python scripts/validation_report.py
```

That produces `validation/REPORT.md`, comparing your values with the pipeline line by line against the tolerances it lists. Any failures are investigated, fixed, and re-run before the pipeline is used for client work.
