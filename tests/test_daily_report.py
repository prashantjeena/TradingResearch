"""Tests for Phase 18 consolidated daily report projection."""

from __future__ import annotations

import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from reporting.daily_report import DAILY_REPORT_COLUMNS, DailyReportError, DailyReportGenerator


class DailyReportGeneratorTests(unittest.TestCase):
    """Verify schema-only daily report generation without input mutation."""

    def setUp(self) -> None:
        """Create a generator and ranked signal data in a non-report order.

        Returns:
            None.

        Raises:
            None.
        """
        self.generator = DailyReportGenerator()
        self.ranked_signals = pd.DataFrame(
            {
                "Ticker": ["INFY.NS", "RELIANCE.NS"],
                "RankScore": [10, 8],
                "EntryDate": pd.to_datetime(["2024-01-10", "2024-01-09"]),
                "EntryFill": [1500.5, 2500.25],
                "StopPrice": [1450.0, 2400.0],
                "TargetPrice": [1600.0, 2700.0],
                "Risk": [50.5, 100.25],
                "RiskPercent": [3.37, 4.01],
                "Rank": [1, 2],
                "SourceColumn": ["retained only in input", "retained only in input"],
            }
        )

    def test_output_columns_match_the_public_schema_exactly(self) -> None:
        """Return only the report columns in the required order.

        Returns:
            None.

        Raises:
            None.
        """
        result = self.generator.generate(self.ranked_signals)

        self.assertEqual(list(result.columns), list(DAILY_REPORT_COLUMNS))

    def test_values_are_copied_unchanged(self) -> None:
        """Copy report values without formatting, rounding, or calculation.

        Returns:
            None.

        Raises:
            None.
        """
        result = self.generator.generate(self.ranked_signals)
        expected = self.ranked_signals.loc[:, DAILY_REPORT_COLUMNS]

        assert_frame_equal(result, expected)

    def test_row_order_is_preserved(self) -> None:
        """Retain the exact ranked-signal row order.

        Returns:
            None.

        Raises:
            None.
        """
        result = self.generator.generate(self.ranked_signals)

        self.assertEqual(list(result.index), list(self.ranked_signals.index))
        self.assertEqual(list(result["Ticker"]), ["INFY.NS", "RELIANCE.NS"])

    def test_empty_input_returns_empty_report_with_correct_schema(self) -> None:
        """Produce a schema-correct empty report for empty ranked signals.

        Returns:
            None.

        Raises:
            None.
        """
        result = self.generator.generate(self.ranked_signals.iloc[0:0])

        self.assertTrue(result.empty)
        self.assertEqual(list(result.columns), list(DAILY_REPORT_COLUMNS))

    def test_missing_required_columns_raise_public_error(self) -> None:
        """Reject incomplete ranked signal input.

        Returns:
            None.

        Raises:
            None.
        """
        with self.assertRaises(DailyReportError):
            self.generator.generate(self.ranked_signals.drop(columns="TargetPrice"))

    def test_generate_does_not_mutate_input(self) -> None:
        """Leave the ranked signal DataFrame unchanged.

        Returns:
            None.

        Raises:
            None.
        """
        original = self.ranked_signals.copy(deep=True)

        self.generator.generate(self.ranked_signals)

        assert_frame_equal(self.ranked_signals, original)

    def test_repeated_execution_is_deterministic(self) -> None:
        """Return identical report DataFrames for identical ranked input.

        Returns:
            None.

        Raises:
            None.
        """
        first_result = self.generator.generate(self.ranked_signals)
        second_result = self.generator.generate(self.ranked_signals)

        assert_frame_equal(first_result, second_result)


if __name__ == "__main__":
    unittest.main()
