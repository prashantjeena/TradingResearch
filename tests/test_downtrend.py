"""Unit tests for the Version 1 downtrend evaluation engine."""

from __future__ import annotations

import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from analysis.trend import DOWNTREND_COLUMNS, DowntrendEvaluator, DowntrendInputError
from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS
from patterns.bullish_engulfing import BullishEngulfingDetector


def _dataset(
    highs: list[float],
    lows: list[float],
    ticker: str = "TEST.NS",
    index: list[int] | None = None,
) -> pd.DataFrame:
    """Create data with a Bullish Engulfing pattern at its final candle.

    Args:
        highs: High values for all candles, including the pattern candle.
        lows: Low values for all candles, including the pattern candle.
        ticker: Ticker assigned to the generated candles.
        index: Optional source row indexes.

    Returns:
        Canonical data whose final row is a Bullish Engulfing pattern.
    """
    rows: list[list[object]] = []
    for position, (high, low) in enumerate(zip(highs, lows, strict=True)):
        date = f"2024-01-{position + 1:02d}"
        if position == len(highs) - 2:
            open_price, close_price = 105.0, 100.0
        elif position == len(highs) - 1:
            open_price, close_price = 99.0, 106.0
        else:
            open_price, close_price = 103.0, 102.0
        rows.append([date, open_price, high, low, close_price, close_price, 1_000, ticker])
    return pd.DataFrame(rows, columns=CANONICAL_OHLCV_COLUMNS, index=index)


class DowntrendEvaluatorTests(unittest.TestCase):
    """Verify exact, pattern-index-driven Version 1 downtrend decisions."""

    def setUp(self) -> None:
        """Create shared detector and evaluator instances."""
        self.detector = BullishEngulfingDetector()
        self.evaluator = DowntrendEvaluator()

    def test_three_of_four_comparisons_passes(self) -> None:
        """Exactly three lower-high/lower-low comparisons must pass the rule."""
        dataset = _dataset(
            highs=[110.0, 109.0, 111.0, 107.0, 106.0, 108.0],
            lows=[100.0, 99.0, 101.0, 97.0, 96.0, 95.0],
        )

        result = self.evaluator.evaluate(dataset, self.detector.detect(dataset))

        self.assertTrue(result.iloc[0]["DowntrendPassed"])
        self.assertIsNone(result.iloc[0]["DowntrendRejectionReason"])

    def test_two_of_four_comparisons_rejects_with_clear_reason(self) -> None:
        """Fewer than three qualifying comparisons must reject the pattern."""
        dataset = _dataset(
            highs=[110.0, 109.0, 111.0, 112.0, 106.0, 108.0],
            lows=[100.0, 99.0, 101.0, 102.0, 96.0, 95.0],
        )

        result = self.evaluator.evaluate(dataset, self.detector.detect(dataset))

        self.assertFalse(result.iloc[0]["DowntrendPassed"])
        self.assertEqual(
            result.iloc[0]["DowntrendRejectionReason"],
            "Downtrend rejected: 2 of 4 lower-high/lower-low comparisons; requires at least 3.",
        )

    def test_insufficient_prior_candles_rejects(self) -> None:
        """A detected pattern without five prior candles must be rejected."""
        dataset = _dataset(highs=[110.0, 112.0], lows=[100.0, 98.0])

        result = self.evaluator.evaluate(dataset, self.detector.detect(dataset))

        self.assertFalse(result.iloc[0]["DowntrendPassed"])
        self.assertEqual(
            result.iloc[0]["DowntrendRejectionReason"],
            "Insufficient prior candles: requires five candles from T-5 through T-1.",
        )

    def test_pattern_candle_is_not_used_for_downtrend(self) -> None:
        """Changing Day T High and Low must not change the prior-candle result."""
        dataset = _dataset(
            highs=[110.0, 109.0, 111.0, 107.0, 106.0, 108.0],
            lows=[100.0, 99.0, 101.0, 97.0, 96.0, 95.0],
        )
        altered_dataset = dataset.copy(deep=True)
        altered_dataset.loc[altered_dataset.index[-1], "High"] = 200.0
        altered_dataset.loc[altered_dataset.index[-1], "Low"] = 1.0

        original_result = self.evaluator.evaluate(dataset, self.detector.detect(dataset))
        altered_result = self.evaluator.evaluate(altered_dataset, self.detector.detect(altered_dataset))

        self.assertEqual(original_result.iloc[0]["DowntrendPassed"], altered_result.iloc[0]["DowntrendPassed"])

    def test_evaluation_preserves_detector_columns_order_and_inputs(self) -> None:
        """Evaluation must append only metadata and leave both inputs unchanged."""
        dataset = _dataset(
            highs=[110.0, 109.0, 111.0, 107.0, 106.0, 108.0],
            lows=[100.0, 99.0, 101.0, 97.0, 96.0, 95.0],
            index=[10, 20, 30, 40, 50, 60],
        )
        patterns = self.detector.detect(dataset)
        original_dataset = dataset.copy(deep=True)
        original_patterns = patterns.copy(deep=True)

        result = self.evaluator.evaluate(dataset, patterns)

        self.assertEqual(tuple(result.columns), DOWNTREND_COLUMNS)
        assert_frame_equal(dataset, original_dataset)
        assert_frame_equal(patterns, original_patterns)

    def test_ticker_histories_do_not_cross(self) -> None:
        """A ticker's prior candles must not be supplied by another ticker."""
        first_ticker = _dataset(highs=[110.0, 112.0], lows=[100.0, 98.0], ticker="FIRST.NS")
        second_ticker = _dataset(
            highs=[210.0, 209.0, 211.0, 207.0, 206.0, 208.0],
            lows=[200.0, 199.0, 201.0, 197.0, 196.0, 195.0],
            ticker="SECOND.NS",
        )
        dataset = pd.concat([first_ticker, second_ticker], ignore_index=True)
        patterns = self.detector.detect(dataset)

        result = self.evaluator.evaluate(dataset, patterns)

        first_result = result.loc[result["Ticker"] == "FIRST.NS"].iloc[0]
        second_result = result.loc[result["Ticker"] == "SECOND.NS"].iloc[0]
        self.assertFalse(first_result["DowntrendPassed"])
        self.assertTrue(second_result["DowntrendPassed"])

    def test_mismatched_pattern_metadata_raises_error(self) -> None:
        """Pattern metadata from another source must not be evaluated silently."""
        dataset = _dataset(
            highs=[110.0, 109.0, 111.0, 107.0, 106.0, 108.0],
            lows=[100.0, 99.0, 101.0, 97.0, 96.0, 95.0],
        )
        patterns = self.detector.detect(dataset)
        patterns.loc[patterns.index[0], "Ticker"] = "OTHER.NS"

        with self.assertRaises(DowntrendInputError):
            self.evaluator.evaluate(dataset, patterns)


if __name__ == "__main__":
    unittest.main()
