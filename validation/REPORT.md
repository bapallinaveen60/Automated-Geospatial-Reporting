# Phase 7 validation report

Generated 2026-10-20 13:26 UTC by `scripts/validation_report.py`. Do not edit by hand.

## Summary

| Check | Compared | Passed | Failed |
|---|---:|---:|---:|
| Pipeline vs automated QGIS cross-check | 98 | 98 | 0 |
| Pipeline vs manual analyst baseline | 0 | 0 | 0 |
| Analyst agrees with pipeline flags | 0 | 0 | 0 |

**Manual baselines are pending.** The pipeline is not yet validated for client use. The analyst follows `validation/MANUAL_PROTOCOL.md` and fills in `validation/baselines/manual_baseline.csv`; then re-run this script.

## What each check proves

- **Automated QGIS cross-check** recomputes every metric from the pipeline's own saved inputs with QGIS algorithms (ellipsoidal area/length, zonal histogram, zonal statistics, reclassify). It catches computation errors (projection, pixel inclusion, unit, masking bugs). It cannot catch wrong or incomplete *input* data.
- **Manual baseline** is an analyst's independent workflow in QGIS Desktop from the source datasets, plus their judgement on whether each flag is right for the site. It is the evidence that the reports are fit for client use.

## Tolerances

| Metric | Absolute | Relative | Rationale |
|---|---:|---:|---|
| `site.area_ha` | 0 | 0.5% | 0.5%: planar UTM vs ellipsoidal area |
| `site.perimeter_m` | 0 | 0.5% | 0.5%: planar UTM vs ellipsoidal length |
| `lulc.*.percent` | 1 | 0.0% | 1 percentage point of site area |
| `indices.ndvi.median` | 0.05 | 0.0% | 0.05 NDVI: single-scene manual vs median composite |
| `indices.mndwi.median` | 0.05 | 0.0% | 0.05 MNDWI: single-scene manual vs median composite |
| `change.ndvi.loss_ha` | 0.5 | 25.0% | 0.5 ha or 25%: two-scene manual vs composites |
| `change.ndvi.gain_ha` | 0.5 | 25.0% | 0.5 ha or 25%: two-scene manual vs composites |
| `proximity.*.distance_m` | 15 | 0.0% | 15 m: one to two 10 m pixels |
| `proximity.*.overlap_ha` | 0.05 | 5.0% | 0.05 ha or 5% |

## Results by site

### Ameenpur urban fringe, Sangareddy, Telangana (`val-ameenpur`)

*Purpose:* Peri-urban land cover mix; lake 50 m away (wetland buffer rule)

| Metric | Pipeline | QGIS cross-check | | Manual baseline | | Tolerance |
|---|---:|---:|:-:|---:|:-:|---|
| Site area (ha) | 41.18 | 41.13 | ✅ | pending | · | 0.5%: planar UTM vs ellipsoidal area |
| Perimeter (m) | 2,595 | 2,593 | ✅ | pending | · | 0.5%: planar UTM vs ellipsoidal length |
| Land cover: Tree cover (%) | 2.87 | 2.87 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Grassland (%) | 23.32 | 23.32 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Cropland (%) | 10.59 | 10.59 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Built-up (%) | 60.30 | 60.30 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Bare / sparse (%) | 2.92 | 2.92 | ✅ | pending | · | 1 percentage point of site area |
| MNDWI median | -0.298 | -0.298 | ✅ | pending | · | 0.05 MNDWI: single-scene manual vs median composite |
| NDVI median | 0.222 | 0.222 | ✅ | pending | · | 0.05 NDVI: single-scene manual vs median composite |
| Vegetation gain (ha) | 3.32 | 3.32 | ✅ | pending | · | 0.5 ha or 25%: two-scene manual vs composites |
| Vegetation loss (ha) | 3.34 | 3.34 | ✅ | pending | · | 0.5 ha or 25%: two-scene manual vs composites |
| Nearest coastline, distance (m) | none | none | ✅ | pending | · | 15 m: one to two 10 m pixels |
| Nearest coastline, overlap (ha) | 0.00 | 0.00 | ✅ | pending | · | 0.05 ha or 5% |
| Nearest forest, distance (m) | none | none | ✅ | pending | · | 15 m: one to two 10 m pixels |
| Nearest forest, overlap (ha) | 0.00 | 0.00 | ✅ | pending | · | 0.05 ha or 5% |
| Nearest protected area, distance (m) | none | none | ✅ | pending | · | 15 m: one to two 10 m pixels |
| Nearest protected area, overlap (ha) | 0.00 | 0.00 | ✅ | pending | · | 0.05 ha or 5% |
| Nearest water / wetland, distance (m) | 48.52 | 48.49 | ✅ | pending | · | 15 m: one to two 10 m pixels |
| Nearest water / wetland, overlap (ha) | 0.00 | 0.00 | ✅ | pending | · | 0.05 ha or 5% |

