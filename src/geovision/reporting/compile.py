"""Compile a report with the Typst CLI from a JSON payload."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from geovision.core.config import get_settings

TEMPLATE_DIR = Path(__file__).parent / "typst"


class TypstError(RuntimeError):
    pass


def find_typst() -> str:
    """Configured binary, else PATH, else a winget install (shells opened before the install
    don't see winget's PATH update)."""
    configured = get_settings().typst_bin
    found = shutil.which(configured)
    if found:
        return found
    local = os.environ.get("LOCALAPPDATA")
    if local:
        winget = sorted(
            Path(local, "Microsoft", "WinGet", "Packages").glob("Typst.Typst_*/*/typst.exe")
        )
        if winget:
            return str(winget[-1])
    raise TypstError(
        f"Typst CLI not found ({configured!r}). Install it (winget install --id Typst.Typst), "
        "open a new terminal, or set GEOVISION_TYPST_BIN to the full path."
    )


def payload_path(pdf: Path) -> Path:
    return pdf.with_name(f"{pdf.stem}.payload.json")


def compile_report(
    payload: dict[str, Any],
    out_pdf: str | Path,
    template: str = "report.typ",
    build_dir: str | Path | None = None,
    pdf_standard: str | None = "a-2b",
) -> Path:
    """Copy the template into a build dir, write ``report.json`` beside it and run Typst.

    Plate/chart files referenced in the payload are copied into the build dir, and their
    paths rewritten with forward slashes (Typst rejects backslashes). The source payload is
    saved as ``<pdf stem>.payload.json`` so the report can be recompiled (e.g. on approval)
    from exactly the content that was reviewed.
    """
    out_pdf = Path(out_pdf)
    build = Path(build_dir) if build_dir else out_pdf.parent / f"_build_{out_pdf.stem}"
    build.mkdir(parents=True, exist_ok=True)
    for f in TEMPLATE_DIR.glob("*.typ"):
        shutil.copy2(f, build / f.name)

    payload = {
        **payload,
        **{
            kind: [{**i, "path": str(Path(i["path"]).resolve())} for i in payload.get(kind, [])]
            for kind in ("plates", "charts")
        },
    }
    payload_path(out_pdf).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    # Typst can only read files under --root, so copy figures in and rewrite their paths.
    payload = {**payload}
    for kind in ("plates", "charts"):
        items = []
        for item in payload.get(kind, []):
            src = Path(item["path"])
            if src.exists():
                dest = build / kind / src.name
                dest.parent.mkdir(exist_ok=True)
                shutil.copy2(src, dest)
                item = {**item, "path": f"{kind}/{src.name}"}
            items.append(item)
        payload[kind] = items

    (build / "report.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    cmd = [find_typst(), "compile", "--root", str(build)]
    if pdf_standard:
        cmd += ["--pdf-standard", pdf_standard]
    cmd += [str(build / template), str(out_pdf.resolve())]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise TypstError(result.stderr.strip())
    return out_pdf
