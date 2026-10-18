"""Compile a report with the Typst CLI from a JSON payload."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from geovision.core.config import get_settings

TEMPLATE_DIR = Path(__file__).parent / "typst"


class TypstError(RuntimeError):
    pass


def compile_report(
    payload: dict[str, Any],
    out_pdf: str | Path,
    template: str = "report.typ",
    build_dir: str | Path | None = None,
    pdf_standard: str | None = "a-2b",
) -> Path:
    """Copy the template into a build dir, write ``report.json`` beside it and run Typst.

    Map plates and charts referenced in the payload must be paths relative to ``build_dir``.
    """
    out_pdf = Path(out_pdf)
    build = Path(build_dir) if build_dir else out_pdf.parent / "_build"
    build.mkdir(parents=True, exist_ok=True)
    for f in TEMPLATE_DIR.glob("*.typ"):
        shutil.copy2(f, build / f.name)
    (build / "report.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    cmd = [get_settings().typst_bin, "compile", "--root", str(build)]
    if pdf_standard:
        cmd += ["--pdf-standard", pdf_standard]
    cmd += [str(build / template), str(out_pdf.resolve())]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except FileNotFoundError as e:
        raise TypstError("Typst CLI not found; install it or set GEOVISION_TYPST_BIN") from e
    if result.returncode != 0:
        raise TypstError(result.stderr.strip())
    return out_pdf
