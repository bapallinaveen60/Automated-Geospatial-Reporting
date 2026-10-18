"""Provenance contract: every pipeline output records exactly what produced it."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class InputRef(BaseModel):
    kind: Literal["stac_item", "vector_source", "raster_source", "file", "asset"]
    id: str
    href: str | None = None
    collection: str | None = None
    acquired: datetime | None = None
    licence: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class LineageRecord(BaseModel):
    asset_key: str
    project_id: str
    inputs: list[InputRef] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    code_version: str
    package_versions: dict[str, str] = Field(default_factory=dict)
    started_at: datetime
    finished_at: datetime
