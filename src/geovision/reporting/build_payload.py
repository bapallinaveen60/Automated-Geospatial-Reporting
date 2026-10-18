"""Assemble the JSON the Typst template renders from: metrics, flags, plates, lineage, branding."""

from datetime import date
from typing import Any

from geovision.contracts.aoi import AOIRequest
from geovision.contracts.lineage import LineageRecord
from geovision.contracts.metrics import MetricsPayload


def build_payload(
    request: AOIRequest,
    metrics: MetricsPayload,
    module: dict[str, Any],
    lineage: list[LineageRecord] | None = None,
    plates: list[dict[str, str]] | None = None,
    charts: list[dict[str, str]] | None = None,
    draft: bool = True,
    reviewer: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "draft": draft,
        "generated": date.today().isoformat(),
        "module": {
            "name": module["name"],
            "title": module["title"],
            "regulations": module.get("regulations", []),
            "disclaimer": module.get("disclaimer", ""),
        },
        "project": {
            "id": request.project_id,
            "client": request.client,
            "site_name": request.site_name,
            "baseline_period": request.baseline_period.model_dump(mode="json"),
            "current_period": request.current_period.model_dump(mode="json"),
        },
        "metrics": metrics.model_dump(mode="json"),
        "plates": plates or [],
        "charts": charts or [],
        "lineage": [rec.model_dump(mode="json") for rec in (lineage or [])],
        "reviewer": reviewer,
    }
