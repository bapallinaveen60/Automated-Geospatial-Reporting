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
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
