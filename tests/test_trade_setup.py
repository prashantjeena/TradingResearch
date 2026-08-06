"""Unit tests for the Version 1 Trade Setup Engine."""

from __future__ import annotations

import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from analysis.confirmation import ConfirmationEvaluator
from analysis.trade_setup import TRADE_SETUP_COLUMNS, TradeSetupEvaluator, TradeSetupInputError
from analysis.trend import DowntrendEvaluator
from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS
from patterns.bullish_engulfing import BullishEngulfingDetector


def _dataset(
    entry_open: float | None = 120.0,
    confirmation_close: float = 109.0,
    ticker: str = "TEST.NS",
    index: list[int] | None = None,
) -> pd.DataFrame:
    """Create canonical source data with a qualifying pattern and confirmation.

    Args:
        entry_open: Day T+2 open, or None to omit the entry candle.
        confirmation_close: Day T+1 close.
        ticker: Ticker assigned to the generated observations.
        index: Optional source row indexes.

    Returns:
        Canonical data containing a pattern at T and confirmation at T+1.
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
    rows.append(["2024-01-07", 107.0, 112.0, 105.0, confirmation_close, confirmation_close, 1_100, ticker])
    if entry_open is not None:
        rows.append(["2024-01-08", entry_open, entry_open + 5.0, entry_open - 5.0, entry_open + 1.0, entry_open + 1.0, 1_200, ticker])
    return pd.DataFrame(rows, columns=CANONICAL_OHLCV_COLUMNS, index=index)


def _confirmation_patterns(dataset: pd.DataFrame) -> pd.DataFrame:
    """Run generated source data through Phases 3 through 5.

    Args:
        dataset: Canonical source data containing a generated pattern.

    Returns:
        Confirmation Engine output.
    """
    patterns = BullishEngulfingDetector().detect(dataset)
    downtrend_patterns = DowntrendEvaluator().evaluate(dataset, patterns)
    return ConfirmationEvaluator().evaluate(dataset, downtrend_patterns)


class TradeSetupEvaluatorTests(unittest.TestCase):
    """Verify deterministic, index-driven Version 1 setup calculations."""

    def setUp(self) -> None:
        """Create the evaluator shared by each test."""
        self.evaluator = TradeSetupEvaluator()

    def test_qualified_confirmation_creates_expected_setup(self) -> None:
        """A qualified confirmed pattern must use the next same-ticker open at T+2."""
        dataset = _dataset(index=[10, 20, 30, 40, 50, 60, 70, 80])

        result = self.evaluator.evaluate(dataset, _confirmation_patterns(dataset))

        setup = result.iloc[0]
        self.assertTrue(setup["TradeEligible"])
        self.assertEqual(setup["EntryDate"], "2024-01-08")
        self.assertEqual(setup["EntryIndex"], 80)
        self.assertEqual(setup["RawEntryPrice"], 120.0)
        self.assertAlmostEqual(setup["EntryFill"], 120.12)
        self.assertAlmostEqual(setup["StopPrice"], 95.0)
        self.assertAlmostEqual(setup["Risk"], 25.12)
        self.assertAlmostEqual(setup["RiskPercent"], (25.12 / 120.12) * 100)
        self.assertAlmostEqual(setup["TargetPrice"], 170.36)

    def test_downtrend_rejection_skips_setup_calculation(self) -> None:
        """A failed downtrend gate must leave all setup prices unset."""
        dataset = _dataset()
        patterns = _confirmation_patterns(dataset)
        patterns.loc[patterns.index[0], "DowntrendPassed"] = False

        result = self.evaluator.evaluate(dataset, patterns)

        self.assertFalse(result.iloc[0]["TradeEligible"])
        self.assertIsNone(result.iloc[0]["EntryFill"])
        self.assertEqual(result.iloc[0]["TradeRejectionReason"], "Pattern did not pass downtrend evaluation.")

    def test_confirmation_rejection_skips_setup_calculation(self) -> None:
        """A failed confirmation gate must leave all setup prices unset."""
        dataset = _dataset(confirmation_close=107.0)

        result = self.evaluator.evaluate(dataset, _confirmation_patterns(dataset))

        self.assertFalse(result.iloc[0]["TradeEligible"])
        self.assertIsNone(result.iloc[0]["EntryFill"])
        self.assertEqual(result.iloc[0]["TradeRejectionReason"], "Pattern did not pass confirmation evaluation.")

    def test_missing_entry_candle_rejects_setup(self) -> None:
        """A confirmed pattern without T+2 must be ineligible."""
        dataset = _dataset(entry_open=None)

        result = self.evaluator.evaluate(dataset, _confirmation_patterns(dataset))

        self.assertFalse(result.iloc[0]["TradeEligible"])
        self.assertEqual(result.iloc[0]["TradeRejectionReason"], "Entry candle unavailable.")

    def test_non_positive_risk_rejects_without_target(self) -> None:
        """A T+2 entry below the pattern low must be rejected before target setup."""
        dataset = _dataset(entry_open=90.0)

        result = self.evaluator.evaluate(dataset, _confirmation_patterns(dataset))

        setup = result.iloc[0]
        self.assertFalse(setup["TradeEligible"])
        self.assertLessEqual(setup["Risk"], 0)
        self.assertIsNone(setup["TargetPrice"])
        self.assertEqual(setup["TradeRejectionReason"], "Trade rejected: Risk must be greater than zero.")

    def test_source_indexes_match_pattern_confirmation_and_entry(self) -> None:
        """All source reference indexes must identify the intended event candles."""
        dataset = _dataset(index=[10, 20, 30, 40, 50, 60, 70, 80])

        result = self.evaluator.evaluate(dataset, _confirmation_patterns(dataset))

        setup = result.iloc[0]
        self.assertEqual(setup["PatternIndex"], 60)
        self.assertEqual(setup["ConfirmationIndex"], 70)
        self.assertEqual(setup["EntryIndex"], 80)

    def test_ticker_isolation_does_not_use_another_tickers_entry_candle(self) -> None:
        """Another ticker's following row cannot become Day T+2."""
        first_ticker = _dataset(entry_open=None, ticker="FIRST.NS")
        second_ticker = _dataset(entry_open=None, ticker="SECOND.NS").iloc[:1].copy()
        dataset = pd.concat([first_ticker, second_ticker], ignore_index=True)

        result = self.evaluator.evaluate(dataset, _confirmation_patterns(dataset))

        setup = result.loc[result["Ticker"] == "FIRST.NS"].iloc[0]
        self.assertFalse(setup["TradeEligible"])
        self.assertEqual(setup["TradeRejectionReason"], "Entry candle unavailable.")

    def test_invalid_confirmation_index_raises_error(self) -> None:
        """An unknown confirmation source index must not be used silently."""
        dataset = _dataset()
        patterns = _confirmation_patterns(dataset)
        patterns.loc[patterns.index[0], "ConfirmationIndex"] = 999

        with self.assertRaises(TradeSetupInputError):
            self.evaluator.evaluate(dataset, patterns)

    def test_evaluation_preserves_inputs_and_columns(self) -> None:
        """Setup evaluation must append only approved fields and not mutate inputs."""
        dataset = _dataset()
        patterns = _confirmation_patterns(dataset)
        original_dataset = dataset.copy(deep=True)
        original_patterns = patterns.copy(deep=True)

        result = self.evaluator.evaluate(dataset, patterns)

        self.assertEqual(tuple(result.columns), TRADE_SETUP_COLUMNS)
        assert_frame_equal(dataset, original_dataset)
        assert_frame_equal(patterns, original_patterns)

    def test_repeated_execution_is_deterministic(self) -> None:
        """Identical inputs must produce identical setup output."""
        dataset = _dataset()
        patterns = _confirmation_patterns(dataset)

        first_result = self.evaluator.evaluate(dataset, patterns)
        second_result = self.evaluator.evaluate(dataset, patterns)

        assert_frame_equal(first_result, second_result)


if __name__ == "__main__":
    unittest.main()
