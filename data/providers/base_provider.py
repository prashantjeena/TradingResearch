"""Provider contract for historical OHLCV market data."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd


CANONICAL_OHLCV_COLUMNS: tuple[str, ...] = (
    "Date",
    "Open",
    "High",
    "Low",
    "Close",
    "Adj Close",
    "Volume",
    "Ticker",
)
"""Required column names and order for all provider responses."""


class ProviderError(RuntimeError):
    """Raised when a market-data provider cannot return usable data."""


class MarketDataProvider(ABC):
    """Abstract source of normalized historical OHLCV data.

    Implementations must return exactly ``CANONICAL_OHLCV_COLUMNS`` in the
    declared order. Providers without adjusted-close data must include the
    ``Adj Close`` column with missing values; they must not substitute close
    prices or fabricate adjusted values.
    """

    @abstractmethod
    def fetch_ohlcv(
        self,
        ticker: str,
        start_date: date,
        end_date: date | None,
        interval: str,
    ) -> pd.DataFrame:
        """Fetch normalized OHLCV data for one instrument.

        Args:
            ticker: Provider-recognized instrument identifier.
            start_date: Inclusive first date requested.
            end_date: Optional provider-defined final date requested.
            interval: Requested bar interval, such as ``"1d"``.

        Returns:
            A DataFrame containing the canonical OHLCV columns in their
            required order.

        Raises:
            ProviderError: If the provider cannot retrieve or normalize data.
        """
