# GeoVision — Automated Geospatial Reporting: Implementation Plan

> Source: *Automated Geospatial Reporting Strategy.pdf*
> Drafted: 2026-10-18 · Status: **Draft v0.1, for review**

---

## 1. Goal and scope

Build a **productized, open-source, cloud-native pipeline** that turns an Area of Interest (AOI) polygon into a draft regulatory report a scientist can review and approve. The report includes maps, statistics and compliance narrative.

The strategy recommends a **productized platform plus service**, not a multi-tenant SaaS (9.0/10 vs 6.0/10). So we build:

1. **A core engine.** This is a reusable library of ingest, analysis, cartography, document and orchestration modules.
2. **One reference "compliance module"** we can demo and sell. It is also the base for client pilots.
3. **A deployment kit** that installs the engine into a client's own cloud tenant.

### MVP reference module: *Environmental Site Screening Report — India* (`site_screening_in`)

A single, rigid deliverable built from public data. It supports **EIA Notification 2006 pre-screening and Form-1 preparation**, **Wetlands (Conservation & Management) Rules 2017** checks, **CRZ Notification 2019** proximity checks, and lender environmental due diligence (IFC Performance Standards). It is the Indian counterpart of a US Phase I ESA / NEPA screening.

| Section | Analysis | Data (automatable, open) |
|---|---|---|
| Site overview | AOI area (ha/acres), centroid, state/district/village | AOI upload; admin boundaries (Survey of India / LGD where licensed, geoBoundaries fallback) |
| Land use / land cover | Class breakdown (%) | ESA WorldCover 10 m, Impact Observatory LULC 10 m (Planetary Computer STAC) |
| Vegetation & water | NDVI, MNDWI, cloud-masked composite | Sentinel-2 L2A (Earth Search / Planetary Computer STAC, COG) |
| Change detection | NDVI/MNDWI delta between two periods (pre/post monsoon aware); loss/gain areas | Sentinel-2 L2A |
| Surface water & flood exposure | Water occurrence/seasonality in AOI and buffer; historic inundation proxy | JRC Global Surface Water (STAC); optional NRSC/Bhuvan flood hazard atlas layers where available |
| Wetlands | Wetlands within AOI and buffer; encroachment area | OSM water/wetland features + WorldCover wetland/mangrove classes; NWIA (SAC/ISRO) via Bhuvan as a visual overlay |
| Protected areas / ESZ | Distance to national parks, sanctuaries, notified Eco-Sensitive Zones; **10 km EIA General Condition** check | OSM `boundary=protected_area` (ODbL); PARIVESH/state ESZ notifications ingested as client-supplied layers |
| Coastal (CRZ) | Distance to coastline / HTL proxy; 500 m CRZ screening flag | OSM coastline; CZMP HTL layers if client supplies them |
| Terrain | Elevation, slope classes | Copernicus DEM GLO-30 (STAC) |
| Exceedance flags | YAML rules (e.g. PA within 10 km, wetland within buffer, >X% water occurrence) | Derived |
| Map plates | Location, imagery, NDVI, change, LULC, water/wetlands, PA/ESZ proximity | All of the above |

> All regulatory thresholds live in `modules/site_screening_in/module.yaml`. They are **screening defaults that need review by a qualified EIA consultant**, not legal determinations.
>
> **Map boundary compliance:** report maps must show India's external boundaries as published by the Survey of India. Use SoI boundary layers for location and inset maps. Never use generic global boundary datasets for these.

**Out of scope for MVP:** ML classification, the multi-tenant web app, billing, and the TiTiler web viewer (Phase 8 stretch).

### Success criteria (from the strategy doc)

- End-to-end run takes **under 15 min** from AOI to draft PDF. Human QA takes **30 min or less**.
- Metrics match a manual QGIS baseline exactly (**100% equivalence**) on 5 or more test sites.
- Output is **PDF/A-2b**. Every number traces to its inputs: STAC item IDs, cloud threshold, code version and parameters.
- Cloud cost is **under $3 per report**.

---

## 2. Key technical decisions

