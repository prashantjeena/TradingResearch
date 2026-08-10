"""Authoritative ordered ticker-universe file loading."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd


LOGGER = logging.getLogger(__name__)


def load_tickers(ticker_file_path: Path) -> tuple[str, ...]:
    """Load non-empty, non-comment ticker lines in file order.

    Args:
        ticker_file_path: UTF-8 text file containing one ticker per line.

    Returns:
        Ordered ticker symbols.

    Raises:
        OSError: If the file cannot be read.
        UnicodeError: If the file is not valid UTF-8 text.
    """
    return tuple(
        ticker
        for line in ticker_file_path.read_text(encoding="utf-8").splitlines()
        if (ticker := line.strip()) and not ticker.startswith("#")
    )


def load_ticker_universes(
    universe_files: tuple[tuple[str, Path], ...],
) -> pd.DataFrame:
    """Load configured ticker buckets while retaining labels and order.

    Args:
        universe_files: Ordered ``(universe, ticker_file_path)`` pairs.

    Returns:
        A new DataFrame with ``Ticker`` and ``Universe`` columns. A failed
        universe file contributes no rows and does not prevent later files
        from loading.

    Raises:
        None.
    """
    records: list[dict[str, str]] = []
    for universe, ticker_file_path in universe_files:
        try:
            tickers = load_tickers(ticker_file_path)
        except (OSError, UnicodeError) as error:
            LOGGER.error("Could not load ticker file %s: %s", ticker_file_path, error)
            continue
        records.extend({"Ticker": ticker, "Universe": universe} for ticker in tickers)
    return pd.DataFrame(records, columns=["Ticker", "Universe"])
