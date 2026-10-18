# GeoVision — Automated Geospatial Reporting

AOI polygon in → reviewed, audit-ready environmental screening report (PDF/A) out.

Cloud-native pipeline: **STAC + COG** (Sentinel-2, ESA WorldCover, JRC GSW, Copernicus DEM) → **xarray/GeoPandas** analysis → **headless PyQGIS** map plates → **Typst** report → **Dagster** orchestration with full lineage → **human-in-the-loop** approval.

The reference module is `site_screening_in`, an Environmental Site Screening Report for **India**. It covers EIA 2006 10 km proximity, Wetlands Rules 2017, CRZ 2019 and forest checks.

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the roadmap.

## Quick start

```bash
uv sync --group dev
uv run pytest                      # offline unit tests
uv run pytest -m network           # live STAC / OSM smoke tests
uv run geovision validate-aoi data/fixtures/aoi_ameenpur.geojson
uv run geovision schemas --out docs/schemas
```

Optional extras:

```bash
uv sync --extra orchestration      # Dagster:  uv run dagster dev
uv sync --extra review             # Streamlit review app
```

External tools:

| Tool | Used for | Install |
|---|---|---|
| Typst ≥ 0.13 | Report compilation | `winget install --id Typst.Typst` |
| Docker Desktop | QGIS renderer, dev stack | docker.com |
| QGIS LTR | Designing `.qpt` templates / `.qml` styles | qgis.org |

## Layout

```
src/geovision/
  core/          settings, fsspec storage, provenance, logging
  contracts/     Pydantic data contracts (AOIRequest, MetricsPayload, LineageRecord)
  ingest/        AOI validation, Sentinel-2 STAC, thematic rasters, vector connectors (OSM / file)
  analysis/      SCL masking, indices, change, overlays, YAML rules engine
  carto/         headless PyQGIS renderer (runs in docker/qgis.Dockerfile), templates, styles
  reporting/     payload builder, Typst template + compiler
  orchestration/ Dagster assets, sensor, job
  review/        Streamlit HITL review app
  modules/       compliance modules (site_screening_in/module.yaml)
```

## Data and licensing notes

- Report maps must show India's boundaries **as published by the Survey of India**.
- WDPA and GADM are non-commercial. The defaults use OSM (ODbL), ESA WorldCover (CC BY 4.0) and other open data.
- Screening thresholds in `module.yaml` are defaults that need review by a qualified EIA consultant.
