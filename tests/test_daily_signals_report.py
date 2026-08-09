"""Tests for consolidated current-day signal report orchestration helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal

from main import (
    _DAILY_SIGNAL_COLUMNS,
    _consolidate_daily_signals,
    _daily_signal_rows,
    _export_daily_signals,
)


class DailySignalsReportTests(unittest.TestCase):
    """Verify projection, mixed-ticker ordering, and empty CSV behavior."""

    def _sized_positions(self, ticker: str, rank: int, score: float) -> pd.DataFrame:
        """Build one representative post-position-sizing signal row.

        Args:
            ticker: Signal ticker symbol.
            rank: Existing live-safe rank.
            score: Existing live-safe rank score.

        Returns:
            One-row post-sizing DataFrame.

        Raises:
            None.
        """
        return pd.DataFrame(
            {
                "Ticker": [ticker],
                "Rank": [rank],
                "RankScore": [score],
                "EntryDate": pd.to_datetime(["2024-01-05"]),
                "EntryFill": [100.0],
                "StopPrice": [95.0],
                "TargetPrice": [110.0],
                "RiskPercent": [5.0],
                "Quantity": [20],
                "CapitalRequired": [2000.0],
                "ConfirmationPassed": [True],
                "DowntrendPassed": [True],
                "NewsSentiment": ["Neutral"],
                "NewsHeadline": [None],
            }
        )

    def test_mixed_ticker_consolidation_preserves_universe_group_order(self) -> None:
        """Keep configured universe groups and each group's existing rank order.

        Returns:
            None.

        Raises:
            None.
        """
        reliance = _daily_signal_rows(
            self._sized_positions("RELIANCE.NS", 1, 100.0),
            "RELIANCE.NS",
            "NIFTY50",
        )
        infy = _daily_signal_rows(
            self._sized_positions("INFY.NS", 1, 110.0),
            "INFY.NS",
            "NIFTY100",
        )
        tcs = _daily_signal_rows(
            self._sized_positions("TCS.NS", 2, 120.0),
            "TCS.NS",
            "NIFTY150",
        )

        result = _consolidate_daily_signals([reliance, infy, tcs])

        self.assertEqual(list(result.columns), list(_DAILY_SIGNAL_COLUMNS))
        self.assertEqual(list(result["Universe"]), ["NIFTY50", "NIFTY100", "NIFTY150"])
        self.assertEqual(list(result["Ticker"]), ["RELIANCE.NS", "INFY.NS", "TCS.NS"])
        self.assertEqual(list(result["EntryPrice"]), [100.0, 100.0, 100.0])
        self.assertEqual(list(result["Shares"]), [20, 20, 20])

    def test_missing_ticker_column_is_appended_from_current_ticker(self) -> None:
        """Supply the current ticker when post-sizing data lacks that column.

        Returns:
            None.

        Raises:
            None.
        """
        sized_positions = self._sized_positions("INFY.NS", 1, 100.0).drop(columns="Ticker")

        result = _daily_signal_rows(sized_positions, "INFY.NS", "NIFTY50")

        self.assertEqual(list(result["Ticker"]), ["INFY.NS"])
        self.assertEqual(list(result["Universe"]), ["NIFTY50"])

    def test_empty_consolidated_report_exports_headers_only(self) -> None:
        """Write a readable header-only CSV when no current signals exist.

        Returns:
            None.

        Raises:
            None.
        """
        empty_report = _consolidate_daily_signals([])
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "results" / "daily_signals.csv"
            _export_daily_signals(empty_report, output_path)
            reloaded = pd.read_csv(output_path)

        self.assertTrue(reloaded.empty)
        self.assertEqual(list(reloaded.columns), list(_DAILY_SIGNAL_COLUMNS))

    def test_projection_does_not_mutate_sized_positions(self) -> None:
        """Leave post-sizing pipeline output untouched during CSV projection.

        Returns:
            None.

        Raises:
            None.
        """
        sized_positions = self._sized_positions("INFY.NS", 1, 100.0)
        original = sized_positions.copy(deep=True)

        _daily_signal_rows(sized_positions, "INFY.NS", "NIFTY50")

        assert_frame_equal(sized_positions, original)


if __name__ == "__main__":
    unittest.main()