**Flags raised by the pipeline:** `wetland_within_buffer`, `vegetation_loss`

### Thane Creek edge, Vashi, Navi Mumbai, Maharashtra (`val-vashi-creek`)

*Purpose:* Coastal mangroves and tidal creek (CRZ and mangrove rules)

| Metric | Pipeline | QGIS cross-check | | Manual baseline | | Tolerance |
|---|---:|---:|:-:|---:|:-:|---|
| Site area (ha) | 40.79 | 40.78 | ✅ | pending | · | 0.5%: planar UTM vs ellipsoidal area |
| Perimeter (m) | 2,581 | 2,580 | ✅ | pending | · | 0.5%: planar UTM vs ellipsoidal length |
| Land cover: Tree cover (%) | 9.74 | 9.74 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Grassland (%) | 1.46 | 1.46 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Cropland (%) | 5.10 | 5.10 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Built-up (%) | 11.52 | 11.52 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Bare / sparse (%) | 0.02 | 0.02 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Permanent water (%) | 6.37 | 6.37 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Mangroves (%) | 65.77 | 65.77 | ✅ | pending | · | 1 percentage point of site area |
| MNDWI median | -0.356 | -0.356 | ✅ | pending | · | 0.05 MNDWI: single-scene manual vs median composite |
| NDVI median | 0.536 | 0.536 | ✅ | pending | · | 0.05 NDVI: single-scene manual vs median composite |
| Vegetation gain (ha) | 4.10 | 4.10 | ✅ | pending | · | 0.5 ha or 25%: two-scene manual vs composites |
| Vegetation loss (ha) | 0.85 | 0.85 | ✅ | pending | · | 0.5 ha or 25%: two-scene manual vs composites |
| Nearest coastline, distance (m) | 0.00 | 0.00 | ✅ | pending | · | 15 m: one to two 10 m pixels |
| Nearest coastline, overlap (ha) | 0.00 | 0.00 | ✅ | pending | · | 0.05 ha or 5% |
| Nearest forest, distance (m) | none | none | ✅ | pending | · | 15 m: one to two 10 m pixels |
| Nearest forest, overlap (ha) | 0.00 | 0.00 | ✅ | pending | · | 0.05 ha or 5% |
| Nearest protected area, distance (m) | 749 | 748 | ✅ | pending | · | 15 m: one to two 10 m pixels |
| Nearest protected area, overlap (ha) | 0.00 | 0.00 | ✅ | pending | · | 0.05 ha or 5% |
| Nearest water / wetland, distance (m) | 0.00 | 0.00 | ✅ | pending | · | 15 m: one to two 10 m pixels |
| Nearest water / wetland, overlap (ha) | 26.43 | 26.42 | ✅ | pending | · | 0.05 ha or 5% |

**Flags raised by the pipeline:** `pa_within_10km`, `wetland_overlap`, `coast_crz`, `mangrove_present`, `wetland_within_buffer`, `water_lulc_share`, `vegetation_loss`

### Kalkere, north of Bannerghatta NP, Bengaluru Urban, Karnataka (`val-bannerghatta`)

