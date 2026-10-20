"""GeoVision web API: submit screening requests, follow progress, fetch reports and maps.

The React app (frontend/) talks to this; in production its built files are served from here
too, so everything runs on one port:

    uv run --extra api uvicorn geovision.api.main:app --port 8000
"""

import json
import re
import secrets
import shutil
import tempfile
from datetime import date
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError
from shapely.geometry import mapping

from geovision.api.status import list_project_ids, load_request, project_status, report_path
from geovision.contracts import AOIRequest, DateRange, MetricsPayload
from geovision.core.config import get_settings
from geovision.ingest.aoi import AOIValidationError, read_aoi, validate_aoi
from geovision.modules import load_module
from geovision.reporting.narrative import summary_paragraphs

PROJECT_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
PLATE_FILE = re.compile(r"^plate\d+_[a-z_]+\.png$")
PLATE_TITLES = {
    "context": "Site context",
    "ndvi": "Vegetation (NDVI)",
    "landcover": "Land cover",
    "ndvi_change": "Vegetation change",
}
UPLOAD_SUFFIXES = {".geojson", ".json", ".kml", ".gpkg", ".zip"}
FRONTEND_DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"

app = FastAPI(title="GeoVision", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _root() -> Path:
    return Path(get_settings().data_root)


def _check_id(project_id: str) -> str:
    if not PROJECT_ID.match(project_id):
        raise HTTPException(404, "Unknown project")
    return project_id


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def default_periods(today: date | None = None) -> dict[str, DateRange]:
    """Latest complete Oct–Mar dry season, and the same season four years earlier."""
    today = today or date.today()
    end_year = today.year if today.month >= 4 else today.year - 1
    current = DateRange(start=date(end_year - 1, 10, 1), end=date(end_year, 3, 31))
    baseline = DateRange(start=date(end_year - 5, 10, 1), end=date(end_year - 4, 3, 31))
    return {"baseline": baseline, "current": current}


def new_project_id(site_name: str, today: date | None = None) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", site_name.lower()).strip("-")[:40] or "site"
    stamp = (today or date.today()).strftime("%Y%m%d")
    return f"{slug}-{stamp}-{secrets.token_hex(2)}"


# ---------------------------------------------------------------------------------- API ---


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/defaults")
def defaults() -> dict[str, Any]:
    module = load_module("site_screening_in")
    return {
        "periods": {k: v.model_dump(mode="json") for k, v in default_periods().items()},
        "max_area_ha": module.aoi.get("max_area_ha"),
        "module_title": module.title,
    }


@app.post("/api/aoi/preview")
async def preview_aoi(file: Annotated[UploadFile, File()]) -> dict[str, Any]:
    """Validate an uploaded boundary file and return it as GeoJSON with its area."""
    name = file.filename or "upload"
    suffix = Path(name).suffix.lower()
    if suffix not in UPLOAD_SUFFIXES:
        raise HTTPException(422, "Upload a GeoJSON, KML, GeoPackage or zipped Shapefile.")
    limits = load_module("site_screening_in").aoi
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"aoi{suffix}"
        with path.open("wb") as out:
            shutil.copyfileobj(file.file, out)
        try:
            aoi = validate_aoi(
                read_aoi(path),
                min_area_ha=limits.get("min_area_ha", 0.01),
                max_area_ha=limits.get("max_area_ha", 50_000),
            )
        except AOIValidationError as e:
            raise HTTPException(422, str(e)) from e
        except Exception as e:  # noqa: BLE001 - unreadable/corrupt files
            raise HTTPException(422, f"Could not read the boundary file: {e}") from e
    c = aoi.geometry.centroid
    return {
        "geometry": mapping(aoi.geometry),
        "area_ha": round(aoi.area_ha, 4),
        "perimeter_m": round(aoi.perimeter_m, 1),
        "centroid": [c.x, c.y],
        "bbox": list(aoi.bbox),
        "warnings": list(aoi.warnings),
    }


class NewProject(BaseModel):
    client: str = Field(min_length=1, max_length=200)
    site_name: str = Field(min_length=1, max_length=200)
    geometry: dict[str, Any]
    baseline_period: DateRange
    current_period: DateRange
    requested_by: str | None = None
    notes: str | None = None


@app.post("/api/projects", status_code=201)
def create_project(body: NewProject) -> dict[str, str]:
    project_id = new_project_id(body.site_name)
    try:
        request = AOIRequest(project_id=project_id, module="site_screening_in", **body.model_dump())
    except ValidationError as e:
        raise HTTPException(422, e.errors()[0]["msg"]) from e
    incoming = _root() / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    (incoming / f"{project_id}.json").write_text(
        request.model_dump_json(indent=2), encoding="utf-8"
    )
    return {"id": project_id}


def _flag_counts(metrics: dict[str, Any] | None) -> dict[str, int]:
    flags = (metrics or {}).get("flags", [])
    return {sev: sum(f["severity"] == sev for f in flags) for sev in ("critical", "warning")}


@app.get("/api/projects")
def list_projects() -> list[dict[str, Any]]:
    root, url = _root(), get_settings().dagster_url
    out = []
    for pid in list_project_ids(root):
        loaded = load_request(root, pid)
        if loaded is None:
            continue
        req, submitted = loaded
        status = project_status(pid, root, url)
        out.append(
            {
                "id": pid,
                "site_name": req.get("site_name"),
                "client": req.get("client"),
                "submitted": submitted.isoformat(),
                "status": {
                    "state": status.state,
                    "label": status.label,
                    "completed": status.completed,
                    "total": status.total,
                    "engine_online": status.engine_online,
                },
                "flags": _flag_counts(_read_json(root / pid / "analysis" / "metrics.json")),
            }
        )
    return sorted(out, key=lambda p: p["submitted"], reverse=True)


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict[str, Any]:
    root = _root()
    pid = _check_id(project_id)
    loaded = load_request(root, pid)
    if loaded is None:
        raise HTTPException(404, "Unknown project")
    req, submitted = loaded
    status = project_status(pid, root, get_settings().dagster_url)

    metrics_raw = _read_json(root / pid / "analysis" / "metrics.json")
    metrics = MetricsPayload.model_validate(metrics_raw) if metrics_raw else None
    lineage = _read_json(root / pid / "analysis" / "lineage.json") or {}
    plates_dir = root / pid / "analysis" / "plates"
    plates = [
        {
            "title": PLATE_TITLES.get(p.stem.split("_", 1)[1], p.stem.split("_", 1)[1]),
            "url": f"/api/projects/{pid}/plates/{p.name}",
        }
        for p in sorted(plates_dir.glob("plate*_*.png"))
    ]
    return {
        "id": pid,
        "site_name": req.get("site_name"),
        "client": req.get("client"),
        "submitted": submitted.isoformat(),
        "periods": {"baseline": req.get("baseline_period"), "current": req.get("current_period")},
        "geometry": req.get("geometry"),
        "status": status.to_dict(),
        "summary": summary_paragraphs(metrics) if metrics else [],
        "metrics": metrics.model_dump(mode="json") if metrics else None,
        "warnings": lineage.get("warnings", []),
        "plates": plates,
        "report_url": f"/api/projects/{pid}/report" if report_path(root, pid).exists() else None,
    }


@app.post("/api/projects/{project_id}/rerun", status_code=202)
def rerun_project(project_id: str) -> dict[str, str]:
    """Touch the request file; the Dagster sensor treats a new mtime as a new run."""
    root, pid = _root(), _check_id(project_id)
    incoming = root / "incoming" / f"{pid}.json"
    if not incoming.exists():
        archived = root / pid / "request.json"
        if not archived.exists():
            raise HTTPException(404, "Unknown project")
        incoming.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(archived, incoming)
    incoming.touch()
    return {"id": pid}


@app.get("/api/projects/{project_id}/report")
def get_report(project_id: str) -> FileResponse:
    pid = _check_id(project_id)
    path = report_path(_root(), pid)
    if not path.exists():
        raise HTTPException(404, "Report not ready yet")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@app.get("/api/projects/{project_id}/plates/{filename}")
def get_plate(project_id: str, filename: str) -> FileResponse:
    pid = _check_id(project_id)
    if not PLATE_FILE.match(filename):
        raise HTTPException(404, "Unknown map")
    path = _root() / pid / "analysis" / "plates" / filename
    if not path.exists():
        raise HTTPException(404, "Unknown map")
    return FileResponse(path, media_type="image/png")


# ------------------------------------------------------------------ built React app ---


@app.get("/{path:path}", include_in_schema=False)
def frontend(path: str) -> FileResponse:
    if path == "api" or path.startswith("api/"):
        raise HTTPException(404, "Not found")
    if not FRONTEND_DIST.exists():
        raise HTTPException(404, "Frontend not built. Run `npm run build` in frontend/.")
    target = (FRONTEND_DIST / path).resolve()
    if path and target.is_file() and FRONTEND_DIST in target.parents:
        return FileResponse(target)
    return FileResponse(FRONTEND_DIST / "index.html")  # client-side routes
