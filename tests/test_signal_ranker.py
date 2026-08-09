"""Tests for Phase 21 live-safe daily signal ranking."""

from __future__ import annotations

import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from ranking.signal_ranker import SignalRanker, SignalRankingError


class SignalRankerTests(unittest.TestCase):
    """Verify deterministic ranking based only on pre-entry signal information."""

    def setUp(self) -> None:
        """Create a ranker and representative signal data.

        Returns:
            None.

        Raises:
            None.
        """
        self.ranker = SignalRanker()
        self.signals = pd.DataFrame(
            {
                "Ticker": ["TCS.NS", "RELIANCE.NS", "INFY.NS"],
                "DowntrendPassed": [True, True, False],
                "ConfirmationPassed": [True, True, True],
                "RiskPercent": [2.0, 4.0, 3.0],
                "NewsAvailable": [True, True, True],
                "NewsSentiment": ["Positive", "Neutral", "Negative"],
                "Outcome": ["WIN", "LOSS", "EXPIRED"],
                "NetReturn": [12.0, -8.0, 1.0],
                "GrossReturn": [13.0, -7.0, 2.0],
                "MFE": [20.0, 1.0, 3.0],
                "MAE": [1.0, 9.0, 4.0],
            }
        )

    def test_empty_input_returns_empty_frame_with_ranking_columns(self) -> None:
        """Append ranking columns without adding rows to empty signals.

        Returns:
            None.

        Raises:
            None.
        """
        empty_signals = self.signals.iloc[0:0]

        result = self.ranker.rank(empty_signals)

        self.assertTrue(result.empty)
        self.assertEqual(list(result.columns), [*empty_signals.columns, "RankScore", "Rank"])

    def test_score_uses_only_live_safe_formula(self) -> None:
        """Apply base score, risk, confirmation, downtrend, and news adjustments.

        Returns:
            None.

        Raises:
            None.
        """
        result = self.ranker.rank(self.signals)

        self.assertEqual(list(result["RankScore"]), [115.0, 85.0, 75.0])
        self.assertEqual(list(result["Rank"]), [1, 2, 3])

    def test_positive_news_increases_score(self) -> None:
        """Add ten points for positive available news sentiment.

        Returns:
            None.

        Raises:
            None.
        """
        neutral = self.signals.iloc[[0]].assign(NewsSentiment="Neutral")
        positive = self.signals.iloc[[0]].assign(NewsSentiment="Positive")

        self.assertEqual(
            self.ranker.rank(positive).iloc[0]["RankScore"],
            self.ranker.rank(neutral).iloc[0]["RankScore"] + 10,
        )

    def test_negative_news_decreases_score(self) -> None:
        """Subtract ten points for negative available news sentiment.

        Returns:
            None.

        Raises:
            None.
        """
        neutral = self.signals.iloc[[0]].assign(NewsSentiment="Neutral")
        negative = self.signals.iloc[[0]].assign(NewsSentiment="Negative")

        self.assertEqual(
            self.ranker.rank(negative).iloc[0]["RankScore"],
            self.ranker.rank(neutral).iloc[0]["RankScore"] - 10,
        )

    def test_higher_risk_lowers_score(self) -> None:
        """Subtract ten ranking points for every additional risk-percent unit.

        Returns:
            None.

        Raises:
            None.
        """
        low_risk = self.signals.iloc[[0]].assign(RiskPercent=2.0)
        high_risk = self.signals.iloc[[0]].assign(RiskPercent=5.0)

        self.assertEqual(
            self.ranker.rank(low_risk).iloc[0]["RankScore"],
            self.ranker.rank(high_risk).iloc[0]["RankScore"] + 30,
        )

    def test_outcome_does_not_influence_score_or_rank(self) -> None:
        """Ignore the future trade outcome when ranking current signals.

        Returns:
            None.

        Raises:
            None.
        """
        self._assert_future_column_is_ignored("Outcome", ["LOSS", "WIN", "WIN"])

    def test_net_return_does_not_influence_score_or_rank(self) -> None:
        """Ignore future net return when ranking current signals.

        Returns:
            None.

        Raises:
            None.
        """
        self._assert_future_column_is_ignored("NetReturn", [-99.0, 99.0, 0.0])

    def test_gross_return_does_not_influence_score_or_rank(self) -> None:
        """Ignore future gross return when ranking current signals.

        Returns:
            None.

        Raises:
            None.
        """
        self._assert_future_column_is_ignored("GrossReturn", [-99.0, 99.0, 0.0])

    def test_mfe_does_not_influence_score_or_rank(self) -> None:
        """Ignore maximum favorable excursion when ranking current signals.

        Returns:
            None.

        Raises:
            None.
        """
        self._assert_future_column_is_ignored("MFE", [0.0, 100.0, -5.0])

    def test_mae_does_not_influence_score_or_rank(self) -> None:
        """Ignore maximum adverse excursion when ranking current signals.

        Returns:
            None.

        Raises:
            None.
        """
        self._assert_future_column_is_ignored("MAE", [100.0, 0.0, -5.0])

    def test_deterministic_ordering_uses_score_risk_then_ticker(self) -> None:
        """Break equal-score ties by risk percent and then ticker symbol.

        Returns:
            None.

        Raises:
            None.
        """
        signals = pd.DataFrame(
            {
                "Ticker": ["TCS.NS", "RELIANCE.NS", "INFY.NS"],
                "DowntrendPassed": [True, True, True],
                "ConfirmationPassed": [True, True, True],
                "RiskPercent": [3.0, 2.0, 2.0],
                "NewsSentiment": ["Positive", "Neutral", "Neutral"],
            }
        )

        result = self.ranker.rank(signals)

        self.assertEqual(list(result["Ticker"]), ["INFY.NS", "RELIANCE.NS", "TCS.NS"])
        self.assertEqual(list(result["Rank"]), [1, 2, 3])

    def test_source_columns_and_values_are_preserved(self) -> None:
        """Retain source columns and values while appending ranking metadata.

        Returns:
            None.

        Raises:
            None.
        """
        result = self.ranker.rank(self.signals)

        self.assertEqual(list(result.columns), [*self.signals.columns, "RankScore", "Rank"])
        assert_frame_equal(
            result.drop(columns=["RankScore", "Rank"]).sort_index(),
            self.signals.sort_index(),
        )

    def test_rank_does_not_mutate_input(self) -> None:
        """Leave the supplied signal DataFrame unchanged.

        Returns:
            None.

        Raises:
            None.
        """
        original = self.signals.copy(deep=True)

        self.ranker.rank(self.signals)

        assert_frame_equal(self.signals, original)

    def test_repeated_execution_is_deterministic(self) -> None:
        """Return identical ranks for repeated execution on unchanged input.

        Returns:
            None.

        Raises:
            None.
        """
        assert_frame_equal(self.ranker.rank(self.signals), self.ranker.rank(self.signals))

    def test_default_trend_field_preserves_bullish_rank_scores(self) -> None:
        """The optional trend field preserves default Bullish scores and ranks."""
        assert_frame_equal(
            self.ranker.rank(self.signals),
            self.ranker.rank(self.signals, trend_column="DowntrendPassed"),
        )

    def test_missing_required_column_raises_public_error(self) -> None:
        """Reject signals without a required live-safe ranking input.

        Returns:
            None.

        Raises:
            None.
        """
        with self.assertRaises(SignalRankingError):
            self.ranker.rank(self.signals.drop(columns="RiskPercent"))

    def _assert_future_column_is_ignored(self, column: str, replacement: list[object]) -> None:
        """Assert that changing a future-only column cannot affect ranking.

        Args:
            column: Future-only column to alter for the regression check.
            replacement: Replacement values for the selected column.

        Returns:
            None.

        Raises:
            None.
        """
        modified = self.signals.copy()
        modified[column] = replacement

        baseline = self.ranker.rank(self.signals)[["Ticker", "RankScore", "Rank"]]
        revised = self.ranker.rank(modified)[["Ticker", "RankScore", "Rank"]]
        assert_frame_equal(baseline, revised)


if __name__ == "__main__":
    unittest.main()
