"""Yahoo Finance implementation of the market-data provider contract."""

from __future__ import annotations

from datetime import date

import pandas as pd
import yfinance as yf

from data.providers.base_provider import (
    CANONICAL_OHLCV_COLUMNS,
    MarketDataProvider,
    ProviderError,
)


class YFinanceProvider(MarketDataProvider):
    """Retrieve historical OHLCV data through the yfinance package."""

    def fetch_ohlcv(
        self,
        ticker: str,
        start_date: date,
        end_date: date | None,
        interval: str,
    ) -> pd.DataFrame:
        """Fetch and normalize one ticker's Yahoo Finance price history.

        Args:
            ticker: Yahoo Finance ticker symbol, for example ``"RELIANCE.NS"``.
            start_date: Inclusive first date requested from Yahoo Finance.
            end_date: Optional final date requested from Yahoo Finance.
            interval: Yahoo Finance interval, for example ``"1d"``.

        Returns:
            A DataFrame with the canonical OHLCV columns in the required order.
            ``Adj Close`` contains missing values when Yahoo Finance does not
            return that field.

        Raises:
            ProviderError: If Yahoo Finance returns no data or an incomplete
                OHLCV response.
        """
        try:
            raw_data = yf.download(
                tickers=ticker,
                start=start_date,
                end=end_date,
                interval=interval,
                auto_adjust=False,
                progress=False,
                threads=False,
            )
        except Exception as error:
            raise ProviderError(f"Failed to download {ticker} from yfinance.") from error

        if raw_data.empty:
            raise ProviderError(f"yfinance returned no data for {ticker}.")

        normalized_data = self._flatten_columns(raw_data)
        return self._build_canonical_frame(normalized_data, ticker)

    @staticmethod
    def _flatten_columns(raw_data: pd.DataFrame) -> pd.DataFrame:
        """Return a copy whose columns are yfinance price-field names.

        Args:
            raw_data: Unmodified DataFrame returned by yfinance.

        Returns:
            A DataFrame with one-level price-field columns.

        Raises:
            ProviderError: If yfinance returns an unsupported column layout.
        """
        flattened_data = raw_data.copy()
        if not isinstance(flattened_data.columns, pd.MultiIndex):
            return flattened_data

        expected_fields = {"Open", "High", "Low", "Close", "Adj Close", "Volume"}
        for level in range(flattened_data.columns.nlevels):
            level_values = flattened_data.columns.get_level_values(level)
            if expected_fields.intersection(level_values):
                flattened_data.columns = level_values
                return flattened_data

        raise ProviderError("yfinance returned an unsupported multi-level column layout.")

    @staticmethod
    def _build_canonical_frame(data: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """Map yfinance fields to the provider-independent OHLCV schema.

        Args:
            data: yfinance data with one-level price-field columns.
            ticker: Ticker to attach to every returned record.

        Returns:
            A canonical OHLCV DataFrame.

        Raises:
            ProviderError: If a required OHLCV field is absent.
        """
        required_fields = ("Open", "High", "Low", "Close", "Volume")
        missing_fields = [field for field in required_fields if field not in data.columns]
        if missing_fields:
            missing_text = ", ".join(missing_fields)
            raise ProviderError(f"yfinance response is missing required fields: {missing_text}.")

        adjusted_close = (
            data["Adj Close"]
            if "Adj Close" in data.columns
            else pd.Series(float("nan"), index=data.index, dtype="float64")
        )
        canonical_data = pd.DataFrame(
            {
                "Date": pd.to_datetime(data.index),
                "Open": data["Open"],
                "High": data["High"],
                "Low": data["Low"],
                "Close": data["Close"],
                "Adj Close": adjusted_close,
                "Volume": data["Volume"],
                "Ticker": ticker,
            }
        )
        return canonical_data.loc[:, CANONICAL_OHLCV_COLUMNS]
