"""Unit tests for the Version 1 confirmation evaluation engine."""

from __future__ import annotations

import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from analysis.confirmation import CONFIRMATION_COLUMNS, ConfirmationEvaluator, ConfirmationInputError
from analysis.trend import DowntrendEvaluator
from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS
from patterns.bullish_engulfing import BullishEngulfingDetector


def _dataset(
    confirmation_close: float | None,
    ticker: str = "TEST.NS",
    index: list[int] | None = None,
) -> pd.DataFrame:
    """Create a qualifying downtrend and final Bullish Engulfing sample.

    Args:
        confirmation_close: Close for Day T+1, or None to omit that candle.
        ticker: Ticker assigned to generated data.
        index: Optional source row indexes.

    Returns:
        Canonical data with a Bullish Engulfing pattern at Day T.
    """
    highs = [110.0, 109.0, 111.0, 107.0, 106.0, 108.0]
    lows = [100.0, 99.0, 101.0, 97.0, 96.0, 95.0]
    rows: list[list[object]] = []
    for position, (high, low) in enumerate(zip(highs, lows, strict=True)):
        date = f"2024-01-{position + 1:02d}"
        if position == 4:
            open_price, close_price = 105.0, 100.0
        elif position == 5:
            open_price, close_price = 99.0, 106.0
        else:
            open_price, close_price = 103.0, 102.0
        rows.append([date, open_price, high, low, close_price, close_price, 1_000, ticker])
    if confirmation_close is not None:
        rows.append(["2024-01-07", 107.0, 112.0, 105.0, confirmation_close, confirmation_close, 1_100, ticker])
    return pd.DataFrame(rows, columns=CANONICAL_OHLCV_COLUMNS, index=index)


def _downtrend_patterns(dataset: pd.DataFrame) -> pd.DataFrame:
    """Return Phase 4 output for a generated source dataset.

    Args:
        dataset: Canonical source data containing one generated pattern.

    Returns:
        Downtrend evaluator output.
    """
    return DowntrendEvaluator().evaluate(dataset, BullishEngulfingDetector().detect(dataset))


class ConfirmationEvaluatorTests(unittest.TestCase):
    """Verify strict, ticker-safe, read-only Version 1 confirmation behavior."""

    def setUp(self) -> None:
        """Create the evaluator shared by each test."""
        self.evaluator = ConfirmationEvaluator()

    def test_confirmation_succeeds_and_records_confirmation_index(self) -> None:
        """A next-day close above the pattern high must confirm strictly."""
        dataset = _dataset(109.0, index=[10, 20, 30, 40, 50, 60, 70])

        result = self.evaluator.evaluate(dataset, _downtrend_patterns(dataset))

        self.assertTrue(result.iloc[0]["ConfirmationPassed"])
        self.assertEqual(result.iloc[0]["ConfirmationDate"], "2024-01-07")
        self.assertEqual(result.iloc[0]["ConfirmationIndex"], 70)
        self.assertIsNone(result.iloc[0]["ConfirmationRejectionReason"])

    def test_confirmation_failure_records_required_reason(self) -> None:
        """A next-day close below the pattern high must fail confirmation."""
        dataset = _dataset(107.0)

        result = self.evaluator.evaluate(dataset, _downtrend_patterns(dataset))

        self.assertFalse(result.iloc[0]["ConfirmationPassed"])
        self.assertIsNone(result.iloc[0]["ConfirmationIndex"])
        self.assertEqual(result.iloc[0]["ConfirmationRejectionReason"], "Confirmation failed: Close[T+1] <= High[T].")

    def test_equality_does_not_confirm(self) -> None:
        """A next-day close equal to the pattern high must not confirm."""
        dataset = _dataset(108.0)

        result = self.evaluator.evaluate(dataset, _downtrend_patterns(dataset))

        self.assertFalse(result.iloc[0]["ConfirmationPassed"])
        self.assertEqual(result.iloc[0]["ConfirmationRejectionReason"], "Confirmation failed: Close[T+1] <= High[T].")

    def test_missing_next_same_ticker_candle_rejects(self) -> None:
        """A pattern at the final same-ticker row must report unavailable confirmation."""
        dataset = _dataset(None)

        result = self.evaluator.evaluate(dataset, _downtrend_patterns(dataset))

        self.assertFalse(result.iloc[0]["ConfirmationPassed"])
        self.assertIsNone(result.iloc[0]["ConfirmationDate"])
        self.assertIsNone(result.iloc[0]["ConfirmationIndex"])
        self.assertEqual(result.iloc[0]["ConfirmationRejectionReason"], "Confirmation candle unavailable.")

    def test_failed_downtrend_skips_confirmation(self) -> None:
        """A downtrend-rejected pattern must not evaluate its next candle."""
        dataset = _dataset(109.0)
        patterns = _downtrend_patterns(dataset)
        patterns.loc[patterns.index[0], "DowntrendPassed"] = False

        result = self.evaluator.evaluate(dataset, patterns)

        self.assertFalse(result.iloc[0]["ConfirmationPassed"])
        self.assertIsNone(result.iloc[0]["ConfirmationDate"])
        self.assertEqual(result.iloc[0]["ConfirmationRejectionReason"], "Pattern did not pass downtrend evaluation.")

    def test_ticker_isolation_does_not_use_another_tickers_candle(self) -> None:
        """A following row for another ticker cannot serve as confirmation."""
        first_ticker = _dataset(None, ticker="FIRST.NS")
        second_ticker = _dataset(None, ticker="SECOND.NS").iloc[:1].copy()
        dataset = pd.concat([first_ticker, second_ticker], ignore_index=True)

        result = self.evaluator.evaluate(dataset, _downtrend_patterns(dataset))

        first_result = result.loc[result["Ticker"] == "FIRST.NS"].iloc[0]
        self.assertFalse(first_result["ConfirmationPassed"])
        self.assertEqual(first_result["ConfirmationRejectionReason"], "Confirmation candle unavailable.")

    def test_invalid_pattern_index_raises_error(self) -> None:
        """Unknown PatternIndex values must not be resolved silently."""
        dataset = _dataset(109.0)
        patterns = _downtrend_patterns(dataset)
        patterns.loc[patterns.index[0], "PatternIndex"] = 999

        with self.assertRaises(ConfirmationInputError):
            self.evaluator.evaluate(dataset, patterns)

    def test_evaluation_preserves_inputs_and_column_order(self) -> None:
        """Confirmation must append only approved columns without input mutation."""
        dataset = _dataset(109.0)
        patterns = _downtrend_patterns(dataset)
        original_dataset = dataset.copy(deep=True)
        original_patterns = patterns.copy(deep=True)

        result = self.evaluator.evaluate(dataset, patterns)

        self.assertEqual(tuple(result.columns), CONFIRMATION_COLUMNS)
        assert_frame_equal(dataset, original_dataset)
        assert_frame_equal(patterns, original_patterns)

    def test_repeated_execution_is_deterministic(self) -> None:
        """Identical inputs must produce identical confirmation output."""
        dataset = _dataset(109.0)
        patterns = _downtrend_patterns(dataset)

        first_result = self.evaluator.evaluate(dataset, patterns)
        second_result = self.evaluator.evaluate(dataset, patterns)

        assert_frame_equal(first_result, second_result)


if __name__ == "__main__":
    unittest.main()
