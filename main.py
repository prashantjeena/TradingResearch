"""Command-line entry point for the historical-data download workflow."""

from __future__ import annotations

import logging
from importlib import import_module
from pathlib import Path

from config import DOWNLOAD_SETTINGS, LOGGING_SETTINGS, PROVIDER_SETTINGS
from data.providers.base_provider import MarketDataProvider, ProviderError
from logging_config import configure_logging


LOGGER = logging.getLogger(__name__)


def _load_provider(class_path: str) -> MarketDataProvider:
    """Instantiate the provider class named by a dotted import path.

    Args:
        class_path: Dotted class path, for example
            ``"data.providers.yfinance_provider.YFinanceProvider"``.

    Returns:
        An instance implementing ``MarketDataProvider``.

    Raises:
        ValueError: If the configured class path is invalid or does not name a
            ``MarketDataProvider`` implementation.
        ImportError: If the provider module cannot be imported.
        AttributeError: If the provider class is absent from its module.
    """
    module_path, separator, class_name = class_path.rpartition(".")
    if not separator or not module_path or not class_name:
        raise ValueError(f"Invalid provider class path: {class_path!r}")

    provider_module = import_module(module_path)
    provider_class = getattr(provider_module, class_name)
    if not isinstance(provider_class, type) or not issubclass(provider_class, MarketDataProvider):
        raise ValueError(f"Configured provider does not implement MarketDataProvider: {class_path}")

    return provider_class()


def _dataset_path(output_directory: Path, ticker: str, interval: str) -> Path:
    """Build a portable CSV file path for one ticker and interval.

    Args:
        output_directory: Directory configured for raw datasets.
        ticker: Provider-recognized ticker symbol.
        interval: Bar interval included in the output file name.

    Returns:
        The CSV path to use for the requested dataset.

    Raises:
        None.
    """
    safe_ticker = ticker.replace(".", "_").replace("/", "_").replace("\\", "_")
    return output_directory / f"{safe_ticker}_{interval}.csv"


def run() -> int:
    """Run the configured historical-data download workflow.

    Returns:
        Zero when every ticker downloads successfully; otherwise one.

    Raises:
        ValueError: If configuration identifies an invalid provider class.
        ImportError: If the configured provider module is unavailable.
        AttributeError: If the configured provider class is unavailable.
    """
    configure_logging(LOGGING_SETTINGS)
    provider = _load_provider(PROVIDER_SETTINGS.class_path)
    DOWNLOAD_SETTINGS.output_directory.mkdir(parents=True, exist_ok=True)

    failures = 0
    for ticker in DOWNLOAD_SETTINGS.tickers:
        try:
            dataset = provider.fetch_ohlcv(
                ticker=ticker,
                start_date=DOWNLOAD_SETTINGS.start_date,
                end_date=DOWNLOAD_SETTINGS.end_date,
                interval=DOWNLOAD_SETTINGS.interval,
            )
            output_path = _dataset_path(
                DOWNLOAD_SETTINGS.output_directory,
                ticker,
                DOWNLOAD_SETTINGS.interval,
            )
            dataset.to_csv(output_path, index=False)
            LOGGER.info("Saved %s rows for %s to %s", len(dataset), ticker, output_path)
        except ProviderError as error:
            failures += 1
            LOGGER.error("Could not download %s: %s", ticker, error)

    return 1 if failures else 0


def main() -> None:
    """Execute the application and expose its exit status to the shell.

    Returns:
        None.

    Raises:
        SystemExit: Always, with the status returned by ``run``.
    """
    raise SystemExit(run())


if __name__ == "__main__":
    main()