| Area | Decision | Why |
|---|---|---|
| Language | Python 3.11+ | Whole geospatial stack is Python |
| Packaging | `uv` + `pyproject.toml`, monorepo | Fast, reproducible lockfile |
| Raster access | `pystac-client` + `odc-stac` + `xarray`/`rioxarray` + Dask | Windowed COG reads, no full-scene downloads |
| Vector | GeoPandas + `pyogrio` + Shapely 2; GeoParquet / GeoPackage outputs | Vectorized, interoperable with QGIS/ArcGIS |
| Analytics store | DuckDB (spatial ext.) for MVP → PostGIS for client deploys | No server for dev; PostGIS where clients need it |
| Cartography | Headless **PyQGIS** + `.qpt` templates, run in **Docker** (`qgis/qgis` image + `xvfb-run`) | Full QGIS symbology. Docker sidesteps OSGeo4W pain on Windows |
| Charts | Matplotlib (SVG) | Typst embeds SVG natively |
| Documents | **Typst** CLI, data passed as JSON | Compiles in milliseconds, native PDF/A output |
| Orchestration | **Dagster** (software-defined assets, partitions per project/AOI) | Lineage, provenance and audit trail are the moat |
| Storage | Local FS (dev) → S3/Azure Blob via `fsspec` | Same code path for both |
| Config | Pydantic settings + YAML per module/client | Rules, thresholds and branding stay out of code |
| Containers | Docker Compose (dev) → ECS Fargate / Azure Container Apps (client) | Matches the strategy's ~$45/month compute figure |
| IaC | Terraform | Repeatable per-client tenant installs |
| CI | GitHub Actions: lint (ruff), types (mypy), tests (pytest), image build | |

---

## 3. Architecture

```
            ┌──────────── AOI upload (GeoJSON/SHP/KML) ──────────────┐
            ▼                                                        │
  [aoi_validated] ──► [stac_items] ──► [s2_cube] ──► [indices] ──► [change]
        │                                                 │            │
        └──► [vector_layers: parcels, flood, wetlands] ──► [intersects/buffers]
                                                          │            │
                                                          ▼            ▼
                                                    [metrics.json + exceedances]
                                                          │
                              ┌───────────────────────────┼──────────────────┐
                              ▼                           ▼                  ▼
                      [map_plates (PyQGIS)]       [charts (SVG)]     [lineage.json]
                              └──────────────► [report_draft.pdf (Typst)] ◄──┘
                                                          │
                                                 Human-in-the-loop review
                                                          │
                                               [report_final.pdf (PDF/A)]
```

Each `[box]` is a Dagster asset, partitioned by `project_id`. Every asset writes its outputs and a provenance record: inputs, parameters, git SHA and timestamps.

---

## 4. Repository layout

```
geovision/
├── pyproject.toml / uv.lock
├── docker/
│   ├── engine.Dockerfile        # Python + GDAL + Typst
│   └── qgis.Dockerfile          # qgis/qgis base + xvfb + our renderer
├── docker-compose.yml           # dagster-webserver, daemon, postgres, minio
├── src/geovision/
│   ├── core/                    # config, storage (fsspec), logging, provenance
│   ├── ingest/                  # aoi.py, stac.py, vector_sources.py
│   ├── analysis/                # masking.py, indices.py, change.py, overlay.py, rules.py
│   ├── carto/                   # render.py (PyQGIS), styles/*.qml, templates/*.qpt
│   ├── reporting/               # build_payload.py, charts.py, narrative.py, typst/ (templates)
│   ├── orchestration/           # Dagster definitions, assets, sensors, schedules
│   ├── review/                  # HITL review app (Streamlit for MVP)
│   └── modules/
│       └── site_screening_in/   # module config: layers, rules, sections, template
├── tests/                       # unit + golden-file + baseline-equivalence tests
├── data/fixtures/               # small test AOIs + clipped reference data
├── infra/terraform/             # client tenant deployment
└── docs/                        # architecture, data contracts, runbooks
```

---

## 5. Phased delivery plan (~12 weeks, 1–2 engineers)

### Phase 0 — Foundations (Week 1)
- [ ] Init git repo, `uv` project, ruff/mypy/pytest, pre-commit, GitHub Actions.
- [ ] Install Docker Desktop, Typst CLI and QGIS (LTR, for designing templates).
- [ ] Write `core/`: settings, `fsspec` storage abstraction, structured logging, and a `Provenance` record model.
- [ ] Define **data contracts** (Pydantic + JSON Schema): `AOIRequest`, `MetricsPayload`, `ExceedanceFlag` and `LineageRecord`.
- [ ] Choose 5 test AOIs and collect manual baseline outputs for them (see Phase 7).
- **Exit:** CI is green, contracts are documented, and fixtures are in `data/fixtures/`.

### Phase 1 — Ingestion (Weeks 2–3)
- [ ] `ingest/aoi.py`: read GeoJSON/SHP/KML/GPKG and fix invalid geometry (`make_valid`). Check topology, area limits, CRS and multipart. Pick a UTM CRS automatically for area math.
- [ ] `ingest/stac.py`: search Earth Search / Planetary Computer by bbox, date and cloud cover. Load lazily with `odc.stac.load` (Dask chunks) and support retry/backoff.
- [ ] `ingest/vector_sources.py`: pluggable connectors (OSM Overpass, local file/GeoParquet, WFS) for protected areas, wetlands/water and coastline. Clip to the AOI plus a buffer and cache as GeoParquet.
- [ ] `ingest/raster_sources.py`: STAC thematic rasters (ESA WorldCover, JRC GSW, Copernicus DEM) clipped to the AOI and its buffer.
- **Exit:** given an AOI, we get an xarray cube plus clipped vector layers in under 60 s, with a STAC item list recorded.

