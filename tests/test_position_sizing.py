"""Tests for Phase 22 fixed-risk position sizing."""

from __future__ import annotations

import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from portfolio.position_sizing import (
    POSITION_SIZING_COLUMNS,
    PositionSizer,
    PositionSizingError,
)


class PositionSizerTests(unittest.TestCase):
    """Verify deterministic sizing and recommendations for ranked signals."""

    def setUp(self) -> None:
        """Create a sizer and representative ranked signal input.

        Returns:
            None.

        Raises:
            None.
        """
        self.sizer = PositionSizer()
        self.signals = pd.DataFrame(
            {
                "Ticker": ["INFY.NS", "RELIANCE.NS"],
                "EntryFill": [100.0, 250.0],
                "StopPrice": [95.0, 240.0],
                "Risk": [5.0, 10.0],
                "RiskPercent": [5.0, 4.0],
                "Rank": [1, 2],
                "TradeEligible": [True, True],
            }
        )

    def test_basic_position_sizing(self) -> None:
        """Calculate all fixed-risk fields for an eligible trade.

        Returns:
            None.

        Raises:
            None.
        """
        result = self.sizer.size_positions(self.signals.iloc[[0]], 100_000.0, 1.0)

        row = result.iloc[0]
        self.assertEqual(row["RiskCapital"], 1000.0)
        self.assertEqual(row["RiskPerShare"], 5.0)
        self.assertEqual(row["Quantity"], 200)
        self.assertEqual(row["CapitalRequired"], 20_000.0)
        self.assertEqual(row["ActualRisk"], 1000.0)
        self.assertTrue(row["TradeRecommended"])
        self.assertIsNone(row["RecommendationReason"])

    def test_quantity_uses_exact_floor_calculation(self) -> None:
        """Round affordable quantity down to whole shares.

        Returns:
            None.

        Raises:
            None.
        """
        signals = self.signals.iloc[[0]].assign(Risk=6.0)

        result = self.sizer.size_positions(signals, 1_000.0, 1.0)

        self.assertEqual(result.iloc[0]["Quantity"], 1)
        self.assertEqual(result.iloc[0]["ActualRisk"], 6.0)

    def test_insufficient_risk_capital_does_not_recommend_trade(self) -> None:
        """Reject a trade when risk capital cannot buy one share of risk.

        Returns:
            None.

        Raises:
            None.
        """
        result = self.sizer.size_positions(self.signals.iloc[[0]], 100.0, 1.0)

        row = result.iloc[0]
        self.assertEqual(row["Quantity"], 0)
        self.assertFalse(row["TradeRecommended"])
        self.assertEqual(row["RecommendationReason"], "Risk too large for account.")

    def test_invalid_account_size_raises_error(self) -> None:
        """Reject zero or negative account capital.

        Returns:
            None.

        Raises:
            None.
        """
        with self.assertRaises(PositionSizingError):
            self.sizer.size_positions(self.signals, 0.0, 1.0)

    def test_invalid_risk_percent_raises_error(self) -> None:
        """Reject zero or negative risk-per-trade percentages.

        Returns:
            None.

        Raises:
            None.
        """
        with self.assertRaises(PositionSizingError):
            self.sizer.size_positions(self.signals, 100_000.0, 0.0)

    def test_invalid_eligible_trade_risk_raises_error(self) -> None:
        """Reject eligible trades with zero or negative per-share risk.

        Returns:
            None.

        Raises:
            None.
        """
        with self.assertRaises(PositionSizingError):
            self.sizer.size_positions(self.signals.assign(Risk=0.0), 100_000.0, 1.0)

    def test_ineligible_trade_remains_not_recommended(self) -> None:
        """Do not calculate or recommend a position for an ineligible trade.

        Returns:
            None.

        Raises:
            None.
        """
        signals = self.signals.iloc[[0]].assign(TradeEligible=False, Risk=0.0)

        result = self.sizer.size_positions(signals, 100_000.0, 1.0)

        row = result.iloc[0]
        self.assertFalse(row["TradeRecommended"])
        self.assertEqual(row["RecommendationReason"], "Trade was not eligible.")
        self.assertTrue(pd.isna(row["Quantity"]))

    def test_output_column_order_is_preserved(self) -> None:
        """Append only the documented sizing columns in documented order.

        Returns:
            None.

        Raises:
            None.
        """
        result = self.sizer.size_positions(self.signals, 100_000.0, 1.0)

        self.assertEqual(list(result.columns), [*self.signals.columns, *POSITION_SIZING_COLUMNS])

    def test_repeated_execution_is_deterministic(self) -> None:
        """Return identical sizing output for unchanged inputs.

        Returns:
            None.

        Raises:
            None.
        """
        first_result = self.sizer.size_positions(self.signals, 100_000.0, 1.0)
        second_result = self.sizer.size_positions(self.signals, 100_000.0, 1.0)

        assert_frame_equal(first_result, second_result)

    def test_size_positions_does_not_mutate_input(self) -> None:
        """Leave the ranked signal DataFrame unchanged.

        Returns:
            None.

        Raises:
            None.
        """
        original = self.signals.copy(deep=True)

        self.sizer.size_positions(self.signals, 100_000.0, 1.0)

        assert_frame_equal(self.signals, original)


if __name__ == "__main__":
    unittest.main()