*Purpose:* Protected area within 10 km (EIA General Condition)

| Metric | Pipeline | QGIS cross-check | | Manual baseline | | Tolerance |
|---|---:|---:|:-:|---:|:-:|---|
| Site area (ha) | 42.08 | 42.03 | ✅ | pending | · | 0.5%: planar UTM vs ellipsoidal area |
| Perimeter (m) | 2,628 | 2,626 | ✅ | pending | · | 0.5%: planar UTM vs ellipsoidal length |
| Land cover: Tree cover (%) | 50.04 | 50.04 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Shrubland (%) | 6.41 | 6.41 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Grassland (%) | 3.25 | 3.25 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Cropland (%) | 6.87 | 6.87 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Built-up (%) | 31.53 | 31.53 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Bare / sparse (%) | 0.12 | 0.12 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Permanent water (%) | 1.78 | 1.78 | ✅ | pending | · | 1 percentage point of site area |
| MNDWI median | -0.502 | -0.502 | ✅ | pending | · | 0.05 MNDWI: single-scene manual vs median composite |
| NDVI median | 0.449 | 0.449 | ✅ | pending | · | 0.05 NDVI: single-scene manual vs median composite |
| Vegetation gain (ha) | 1.29 | 1.29 | ✅ | pending | · | 0.5 ha or 25%: two-scene manual vs composites |
| Vegetation loss (ha) | 3.74 | 3.74 | ✅ | pending | · | 0.5 ha or 25%: two-scene manual vs composites |
| Nearest coastline, distance (m) | none | none | ✅ | pending | · | 15 m: one to two 10 m pixels |
| Nearest coastline, overlap (ha) | 0.00 | 0.00 | ✅ | pending | · | 0.05 ha or 5% |
| Nearest forest, distance (m) | 2.32 | 2.32 | ✅ | pending | · | 15 m: one to two 10 m pixels |
| Nearest forest, overlap (ha) | 0.00 | 0.00 | ✅ | pending | · | 0.05 ha or 5% |
| Nearest protected area, distance (m) | 1,169 | 1,168 | ✅ | pending | · | 15 m: one to two 10 m pixels |
| Nearest protected area, overlap (ha) | 0.00 | 0.00 | ✅ | pending | · | 0.05 ha or 5% |
| Nearest water / wetland, distance (m) | 0.00 | 0.00 | ✅ | pending | · | 15 m: one to two 10 m pixels |
| Nearest water / wetland, overlap (ha) | 1.40 | 1.40 | ✅ | pending | · | 0.05 ha or 5% |

**Flags raised by the pipeline:** `pa_within_10km`, `wetland_overlap`, `wetland_within_buffer`, `forest_adjacent`, `vegetation_loss`

### North shore of Deepor Beel (Ramsar site), Guwahati, Assam (`val-deepor-beel`)

*Purpose:* Large wetland and seasonal water (wetland and water-share rules, MNDWI)

