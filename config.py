"""Declarative configuration for the Trading Research Toolkit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
"""Absolute path to the repository root."""


@dataclass(frozen=True, slots=True)
class LoggingSettings:
    """Values controlling application log output."""

    level: str
    format: str
    date_format: str


@dataclass(frozen=True, slots=True)
class ProviderSettings:
    """Values identifying the market-data provider implementation to use."""

    class_path: str


@dataclass(frozen=True, slots=True)
class DownloadSettings:
    """Values controlling the initial historical-data download workflow."""

    tickers: tuple[str, ...]
    interval: str
    start_date: date
    end_date: date | None
    output_directory: Path


LOGGING_SETTINGS = LoggingSettings(
    level="INFO",
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    date_format="%Y-%m-%d %H:%M:%S",
)
"""Default logging configuration for command-line execution."""

PROVIDER_SETTINGS = ProviderSettings(
    class_path="data.providers.yfinance_provider.YFinanceProvider",
)
"""The provider implementation selected for the prototype phase."""

DOWNLOAD_SETTINGS = DownloadSettings(
    tickers=("RELIANCE.NS", "INFY.NS", "TCS.NS"),
    interval="1d",
    start_date=date(2020, 1, 1),
    end_date=None,
    output_directory=PROJECT_ROOT / "datasets" / "raw",
)
"""Initial daily-data download settings for a small Indian-equity universe."""
