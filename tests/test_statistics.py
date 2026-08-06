"""Unit tests for experiment-level statistics aggregation."""

from __future__ import annotations

import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from analysis.performance import PERFORMANCE_COLUMNS
from analysis.statistics import StatisticsEvaluator, StatisticsInputError


def _performance_results() -> pd.DataFrame:
    """Return representative Phase 8 rows for aggregate-statistics tests.

    Returns:
        DataFrame using the complete Phase 8 output schema.
    """
    defaults = {column: None for column in PERFORMANCE_COLUMNS}
    rows = [
        {
            **defaults,
            "Ticker": "AAA.NS", "DowntrendPassed": True, "ConfirmationPassed": True, "TradeEligible": True,
            "Outcome": "WIN", "GrossReturn": 20.0, "NetReturn": 18.0, "HoldingDays": 2,
            "MFE": 8.0, "MAE": 2.0, "RiskPercent": 10.0,
        },
        {
            **defaults,
            "Ticker": "AAA.NS", "DowntrendPassed": True, "ConfirmationPassed": True, "TradeEligible": True,
            "Outcome": "LOSS", "GrossReturn": -10.0, "NetReturn": -12.0, "HoldingDays": 3,
            "MFE": 3.0, "MAE": 8.0, "RiskPercent": 20.0,
        },
        {
            **defaults,
            "Ticker": "AAA.NS", "DowntrendPassed": True, "ConfirmationPassed": True, "TradeEligible": True,
            "Outcome": "EXPIRED", "GrossReturn": 5.0, "NetReturn": 4.0, "HoldingDays": 5,
            "MFE": 9.0, "MAE": 4.0, "RiskPercent": 5.0,
        },
        {
            **defaults,
            "Ticker": "AAA.NS", "DowntrendPassed": False, "ConfirmationPassed": False, "TradeEligible": False,
            "Outcome": None,
        },
        {
            **defaults,
            "Ticker": "BBB.NS", "DowntrendPassed": True, "ConfirmationPassed": True, "TradeEligible": True,
            "Outcome": "WIN", "GrossReturn": 10.0, "NetReturn": 8.0, "HoldingDays": 1,
            "MFE": 5.0, "MAE": 1.0, "RiskPercent": 5.0,
        },
    ]
    return pd.DataFrame(rows, columns=PERFORMANCE_COLUMNS)


class StatisticsEvaluatorTests(unittest.TestCase):
    """Verify exact Version 1 experiment-level performance aggregation."""

    def setUp(self) -> None:
        """Create the evaluator shared by each test."""
        self.evaluator = StatisticsEvaluator()

    def test_overall_and_resolved_trade_counts(self) -> None:
        """Overall, eligibility, and outcome counts must match performance rows."""
        result = self.evaluator.evaluate(_performance_results())

        self.assertEqual(result["TotalCandidatePatterns"], 5)
        self.assertEqual(result["ValidPatterns"], 4)
        self.assertEqual(result["ConfirmedPatterns"], 4)
        self.assertEqual(result["TradeEligible"], 4)
        self.assertEqual(result["Wins"], 2)
        self.assertEqual(result["Losses"], 1)
        self.assertEqual(result["ExpiredTrades"], 1)
        self.assertEqual(result["UnresolvedTrades"], 1)
        self.assertEqual(result["ResolvedTrades"], 3)

    def test_win_and_loss_rates_exclude_expired_trades(self) -> None:
        """Resolved rates must divide only wins and losses, never expired trades."""
        result = self.evaluator.evaluate(_performance_results())

        self.assertAlmostEqual(result["WinRateResolved"], 2 / 3)
        self.assertAlmostEqual(result["LossRateResolved"], 1 / 3)

    def test_averages_ignore_missing_values(self) -> None:
        """Averages must include present metrics and ignore unresolved rows."""
        result = self.evaluator.evaluate(_performance_results())

        self.assertAlmostEqual(result["AverageGrossReturn"], 6.25)
        self.assertAlmostEqual(result["AverageNetReturn"], 4.5)
        self.assertAlmostEqual(result["AverageHoldingDays"], 2.75)
        self.assertAlmostEqual(result["AverageMFE"], 6.25)
        self.assertAlmostEqual(result["AverageMAE"], 3.75)
        self.assertAlmostEqual(result["AverageRiskPercent"], 10.0)

    def test_average_reward_risk_ratio_uses_eligible_positive_risk_rows(self) -> None:
        """Reward-risk must omit unqualified and non-positive-risk observations."""
        result = self.evaluator.evaluate(_performance_results())

        self.assertAlmostEqual(result["AverageRewardRiskRatio"], 1.125)

    def test_ticker_summaries_are_nested_and_correct(self) -> None:
        """Each ticker must receive its requested independent summary values."""
        result = self.evaluator.evaluate(_performance_results())

        self.assertEqual(result["ResultsByTicker"]["AAA.NS"]["Patterns"], 4)
        self.assertEqual(result["ResultsByTicker"]["AAA.NS"]["Expired"], 1)
        self.assertAlmostEqual(result["ResultsByTicker"]["AAA.NS"]["WinRateResolved"], 0.5)
        self.assertEqual(result["ResultsByTicker"]["BBB.NS"]["Wins"], 1)
        self.assertAlmostEqual(result["ResultsByTicker"]["BBB.NS"]["AverageNetReturn"], 8.0)

    def test_empty_input_returns_zero_counts_and_missing_rates(self) -> None:
        """An empty valid-schema input must produce a stable empty experiment summary."""
        result = self.evaluator.evaluate(pd.DataFrame(columns=PERFORMANCE_COLUMNS))

        self.assertEqual(result["TotalCandidatePatterns"], 0)
        self.assertEqual(result["ResolvedTrades"], 0)
        self.assertIsNone(result["WinRateResolved"])
        self.assertIsNone(result["AverageNetReturn"])
        self.assertEqual(result["ResultsByTicker"], {})

    def test_missing_required_column_raises_error(self) -> None:
        """Partial performance schemas must be rejected before aggregation."""
        results = _performance_results().drop(columns="GrossReturn")

        with self.assertRaises(StatisticsInputError):
            self.evaluator.evaluate(results)

    def test_evaluation_does_not_mutate_input(self) -> None:
        """Statistics aggregation must remain read-only."""
        results = _performance_results()
        original_results = results.copy(deep=True)

        self.evaluator.evaluate(results)

        assert_frame_equal(results, original_results)

    def test_repeated_execution_is_deterministic(self) -> None:
        """Identical performance rows must produce identical summary dictionaries."""
        results = _performance_results()

        self.assertEqual(self.evaluator.evaluate(results), self.evaluator.evaluate(results))


if __name__ == "__main__":
    unittest.main()
