"""Inbound contract: a request to screen one Area of Interest."""

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class DateRange(BaseModel):
    start: date
    end: date

    @model_validator(mode="after")
    def _ordered(self) -> "DateRange":
        if self.end < self.start:
            raise ValueError("end must not be before start")
        return self

    def to_stac(self) -> str:
        return f"{self.start.isoformat()}/{self.end.isoformat()}"


class AOIRequest(BaseModel):
    """What a project manager submits (via portal upload or a file dropped in ``incoming/``)."""

    project_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{2,63}$")
    client: str
    site_name: str
    module: str = "site_screening_in"
    # GeoJSON geometry or FeatureCollection in EPSG:4326.
    geometry: dict[str, Any]
    baseline_period: DateRange
    current_period: DateRange
    requested_by: str | None = None
    notes: str | None = None

    @field_validator("geometry")
    @classmethod
    def _geojson_type(cls, v: dict[str, Any]) -> dict[str, Any]:
        allowed = {"Polygon", "MultiPolygon", "Feature", "FeatureCollection"}
        if v.get("type") not in allowed:
            raise ValueError(f"geometry type must be one of {sorted(allowed)}")
        return v

    @model_validator(mode="after")
    def _periods_ordered(self) -> "AOIRequest":
        if self.baseline_period.end > self.current_period.start:
            raise ValueError("baseline_period must end before current_period starts")
        return self