### Phase 2 — Analysis engine (Weeks 3–4)
- [ ] `masking.py`: mask with SCL (cloud, shadow, saturated, no-data) and build a median composite.
- [ ] `indices.py`: NDVI and MNDWI, unit-tested against hand-computed arrays.
- [ ] `change.py`: two-period composite delta, thresholded loss/gain rasters and areas in ha/acres.
- [ ] `overlay.py`: LULC class breakdown, water-occurrence stats, wetland buffers/encroachment, protected-area/coast distance, all in a projected CRS (auto UTM 42N–47N).
- [ ] `rules.py`: YAML-driven exceedance rules that produce `ExceedanceFlag[]`.
- [ ] Export: COGs (rioxarray), GeoPackage and GeoParquet, plus `metrics.json`.
- **Exit:** `metrics.json` validates against the schema, and the outputs open cleanly in QGIS.

### Phase 3 — Headless cartography (Weeks 5–6)
- [ ] Design `.qpt` print layouts in QGIS Desktop with fixed item IDs (`MainMap`, `Title`, `Legend`, `ScaleBar`, `InsetMap`). Use one template per plate type.
- [ ] Write `.qml` styles for each layer type, with consistent symbology.
- [ ] `carto/render.py`: build a `QgsProject` from layers, load the template, zoom to the AOI with padding, set labels and export a 300 dpi PDF and PNG.
- [ ] Wait for basemap XYZ tiles to finish loading before export (event-loop sync).
- [ ] Run it in the `qgis` container under `xvfb-run`. It is called as a Dagster op through `docker run` or a sidecar service.
- [ ] Golden-image tests (perceptual diff) on fixture AOIs.
- **Exit:** 6 plates per AOI in under 30 s, visually consistent across all test sites.

### Phase 4 — Document compilation (Weeks 6–7)
- [ ] `reporting/charts.py`: SVG charts covering the land-cover histogram, NDVI distribution and change summary.
- [ ] `reporting/build_payload.py`: merge metrics, flags, plate paths, lineage and branding into `report.json`.
- [ ] Typst template covering the cover page, executive summary, site description, methods (auto-filled from parameters), results tables, exceedance table, map plates, data sources/lineage appendix and a signature block.
- [ ] Narrative text comes from **templated sentences** (Jinja-style rules, no LLM in MVP), for example: "The nearest protected area, X, lies Y km from the site boundary, within the 10 km EIA General Condition radius."
- [ ] Compile with `typst compile --input data=report.json --pdf-standard a-2b`, then check with veraPDF.
- [ ] Mark draft PDFs with a "DRAFT – NOT FOR SUBMISSION" watermark.
- **Exit:** the report compiles in under 1 s and passes the PDF/A validator.

### Phase 5 — Orchestration and lineage (Weeks 7–8)
- [ ] Turn every stage into a Dagster software-defined asset, dynamically partitioned by `project_id`.
- [ ] Add a **sensor** that watches the `incoming/` bucket for new AOIs and a **schedule** for recurring monitoring runs.
- [ ] Attach asset metadata (STAC IDs, cloud %, thresholds, git SHA, package versions, runtime) and emit `lineage.json`, which feeds the report appendix. This is the **chain-of-custody moat**.
- [ ] Add retries, failure alerts (email/Slack) and resource configs (Dask, storage).
- **Exit:** AOI drop → draft PDF fully automatic, with the full lineage graph visible in the Dagster UI.

### Phase 6 — Human-in-the-loop review (Week 9)
- [ ] Build a Streamlit review app that lists pending drafts. It shows the PDF, highlights exceedances and anomalous land-cover change, and offers an interactive map (leafmap/folium over the COGs).
- [ ] Reviewers can add annotations and comments, and override a flag with a required justification.
- [ ] Approval re-runs only the Typst step with reviewer name, licence number and date, removes the watermark and stores an immutable final PDF and audit log.
- **Exit:** the reviewer workflow takes 30 min or less on a test site, and every approval and override is logged.

### Phase 7 — Validation and hardening (Weeks 10–11)
- [ ] **Parallel-run validation:** compare pipeline output with manual QGIS results on 5 or more sites (areas, percentages, buffer distances) within a documented tolerance, aiming for exact match on vector math.
- [ ] Edge cases: AOI crossing UTM zones, tiny or huge AOIs, 100% cloud periods (fallback date window), missing vector coverage, and slivers.
- [ ] Performance: profile and tune Dask chunking. Run AOIs concurrently.
- [ ] Write runbooks for failure handling, manual override and adding a new layer.
- **Exit:** a validation report signed off, and benchmarks recorded (time and cost per report).

