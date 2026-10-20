"""Runtime settings, read from environment variables prefixed ``GEOVISION_`` or a ``.env`` file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GEOVISION_", env_file=".env", extra="ignore")

    # Local path or fsspec URL (s3://, az://) where per-project run outputs are stored.
    data_root: str = "./data/runs"
    stac_url: str = "https://earth-search.aws.element84.com/v1"
    pc_stac_url: str = "https://planetarycomputer.microsoft.com/api/stac/v1"
    typst_bin: str = "typst"
    qgis_image: str = "geovision-qgis:latest"
    # Path to a local QGIS Python launcher (e.g. python-qgis-ltr.bat). When set, map plates
    # render with local QGIS instead of the Docker image.
    qgis_python: str | None = None
    # Dagster webserver, queried by the web app for run progress.
    dagster_url: str = "http://127.0.0.1:3000"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
