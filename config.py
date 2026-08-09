"""Declarative configuration for the Trading Research Toolkit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
"""Absolute path to the repository root."""

load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
"""Load local project secrets without overriding explicitly supplied environment values."""


LOG_FILE_PATH = PROJECT_ROOT / "logs" / "trading_research.log"
"""Append-only destination for application logging."""


TICKER_UNIVERSE_FILES: tuple[tuple[str, Path], ...] = (
    ("NIFTY50", PROJECT_ROOT / "datasets" / "tickers" / "nifty50.txt"),
    ("NIFTY100", PROJECT_ROOT / "datasets" / "tickers" / "nifty100.txt"),
    ("NIFTY150", PROJECT_ROOT / "datasets" / "tickers" / "nifty150.txt"),
    ("NIFTY200", PROJECT_ROOT / "datasets" / "tickers" / "nifty200.txt"),
)
"""Ordered user-maintained ticker files and labels for scanner universes."""


NEWS_PROVIDER = "alpha_vantage"
"""Identifier of the news provider used for informational signal enrichment."""

NEWS_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
"""Alpha Vantage API key read from the local environment or project ``.env`` file."""

CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY", "")
"""Currents News API key read from the local environment or project ``.env`` file."""

NEWS_LOOKBACK_HOURS = 48
"""Maximum age, in hours, of company news eligible for daily enrichment."""


ACCOUNT_SIZE = 100000.0
"""Account capital used by the application's fixed-risk position-sizing workflow."""

RISK_PER_TRADE_PERCENT = 1.0
"""Maximum account-risk percentage allocated to each eligible trade."""


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
    interval="1d",
    start_date=date(2020, 1, 1),
    end_date=None,
    output_directory=PROJECT_ROOT / "datasets" / "raw",
)
"""Initial daily-data download settings for a small Indian-equity universe."""