### Phase 8 — Client deployment kit and demo (Week 12)
- [ ] Terraform for one cloud (start with AWS: S3, ECS Fargate, RDS PostGIS, Dagster+, Secrets Manager).
- [ ] Per-client config overlay covering branding, template, layers and rules.
- [ ] Demo kit: 3 sample reports, a short screen recording and the ROI calculator (from the economics table).
- [ ] *Stretch:* TiTiler service for dynamic web tiles in the review app.
- **Exit:** a fresh tenant deployed from scratch in under 1 day.

---

## 6. Business track (runs in parallel)

This follows the strategy's productized tiers:

| Week | Activity |
|---|---|
| 1–2 | Turn the **qualification matrix** into a scoring sheet: frequency 20%, labor 25%, fragmentation 20%, standardization 20%, error risk 15%. Pursue workflows scoring 20 or more. Treat 15–19 as pilot candidates and skip anything below 12. |
| 2–4 | Build an outreach list of 15–100-person environmental/engineering firms (Practice Leaders, GIS Managers). |
| 6+ | Offer the **Phase 1 Audit & Pilot** ($5–8.5k, 2 weeks), using the MVP as the demo. |
| 12+ | Convert pilots to **Core Build** ($22–45k, 6–10 weeks) plus a **Managed SLA** ($1.5–3.5k/month). |

The client delivery playbook follows the strategy's 10-week rhythm. It runs audit and schema freeze, then core build, then parallel-run validation, then handover. This engine is built to make that playbook repeatable.

---

## 7. Testing strategy

- **Unit tests:** indices, masking, overlay math and rule evaluation, run on synthetic arrays and geometries.
- **Contract tests:** every JSON payload is validated against its schema.
- **Golden-file tests:** map PNGs (perceptual diff) and the report's text layer.
- **Baseline-equivalence tests:** pipeline metrics vs manual QGIS results on fixture sites. CI fails if they drift.
- **Integration test:** run the full Dagster job on a tiny AOI, using cached STAC responses (VCR) so CI needs no network.

---

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| PyQGIS headless crashes or font issues | Pin QGIS LTR in Docker, use `xvfb-run`, bundle fonts, keep golden tests |
| Upstream STAC/API outages or rate limits | Retries/backoff, a secondary catalog (Planetary Computer) and a cache |
| Cloudy periods leave no usable imagery | Expand the date window automatically, then fall back to Landsat and flag it in the report |
| Indian authoritative data (NWIA, flood atlas, ESZ, CZMP HTL) is mostly WMS/PDF, not analysis-ready vector | Compute from open global STAC data (WorldCover, JRC GSW, Cop-DEM) + OSM. Use Bhuvan WMS for visual overlays only. Ingest client-supplied ESZ/HTL shapefiles through the same connector interface |
| Map boundary legality (India) | Survey of India boundaries for every location/inset map; boundary layer pinned in module config; golden-image check |
| Dataset licences (WDPA and GADM are non-commercial) | Use OSM (ODbL), geoBoundaries (CC BY), ESA WorldCover (CC BY 4.0), JRC GSW (open). Licence registry in `module.yaml`, printed in the report appendix |
| Clients ask for endless custom formatting | Rigid modules per standard. Customization is limited to the branding/template overlay and billed under the retainer |
| Liability: automated misclassification | Mandatory HITL approval, draft watermark, lineage appendix, no auto-submission |
| Low technical moat | Invest in connectors, pre-built regulatory templates and lineage/audit features |

---

## 9. Open decisions (need your input)

1. ~~Target geography~~ → **India** (decided 2026-10-18).
2. **Cloud provider** for client deployments: AWS (default here) or Azure?
3. **Team:** how many engineers, and is there a GIS/environmental SME to provide the manual baselines and review the template?
4. **First vertical after MVP:** EIA Form-1 / pre-feasibility support, CRZ clearance support, lender ESDD (IFC PS), or EUDR for Indian exporters?
5. **Survey of India data:** do we have access to SoI OVSF / NGDR boundary layers, or should clients supply them?

---

## 10. Immediate next steps (this week)

1. Confirm the open decisions above.
2. Install Docker Desktop, Typst and QGIS LTR, then `git init` and scaffold the repo layout from §4.
3. Write the data contracts (`AOIRequest`, `MetricsPayload`, `LineageRecord`).
4. Build a **thin vertical slice** first: AOI → STAC search → NDVI → one QGIS plate → one-page Typst PDF. Then deepen each layer.