| Metric | Pipeline | QGIS cross-check | | Manual baseline | | Tolerance |
|---|---:|---:|:-:|---:|:-:|---|
| Site area (ha) | 38.77 | 38.78 | ✅ | pending | · | 0.5%: planar UTM vs ellipsoidal area |
| Perimeter (m) | 2,508 | 2,508 | ✅ | pending | · | 0.5%: planar UTM vs ellipsoidal length |
| Land cover: Tree cover (%) | 16.14 | 16.14 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Grassland (%) | 3.68 | 3.68 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Cropland (%) | 71.17 | 71.17 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Herbaceous wetland (%) | 9.01 | 9.01 | ✅ | pending | · | 1 percentage point of site area |
| MNDWI median | -0.411 | -0.411 | ✅ | pending | · | 0.05 MNDWI: single-scene manual vs median composite |
| NDVI median | 0.503 | 0.503 | ✅ | pending | · | 0.05 NDVI: single-scene manual vs median composite |
| Vegetation gain (ha) | 6.58 | 6.58 | ✅ | pending | · | 0.5 ha or 25%: two-scene manual vs composites |
| Vegetation loss (ha) | 4.28 | 4.28 | ✅ | pending | · | 0.5 ha or 25%: two-scene manual vs composites |
| Nearest coastline, distance (m) | none | none | ✅ | pending | · | 15 m: one to two 10 m pixels |
| Nearest coastline, overlap (ha) | 0.00 | 0.00 | ✅ | pending | · | 0.05 ha or 5% |
| Nearest forest, distance (m) | none | none | ✅ | pending | · | 15 m: one to two 10 m pixels |
| Nearest forest, overlap (ha) | 0.00 | 0.00 | ✅ | pending | · | 0.05 ha or 5% |
| Nearest protected area, distance (m) | 0.00 | 0.00 | ✅ | pending | · | 15 m: one to two 10 m pixels |
| Nearest protected area, overlap (ha) | 24.63 | 24.64 | ✅ | pending | · | 0.05 ha or 5% |
| Nearest water / wetland, distance (m) | 0.00 | 0.00 | ✅ | pending | · | 15 m: one to two 10 m pixels |
| Nearest water / wetland, overlap (ha) | 5.80 | 5.81 | ✅ | pending | · | 0.05 ha or 5% |

**Flags raised by the pipeline:** `pa_within_10km`, `pa_overlap`, `wetland_overlap`, `wetland_within_buffer`, `wetland_lulc_share`, `vegetation_loss`

### Farmland near Mohi, Ludhiana, Punjab (`val-ludhiana-farm`)

*Purpose:* Cropland-dominated site; crop-cycle NDVI change

| Metric | Pipeline | QGIS cross-check | | Manual baseline | | Tolerance |
|---|---:|---:|:-:|---:|:-:|---|
| Site area (ha) | 37.11 | 37.13 | ✅ | pending | · | 0.5%: planar UTM vs ellipsoidal area |
| Perimeter (m) | 2,448 | 2,448 | ✅ | pending | · | 0.5%: planar UTM vs ellipsoidal length |
| Land cover: Tree cover (%) | 0.71 | 0.71 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Shrubland (%) | 0.22 | 0.22 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Grassland (%) | 1.33 | 1.33 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Cropland (%) | 97.58 | 97.58 | ✅ | pending | · | 1 percentage point of site area |
| Land cover: Built-up (%) | 0.16 | 0.16 | ✅ | pending | · | 1 percentage point of site area |
| MNDWI median | -0.402 | -0.402 | ✅ | pending | · | 0.05 MNDWI: single-scene manual vs median composite |
| NDVI median | 0.273 | 0.273 | ✅ | pending | · | 0.05 NDVI: single-scene manual vs median composite |
| Vegetation gain (ha) | 0.38 | 0.38 | ✅ | pending | · | 0.5 ha or 25%: two-scene manual vs composites |
| Vegetation loss (ha) | 8.03 | 8.03 | ✅ | pending | · | 0.5 ha or 25%: two-scene manual vs composites |
| Nearest coastline, distance (m) | none | none | ✅ | pending | · | 15 m: one to two 10 m pixels |
| Nearest coastline, overlap (ha) | 0.00 | 0.00 | ✅ | pending | · | 0.05 ha or 5% |
| Nearest forest, distance (m) | none | none | ✅ | pending | · | 15 m: one to two 10 m pixels |
| Nearest forest, overlap (ha) | 0.00 | 0.00 | ✅ | pending | · | 0.05 ha or 5% |
| Nearest protected area, distance (m) | none | none | ✅ | pending | · | 15 m: one to two 10 m pixels |
| Nearest protected area, overlap (ha) | 0.00 | 0.00 | ✅ | pending | · | 0.05 ha or 5% |
| Nearest water / wetland, distance (m) | 1,220 | 1,220 | ✅ | pending | · | 15 m: one to two 10 m pixels |
| Nearest water / wetland, overlap (ha) | 0.00 | 0.00 | ✅ | pending | · | 0.05 ha or 5% |

**Flags raised by the pipeline:** `vegetation_loss`
