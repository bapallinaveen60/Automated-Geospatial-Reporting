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
uv sync --extra orchestration      # Dagster
uv sync --extra review             # Streamlit review app
```

## Running reports

Copy `.env.example` to `.env` and set `GEOVISION_QGIS_PYTHON` to your QGIS launcher (or build the Docker renderer image instead). Typst must be on `PATH`.

**One-off, without orchestration:**

```bash
uv run python scripts/demo_report.py data/fixtures/request_ameenpur.json
```

**With Dagster (lineage UI, retries, automatic runs):**

```bash
# Optional, keeps run history (PowerShell; the folder must exist):
#   mkdir .dagster -Force; $env:DAGSTER_HOME = "$PWD\.dagster"
uv run --extra orchestration dagster dev
```

Open http://localhost:3000. Any `AOIRequest` JSON saved as `data/runs/incoming/<project_id>.json` is picked up by the `incoming_aoi_sensor` within 30 s and runs through to `data/runs/<project_id>/report/<project_id>_draft.pdf`. Editing the file triggers a re-run. To run one request without the UI:

```bash
uv run --extra orchestration python scripts/run_dagster_partition.py data/fixtures/request_ameenpur.json
```

Asset graph (one partition per project):

```
aoi_request → aoi_validated ─┬─ s2_imagery ────────┐
                             ├─ land_cover ────────┼─ screening_metrics → map_plates → report_draft
                             └─ proximity_results ─┘
```

External tools:

| Tool | Used for | Install |
|---|---|---|
| Typst ≥ 0.15 | Report compilation | `winget install --id Typst.Typst` |
| QGIS 3.44 LTR | Map plates (local renderer); designing `.qpt` / `.qml` | qgis.org |
| Docker Desktop | Containerised QGIS renderer, dev stack (optional locally) | docker.com |

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
