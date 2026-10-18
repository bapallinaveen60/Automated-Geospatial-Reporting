"""Compliance modules: a module is a YAML config of layers, rules and report wording."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from geovision.analysis.rules import Rule

MODULES_DIR = Path(__file__).parent


class LayerSpec(BaseModel, extra="allow"):
    source: str
    search_radius_m: float = 1000


class ModuleConfig(BaseModel):
    name: str
    title: str
    version: str
    regulations: list[str] = Field(default_factory=list)
    disclaimer: str = ""
    aoi: dict[str, float] = Field(default_factory=dict)
    imagery: dict[str, Any] = Field(default_factory=dict)
    indices: dict[str, dict[str, float]] = Field(default_factory=dict)
    rasters: dict[str, dict[str, Any]] = Field(default_factory=dict)
    layers: dict[str, LayerSpec] = Field(default_factory=dict)
    rules: list[Rule] = Field(default_factory=list)
    licences: dict[str, str] = Field(default_factory=dict)

    def lulc_labels(self) -> dict[int, str]:
        return {int(k): v for k, v in self.rasters.get("worldcover", {}).get("labels", {}).items()}


def load_module(name: str) -> ModuleConfig:
    path = MODULES_DIR / name / "module.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Unknown module {name!r} (looked for {path})")
    return ModuleConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
