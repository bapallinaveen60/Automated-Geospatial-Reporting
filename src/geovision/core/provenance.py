"""Capture the code and environment state that produced an output (chain-of-custody)."""

import subprocess
from datetime import UTC, datetime
from importlib import metadata

from geovision import __version__

TRACKED_PACKAGES = (
    "numpy",
    "shapely",
    "geopandas",
    "pyproj",
    "odc-stac",
    "pystac-client",
    "xarray",
    "rioxarray",
    "osmnx",
)


def git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=5
        )
        sha = out.stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, timeout=5
        ).stdout.strip()
        return f"{sha}-dirty" if dirty else sha
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def package_versions(packages: tuple[str, ...] = TRACKED_PACKAGES) -> dict[str, str]:
    versions = {"geovision": __version__}
    for name in packages:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "not-installed"
    return versions


def utcnow() -> datetime:
    return datetime.now(UTC)
