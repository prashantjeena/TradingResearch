"""Focused global-date intraday watchlist command tests."""

from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal

from config import TICKER_UNIVERSE_FILES
from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS
from data.ticker_universe import load_ticker_universes
from intraday.watchlist import WATCHLIST_COLUMNS
from research.intraday_watchlist import build_watchlist, export_watchlist


class IntradayWatchlistCommandTests(unittest.TestCase):
    """Verify completed-data-only prototype watchlist generation."""

    trading_date = pd.Timestamp("2026-01-12")

    def _daily_data(self, ticker: str, direction: str, include_target: bool = False) -> pd.DataFrame:
        """Create one Friday setup with enough strict trend history."""
        dates = pd.bdate_range("2026-01-02", periods=6)
        if direction == "LONG":
            values = [(110, 111, 109, 109), (108, 109, 107, 107), (106, 107, 105, 105), (104, 105, 103, 103), (102, 103, 101, 100), (99, 104, 98, 103)]
        else:
            values = [(100, 101, 99, 100.5), (102, 103, 101, 102.5), (104, 105, 103, 104.5), (106, 107, 105, 106.5), (108, 111, 107, 110), (111, 112, 105, 107)]
        rows = [[day, open_, high, low, close, close, 1000, ticker] for day, (open_, high, low, close) in zip(dates, values, strict=True)]
        if include_target:
            rows.extend([[self.trading_date, 1, 2, 0, 1, 1, 1000, ticker], [self.trading_date + timedelta(days=1), 1, 2, 0, 1, 1, 1000, ticker]])
        data = pd.DataFrame(rows, columns=CANONICAL_OHLCV_COLUMNS)
        data["ConfirmationPassed"] = False
        data["Outcome"] = "LOSS"
        data["NetReturn"] = -99.0
        data["MFE"] = 999.0
        data["MAE"] = 999.0
        return data

    @staticmethod
    def _write(directory: Path, ticker: str, data: pd.DataFrame) -> None:
        """Write one canonical daily fixture in the application file name format."""
        data.to_csv(directory / f"{ticker.replace('.', '_')}_1d.csv", index=False)

    def _universes(self) -> pd.DataFrame:
        """Return ordered two-ticker synthetic universe metadata."""
        return pd.DataFrame({"Ticker": ["LONG.NS", "SHORT.NS"], "Universe": ["NIFTY50", "NIFTY100"]})

    def test_bullish_and_bearish_qualify_without_confirmation(self) -> None:
        """Qualified daily patterns must produce deterministic LONG then SHORT rows."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            self._write(directory, "LONG.NS", self._daily_data("LONG.NS", "LONG"))
            self._write(directory, "SHORT.NS", self._daily_data("SHORT.NS", "SHORT"))
            result = build_watchlist(self.trading_date, self._universes(), directory)
        self.assertEqual(result.setup_date, pd.Timestamp("2026-01-09"))
        self.assertEqual(result.evaluated_tickers, 2)
        self.assertEqual(result.watchlist["Side"].tolist(), ["LONG", "SHORT"])
        self.assertEqual(result.watchlist["PatternName"].tolist(), ["BULLISH_ENGULFING", "BEARISH_ENGULFING"])
        self.assertTrue(result.watchlist["TrendPassed"].all())

    def test_trend_failure_is_excluded(self) -> None:
        """A pattern without the required strict prior trend cannot enter the watchlist."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            failing = self._daily_data("LONG.NS", "LONG")
            failing.loc[2, ["High", "Low"]] = [120, 100]
            self._write(directory, "LONG.NS", failing)
            result = build_watchlist(self.trading_date, self._universes().iloc[:1], directory)
        self.assertTrue(result.watchlist.empty)

    def test_global_setup_date_blocks_stale_per_ticker_fallback(self) -> None:
        """A Thursday-only ticker is stale when Friday is the global setup date."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            current = self._daily_data("LONG.NS", "LONG")
            stale = self._daily_data("SHORT.NS", "SHORT").iloc[:-1]
            self._write(directory, "LONG.NS", current)
            self._write(directory, "SHORT.NS", stale)
            result = build_watchlist(self.trading_date, self._universes(), directory)
        self.assertEqual(result.setup_date, pd.Timestamp("2026-01-09"))
        self.assertEqual(result.stale_tickers, ("SHORT.NS (NIFTY100)",))
        self.assertEqual(result.evaluated_tickers, 1)
        self.assertEqual(result.watchlist["Ticker"].tolist(), ["LONG.NS"])

    def test_target_and_future_daily_candles_cannot_affect_qualification(self) -> None:
        """Partial target-day and future daily candles are excluded before detection."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = self._daily_data("LONG.NS", "LONG", include_target=True)
            original = source.copy(deep=True)
            self._write(directory, "LONG.NS", source)
            universe = self._universes().iloc[:1]
            result = build_watchlist(self.trading_date, universe, directory)
        self.assertEqual(result.setup_date, pd.Timestamp("2026-01-09"))
        self.assertEqual(result.watchlist["SetupDate"].tolist(), [pd.Timestamp("2026-01-09")])
        assert_frame_equal(source, original)

    def test_holiday_like_gap_uses_one_previous_actual_global_session(self) -> None:
        """A date gap resolves Friday rather than assuming a calendar predecessor."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            self._write(directory, "LONG.NS", self._daily_data("LONG.NS", "LONG"))
            result = build_watchlist(pd.Timestamp("2026-01-13"), self._universes().iloc[:1], directory)
        self.assertEqual(result.setup_date, pd.Timestamp("2026-01-09"))

    def test_empty_watchlist_exports_header_only_to_isolated_directory(self) -> None:
        """Zero candidates remain a valid header-only isolated export."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            data_directory = root / "raw"
            output_directory = root / "results" / "intraday_research" / "prototype" / "watchlists"
            data_directory.mkdir()
            self._write(data_directory, "LONG.NS", self._daily_data("LONG.NS", "LONG").iloc[:-1])
            result = build_watchlist(self.trading_date, self._universes().iloc[:1], data_directory)
            path = export_watchlist(result.watchlist, self.trading_date, output_directory)
            exported = pd.read_csv(path)
        self.assertEqual(tuple(result.watchlist.columns), WATCHLIST_COLUMNS)
        self.assertTrue(exported.empty)
        self.assertEqual(tuple(exported.columns), WATCHLIST_COLUMNS)
        self.assertIn("intraday_research", str(path))

    def test_configured_universe_remains_authoritative_195_tickers(self) -> None:
        """Configured text files—not raw CSV contents—define the scan universe."""
        self.assertEqual(len(load_ticker_universes(TICKER_UNIVERSE_FILES)), 195)


if __name__ == "__main__":
    unittest.main()
