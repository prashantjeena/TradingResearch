"""Unit tests for the Bullish Engulfing detection engine."""

from __future__ import annotations

import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS
from patterns.bullish_engulfing import (
    DETECTION_COLUMNS,
    PATTERN_NAME,
    BullishEngulfingDetector,
    DetectionInputError,
)


def _dataset(rows: list[list[object]], index: list[int] | None = None) -> pd.DataFrame:
    """Build a canonical dataset for detector tests.

    Args:
        rows: OHLCV rows in canonical column order.
        index: Optional source row indexes.

    Returns:
        Canonical test dataset.
    """
    return pd.DataFrame(rows, columns=CANONICAL_OHLCV_COLUMNS, index=index)


class BullishEngulfingDetectorTests(unittest.TestCase):
    """Verify strict, ticker-safe, read-only pattern detection behavior."""

    def setUp(self) -> None:
        """Create the detector shared by each test."""
        self.detector = BullishEngulfingDetector()

    def test_detects_valid_pattern_and_preserves_metadata(self) -> None:
        """A strict body engulfing pattern must retain canonical and metadata fields."""
        dataset = _dataset(
            [
                ["2024-01-01", 110.0, 112.0, 99.0, 100.0, 100.0, 1000, "TEST.NS"],
                ["2024-01-02", 99.0, 115.0, 98.0, 114.0, 114.0, 1100, "TEST.NS"],
            ],
            index=[10, 11],
        )

        result = self.detector.detect(dataset)

        self.assertEqual(tuple(result.columns), DETECTION_COLUMNS)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["PatternName"], PATTERN_NAME)
        self.assertEqual(result.iloc[0]["PatternIndex"], 11)
        self.assertEqual(result.iloc[0]["PreviousDate"], "2024-01-01")

    def test_equality_does_not_qualify_as_pattern(self) -> None:
        """Any equality in the strict body conditions must reject the pattern."""
        dataset = _dataset(
            [
                ["2024-01-01", 110.0, 112.0, 99.0, 100.0, 100.0, 1000, "TEST.NS"],
                ["2024-01-02", 100.0, 115.0, 98.0, 114.0, 114.0, 1100, "TEST.NS"],
            ]
        )

        result = self.detector.detect(dataset)

        self.assertTrue(result.empty)

    def test_first_candle_of_each_ticker_cannot_qualify(self) -> None:
        """Previous-candle context must never cross ticker boundaries."""
        dataset = _dataset(
            [
                ["2024-01-01", 110.0, 112.0, 99.0, 100.0, 100.0, 1000, "FIRST.NS"],
                ["2024-01-01", 99.0, 115.0, 98.0, 114.0, 114.0, 1100, "SECOND.NS"],
            ]
        )

        result = self.detector.detect(dataset)

        self.assertTrue(result.empty)

    def test_detector_does_not_modify_input(self) -> None:
        """Detection must not mutate the validated source dataset."""
        dataset = _dataset(
            [
                ["2024-01-01", 110.0, 112.0, 99.0, 100.0, 100.0, 1000, "TEST.NS"],
                ["2024-01-02", 99.0, 115.0, 98.0, 114.0, 114.0, 1100, "TEST.NS"],
            ]
        )
        original_dataset = dataset.copy(deep=True)

        self.detector.detect(dataset)

        assert_frame_equal(dataset, original_dataset)

    def test_patterns_keep_source_chronological_order_without_reordering(self) -> None:
        """Detected rows must retain their input order and original row indexes."""
        dataset = _dataset(
            [
                ["2024-01-01", 110.0, 112.0, 99.0, 100.0, 100.0, 1000, "TEST.NS"],
                ["2024-01-02", 99.0, 115.0, 98.0, 114.0, 114.0, 1100, "TEST.NS"],
                ["2024-01-03", 120.0, 122.0, 109.0, 110.0, 110.0, 1200, "TEST.NS"],
                ["2024-01-04", 109.0, 125.0, 108.0, 124.0, 124.0, 1300, "TEST.NS"],
            ],
            index=[5, 8, 13, 21],
        )

        result = self.detector.detect(dataset)

        self.assertEqual(result["Date"].tolist(), ["2024-01-02", "2024-01-04"])
        self.assertEqual(result["PatternIndex"].tolist(), [8, 21])
        self.assertEqual(result.index.tolist(), [8, 21])

    def test_missing_required_column_raises_clear_error(self) -> None:
        """Detection must reject a dataset without the canonical fields."""
        dataset = _dataset(
            [["2024-01-01", 110.0, 112.0, 99.0, 100.0, 100.0, 1000, "TEST.NS"]]
        ).drop(columns="Volume")

        with self.assertRaises(DetectionInputError):
            self.detector.detect(dataset)


if __name__ == "__main__":
    unittest.main()
