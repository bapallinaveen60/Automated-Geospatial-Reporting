"""Analysis output contract: the numbers the report is built from."""

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["info", "warning", "critical"]


class SiteSummary(BaseModel):
    area_ha: float
    perimeter_m: float
    centroid_lon: float
    centroid_lat: float
    analysis_crs: str
    state: str | None = None
    district: str | None = None
    locality: str | None = None


class ClassShare(BaseModel):
    code: int
    label: str
    area_ha: float
    percent: float


class IndexStats(BaseModel):
    mean: float | None
    median: float | None
    p10: float | None
    p90: float | None
    valid_fraction: float


class ChangeSummary(BaseModel):
    index: str
    threshold: float
    loss_ha: float
    gain_ha: float
    net_change_mean: float | None


class ProximityResult(BaseModel):
    layer: str
    nearest_name: str | None
    distance_m: float | None  # 0 when the feature overlaps the site; None when none were found
    overlap_ha: float = 0.0
    search_radius_m: float


class ExceedanceFlag(BaseModel):
    rule_id: str
    severity: Severity
    message: str
    metric: str
    value: float | None
    threshold: float | None
    regulation: str | None = None


class MetricsPayload(BaseModel):
    project_id: str
    site: SiteSummary
    lulc: list[ClassShare] = Field(default_factory=list)
    indices: dict[str, IndexStats] = Field(default_factory=dict)
    change: list[ChangeSummary] = Field(default_factory=list)
    proximity: list[ProximityResult] = Field(default_factory=list)
    flags: list[ExceedanceFlag] = Field(default_factory=list)

    def flat(self) -> dict[str, float | None]:
        """Dotted-key view for the rules engine, e.g. ``proximity.protected_areas.distance_m``."""
        out: dict[str, float | None] = {
            "site.area_ha": self.site.area_ha,
            "site.perimeter_m": self.site.perimeter_m,
        }
        for c in self.lulc:
            out[f"lulc.{c.code}.percent"] = c.percent
            out[f"lulc.{c.code}.area_ha"] = c.area_ha
        for name, s in self.indices.items():
            for field in ("mean", "median", "p10", "p90", "valid_fraction"):
                out[f"indices.{name}.{field}"] = getattr(s, field)
        for ch in self.change:
            out[f"change.{ch.index}.loss_ha"] = ch.loss_ha
            out[f"change.{ch.index}.gain_ha"] = ch.gain_ha
        for p in self.proximity:
            out[f"proximity.{p.layer}.distance_m"] = p.distance_m
            out[f"proximity.{p.layer}.overlap_ha"] = p.overlap_ha
        return out
