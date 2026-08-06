"""Unit tests for the trade-level performance evaluation engine."""

from __future__ import annotations

import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from analysis.confirmation import ConfirmationEvaluator
from analysis.performance import PERFORMANCE_COLUMNS, PerformanceInputError, TradePerformanceEvaluator
from analysis.trade_setup import TradeSetupEvaluator
from analysis.trade_simulation import TradeSimulator
from analysis.trend import DowntrendEvaluator
from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS
from patterns.bullish_engulfing import BullishEngulfingDetector


def _dataset() -> pd.DataFrame:
    """Create canonical data with a qualified setup and five active candles.

    Returns:
        Canonical source data with one initial Bullish Engulfing pattern.
    """
    rows = [
        ["2024-01-01", 103.0, 110.0, 100.0, 102.0, 102.0, 1000, "TEST.NS"],
        ["2024-01-02", 103.0, 109.0, 99.0, 102.0, 102.0, 1000, "TEST.NS"],
        ["2024-01-03", 103.0, 111.0, 101.0, 102.0, 102.0, 1000, "TEST.NS"],
        ["2024-01-04", 103.0, 107.0, 97.0, 102.0, 102.0, 1000, "TEST.NS"],
        ["2024-01-05", 105.0, 106.0, 96.0, 100.0, 100.0, 1000, "TEST.NS"],
        ["2024-01-06", 99.0, 108.0, 95.0, 106.0, 106.0, 1000, "TEST.NS"],
        ["2024-01-07", 107.0, 112.0, 105.0, 109.0, 109.0, 1000, "TEST.NS"],
        ["2024-01-08", 120.0, 125.0, 115.0, 121.0, 121.0, 1000, "TEST.NS"],
        ["2024-01-09", 120.0, 125.0, 115.0, 121.0, 121.0, 1000, "TEST.NS"],
        ["2024-01-10", 120.0, 125.0, 115.0, 121.0, 121.0, 1000, "TEST.NS"],
        ["2024-01-11", 120.0, 125.0, 115.0, 121.0, 121.0, 1000, "TEST.NS"],
        ["2024-01-12", 120.0, 125.0, 115.0, 121.0, 121.0, 1000, "TEST.NS"],
    ]
    return pd.DataFrame(rows, columns=CANONICAL_OHLCV_COLUMNS)


def _simulated_trades(dataset: pd.DataFrame) -> pd.DataFrame:
    """Run generated source data through Phases 3 through 7.

    Args:
        dataset: Canonical source data containing the generated setup.

    Returns:
        Phase 7 simulation output.
    """
    patterns = BullishEngulfingDetector().detect(dataset)
    downtrends = DowntrendEvaluator().evaluate(dataset, patterns)
    confirmations = ConfirmationEvaluator().evaluate(dataset, downtrends)
    setups = TradeSetupEvaluator().evaluate(dataset, confirmations)
    return TradeSimulator().simulate(dataset, setups)


