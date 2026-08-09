"""Tests for Phase 25 latest-trading-date signal filtering."""

from __future__ import annotations

import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from scanner.daily_scanner import DailySignalScanner


class DailySignalScannerTests(unittest.TestCase):
    """Verify read-only filtering for the supplied completed trading date."""

    def setUp(self) -> None:
        """Create a scanner and a representative completed performance frame.

        Returns:
            None.

        Raises:
            None.
        """
        self.scanner = DailySignalScanner()
        self.latest_trading_date = pd.Timestamp("2024-01-05 15:30:00")
        self.performance = pd.DataFrame(
            {
                "Ticker": ["TCS.NS", "RELIANCE.NS", "INFY.NS", "TCS.NS"],
                "EntryDate": pd.to_datetime(
                    [
                        "2024-01-03 09:15:00",
                        "2024-01-05 09:15:00",
                        "2024-01-05 09:15:00",
                        "2024-01-05 15:00:00",
                    ]
                ),
                "TradeEligible": [True, True, False, True],
                "EntryFill": [100.0, 200.0, 300.0, 110.0],
                "Outcome": ["WIN", None, None, None],
            }
        )

    def test_only_signals_matching_latest_trading_date_are_returned(self) -> None:
        """Keep eligible signals actionable on the supplied latest date only.

        Returns:
            None.

        Raises:
            None.
        """
        result = self.scanner.scan(self.performance, self.latest_trading_date)

        self.assertEqual(list(result.index), [1, 3])
        self.assertTrue(
            result["EntryDate"].dt.normalize().eq(self.latest_trading_date.normalize()).all()
        )

    def test_older_historical_signals_are_excluded(self) -> None:
        """Exclude eligible trades whose entry date precedes the supplied date.

        Returns:
            None.

        Raises:
            None.
        """
        result = self.scanner.scan(self.performance, self.latest_trading_date)

        self.assertNotIn("2024-01-03", set(result["EntryDate"].dt.strftime("%Y-%m-%d")))

    def test_no_eligible_signals_returns_empty_frame_with_identical_columns(self) -> None:
        """Return a schema-preserving empty result when no row qualifies.

        Returns:
            None.

        Raises:
            None.
        """
        performance = self.performance.assign(TradeEligible=False)

        result = self.scanner.scan(performance, self.latest_trading_date)

        self.assertTrue(result.empty)
        self.assertEqual(list(result.columns), list(performance.columns))

    def test_all_columns_and_values_are_preserved(self) -> None:
        """Retain every source column and value for matching signal rows.

        Returns:
            None.

        Raises:
            None.
        """
        result = self.scanner.scan(self.performance, self.latest_trading_date)
        expected = self.performance.loc[[1, 3]]

        assert_frame_equal(result, expected)

    def test_returned_frame_is_a_copy(self) -> None:
        """Ensure changing the returned frame cannot alter performance input.

        Returns:
            None.

        Raises:
            None.
        """
        result = self.scanner.scan(self.performance, self.latest_trading_date)
        result.loc[1, "EntryFill"] = 999.0

        self.assertEqual(self.performance.loc[1, "EntryFill"], 200.0)


if __name__ == "__main__":
    unittest.main()
