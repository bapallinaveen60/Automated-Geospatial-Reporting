"""Logging setup shared by the CLI and Dagster assets."""

import logging

from geovision.core.config import get_settings

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def configure_logging(level: str | None = None) -> None:
    logging.basicConfig(level=(level or get_settings().log_level).upper(), format=_FORMAT)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
