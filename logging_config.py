"""Logging setup for command-line application execution."""

from __future__ import annotations

import logging
from pathlib import Path

from config import LOG_FILE_PATH, LoggingSettings


def configure_logging(settings: LoggingSettings) -> None:
    """Configure the process-wide logging handler and formatting.

    Args:
        settings: Declarative logging values supplied by ``config``.

    Returns:
        None.

    Raises:
        ValueError: If ``settings.level`` is not a valid logging level.
    """
    numeric_level = logging.getLevelNamesMapping().get(settings.level.upper())
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid logging level: {settings.level!r}")

    log_path = Path(LOG_FILE_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    logging.basicConfig(
        level=numeric_level,
        format=settings.format,
        datefmt=settings.date_format,
        handlers=[file_handler],
        force=True,
    )
