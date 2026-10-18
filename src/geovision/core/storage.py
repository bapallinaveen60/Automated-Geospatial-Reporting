"""Storage abstraction over fsspec so the same code writes to local disk, S3 or Azure Blob.

Layout: ``<data_root>/<project_id>/<stage>/<file>``.
"""

import json
from typing import Any

import fsspec
from pydantic import BaseModel

from geovision.core.config import get_settings


class ProjectStorage:
    def __init__(self, project_id: str, root: str | None = None) -> None:
        self.project_id = project_id
        self.root = (root or get_settings().data_root).rstrip("/")
        self.fs, _ = fsspec.core.url_to_fs(self.root)

    def path(self, *parts: str) -> str:
        return "/".join([self.root, self.project_id, *parts])

    def exists(self, *parts: str) -> bool:
        return bool(self.fs.exists(self.path(*parts)))

    def write_json(self, data: BaseModel | dict[str, Any], *parts: str) -> str:
        target = self.path(*parts)
        self.fs.makedirs(target.rsplit("/", 1)[0], exist_ok=True)
        text = (
            data.model_dump_json(indent=2)
            if isinstance(data, BaseModel)
            else json.dumps(data, indent=2, default=str)
        )
        with self.fs.open(target, "w", encoding="utf-8") as f:
            f.write(text)
        return target

    def read_json(self, *parts: str) -> Any:
        with self.fs.open(self.path(*parts), "r", encoding="utf-8") as f:
            return json.load(f)
