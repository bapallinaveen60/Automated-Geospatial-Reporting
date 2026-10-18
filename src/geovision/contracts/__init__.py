"""Pydantic data contracts shared between pipeline stages. JSON Schemas live in docs/schemas/."""

import json
from pathlib import Path

from pydantic import BaseModel

from geovision.contracts.aoi import AOIRequest, DateRange
from geovision.contracts.lineage import InputRef, LineageRecord
from geovision.contracts.metrics import (
    ChangeSummary,
    ClassShare,
    ExceedanceFlag,
    IndexStats,
    MetricsPayload,
    ProximityResult,
    SiteSummary,
)

__all__ = [
    "AOIRequest",
    "ChangeSummary",
    "ClassShare",
    "DateRange",
    "ExceedanceFlag",
    "IndexStats",
    "InputRef",
    "LineageRecord",
    "MetricsPayload",
    "ProximityResult",
    "SiteSummary",
    "export_schemas",
]

_SCHEMA_MODELS: tuple[type[BaseModel], ...] = (AOIRequest, MetricsPayload, LineageRecord)


def export_schemas(out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for model in _SCHEMA_MODELS:
        path = out / f"{model.__name__}.schema.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written