class TradePerformanceEvaluatorTests(unittest.TestCase):
    """Verify read-only trade-level return and excursion measurement."""

    def setUp(self) -> None:
        """Create the evaluator shared by each test."""
        self.evaluator = TradePerformanceEvaluator()

    def test_gross_and_net_return_formulas(self) -> None:
        """Resolved trades must use raw and execution-adjusted price formulas."""
        dataset = _dataset()
        dataset.loc[8, ["Open", "High", "Low", "Close", "Adj Close"]] = [120.0, 180.0, 100.0, 175.0, 175.0]
        trades = _simulated_trades(dataset)

        result = self.evaluator.evaluate(dataset, trades)
        trade = result.iloc[0]

        self.assertAlmostEqual(trade["GrossReturn"], ((trade["ExitPrice"] - trade["RawEntryPrice"]) / trade["RawEntryPrice"]) * 100)
        self.assertAlmostEqual(trade["NetReturn"], ((trade["ExitFill"] - trade["EntryFill"]) / trade["EntryFill"]) * 100)

    def test_winning_trade_mfe_uses_completed_candles_before_exit(self) -> None:
        """A target exit on Day 2 must use only the entry-day high for MFE."""
        dataset = _dataset()
        dataset.loc[8, ["Open", "High", "Low", "Close", "Adj Close"]] = [120.0, 180.0, 100.0, 175.0, 175.0]

        result = self.evaluator.evaluate(dataset, _simulated_trades(dataset))

        self.assertAlmostEqual(result.iloc[0]["MFE"], max(0.0, 125.0 - result.iloc[0]["EntryFill"]))

    def test_losing_trade_mae_uses_completed_candles_before_exit(self) -> None:
        """A stop exit on Day 2 must use only the entry-day low for MAE."""
        dataset = _dataset()
        dataset.loc[8, ["Open", "High", "Low", "Close", "Adj Close"]] = [120.0, 160.0, 90.0, 100.0, 100.0]

        result = self.evaluator.evaluate(dataset, _simulated_trades(dataset))

        self.assertAlmostEqual(result.iloc[0]["MAE"], max(0.0, result.iloc[0]["EntryFill"] - 115.0))

    def test_expired_trade_uses_all_five_active_candles_for_excursions(self) -> None:
        """Expired trades must include T+2 through T+6 for MFE and MAE."""
        dataset = _dataset()
        dataset.loc[11, ["High", "Low", "Close", "Adj Close"]] = [160.0, 100.0, 130.0, 130.0]

        result = self.evaluator.evaluate(dataset, _simulated_trades(dataset))
        trade = result.iloc[0]

        self.assertEqual(trade["Outcome"], "EXPIRED")
        self.assertAlmostEqual(trade["MFE"], max(0.0, 160.0 - trade["EntryFill"]))
        self.assertAlmostEqual(trade["MAE"], max(0.0, trade["EntryFill"] - 100.0))

    def test_entry_day_exit_has_zero_excursions(self) -> None:
        """An entry-day stop has no completed candle before exit."""
        dataset = _dataset()
        dataset.loc[7, "Low"] = 90.0

        result = self.evaluator.evaluate(dataset, _simulated_trades(dataset))

        self.assertEqual(result.iloc[0]["HoldingDays"], 1)
        self.assertEqual(result.iloc[0]["MFE"], 0.0)
        self.assertEqual(result.iloc[0]["MAE"], 0.0)

    def test_unresolved_trade_has_empty_performance_metrics(self) -> None:
        """Trades without an outcome must not receive derived metrics."""
        dataset = _dataset().iloc[:-1].copy()

        result = self.evaluator.evaluate(dataset, _simulated_trades(dataset))

        self.assertIsNone(result.iloc[0]["GrossReturn"])
        self.assertIsNone(result.iloc[0]["NetReturn"])
        self.assertIsNone(result.iloc[0]["MFE"])
        self.assertIsNone(result.iloc[0]["MAE"])

    def test_cross_ticker_rows_are_not_used_for_excursions(self) -> None:
        """Rows for another ticker cannot extend an unavailable trade window."""
        first_ticker = _dataset().iloc[:8].copy()
        second_ticker = _dataset().iloc[:4].copy()
        second_ticker["Ticker"] = "OTHER.NS"
        dataset = pd.concat([first_ticker, second_ticker], ignore_index=True)

        result = self.evaluator.evaluate(dataset, _simulated_trades(dataset))

        trade = result.loc[result["Ticker"] == "TEST.NS"].iloc[0]
        self.assertIsNone(trade["MFE"])
        self.assertIsNone(trade["MAE"])

    def test_invalid_entry_index_raises_error(self) -> None:
        """A resolved trade with an unknown EntryIndex must fail safely."""
        dataset = _dataset()
        dataset.loc[8, ["Open", "High", "Low", "Close", "Adj Close"]] = [120.0, 180.0, 100.0, 175.0, 175.0]
        trades = _simulated_trades(dataset)
        trades.loc[trades.index[0], "EntryIndex"] = 999

        with self.assertRaises(PerformanceInputError):
            self.evaluator.evaluate(dataset, trades)

    def test_evaluation_preserves_inputs_and_output_order(self) -> None:
        """Performance evaluation must append only approved fields without mutation."""
        dataset = _dataset()
        trades = _simulated_trades(dataset)
        original_dataset = dataset.copy(deep=True)
        original_trades = trades.copy(deep=True)

        result = self.evaluator.evaluate(dataset, trades)

        self.assertEqual(tuple(result.columns), PERFORMANCE_COLUMNS)
        assert_frame_equal(dataset, original_dataset)
        assert_frame_equal(trades, original_trades)

    def test_repeated_execution_is_deterministic(self) -> None:
        """Identical inputs must produce identical performance results."""
        dataset = _dataset()
        trades = _simulated_trades(dataset)

        first_result = self.evaluator.evaluate(dataset, trades)
        second_result = self.evaluator.evaluate(dataset, trades)

        assert_frame_equal(first_result, second_result)


if __name__ == "__main__":
    unittest.main()
