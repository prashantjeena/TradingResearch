"""Unit tests for the Version 1 Trade Simulation Engine."""

from __future__ import annotations

import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from analysis.confirmation import ConfirmationEvaluator
from analysis.trade_setup import TradeSetupEvaluator
from analysis.trade_simulation import TRADE_SIMULATION_COLUMNS, TradeSimulationInputError, TradeSimulator
from analysis.trend import DowntrendEvaluator
from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS
from patterns.bullish_engulfing import BullishEngulfingDetector


def _dataset() -> pd.DataFrame:
    """Create source data with a qualifying pattern, confirmation, and five active candles.

    Returns:
        Canonical data where the pattern is Day T and row seven is Day T+2.
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


def _trade_setups(dataset: pd.DataFrame) -> pd.DataFrame:
    """Run generated source data through Phases 3 through 6.

    Args:
        dataset: Canonical source data containing the generated setup.

    Returns:
        Phase 6 trade setup output.
    """
    patterns = BullishEngulfingDetector().detect(dataset)
    downtrends = DowntrendEvaluator().evaluate(dataset, patterns)
    confirmations = ConfirmationEvaluator().evaluate(dataset, downtrends)
    return TradeSetupEvaluator().evaluate(dataset, confirmations)


class TradeSimulatorTests(unittest.TestCase):
    """Verify exact, deterministic Version 1 exit simulation behavior."""

    def setUp(self) -> None:
        """Create the simulator shared by each test."""
        self.simulator = TradeSimulator()

    def test_gap_stop_exits_at_open(self) -> None:
        """A post-entry open at or below stop must exit as a gap stop."""
        dataset = _dataset()
        dataset.loc[8, ["Open", "High", "Low", "Close", "Adj Close"]] = [90.0, 95.0, 85.0, 91.0, 91.0]

        result = self.simulator.simulate(dataset, _trade_setups(dataset))

        exit_row = result.iloc[0]
        self.assertEqual(exit_row["ExitReason"], "STOP_GAP_OPEN")
        self.assertEqual(exit_row["Outcome"], "LOSS")
        self.assertEqual(exit_row["HoldingDays"], 2)
        self.assertEqual(exit_row["ExitPrice"], 90.0)
        self.assertAlmostEqual(exit_row["ExitFill"], 89.91)

    def test_gap_target_exits_at_open(self) -> None:
        """A post-entry open at or above target must exit as a gap target."""
        dataset = _dataset()
        dataset.loc[8, ["Open", "High", "Low", "Close", "Adj Close"]] = [180.0, 185.0, 175.0, 181.0, 181.0]

        result = self.simulator.simulate(dataset, _trade_setups(dataset))

        exit_row = result.iloc[0]
        self.assertEqual(exit_row["ExitReason"], "TARGET_GAP_OPEN")
        self.assertEqual(exit_row["Outcome"], "WIN")
        self.assertEqual(exit_row["HoldingDays"], 2)
        self.assertEqual(exit_row["ExitPrice"], 180.0)

    def test_intraday_stop_exits_at_stop_price(self) -> None:
        """A low at stop without target reach must resolve as an intraday loss."""
        dataset = _dataset()
        dataset.loc[8, ["Open", "High", "Low", "Close", "Adj Close"]] = [120.0, 160.0, 90.0, 100.0, 100.0]

        result = self.simulator.simulate(dataset, _trade_setups(dataset))

        exit_row = result.iloc[0]
        self.assertEqual(exit_row["ExitReason"], "STOP_INTRADAY")
        self.assertEqual(exit_row["Outcome"], "LOSS")
        self.assertAlmostEqual(exit_row["ExitPrice"], exit_row["StopPrice"])

    def test_intraday_target_exits_at_target_price(self) -> None:
        """A high at target without stop reach must resolve as an intraday win."""
        dataset = _dataset()
        dataset.loc[8, ["Open", "High", "Low", "Close", "Adj Close"]] = [120.0, 180.0, 100.0, 175.0, 175.0]

        result = self.simulator.simulate(dataset, _trade_setups(dataset))

        exit_row = result.iloc[0]
        self.assertEqual(exit_row["ExitReason"], "TARGET_INTRADAY")
        self.assertEqual(exit_row["Outcome"], "WIN")
        self.assertAlmostEqual(exit_row["ExitPrice"], exit_row["TargetPrice"])

    def test_same_bar_ambiguity_always_resolves_as_loss(self) -> None:
        """A bar touching both barriers must use the frozen conservative stop policy."""
        dataset = _dataset()
        dataset.loc[8, ["Open", "High", "Low", "Close", "Adj Close"]] = [120.0, 180.0, 90.0, 130.0, 130.0]

        result = self.simulator.simulate(dataset, _trade_setups(dataset))

        exit_row = result.iloc[0]
        self.assertEqual(exit_row["ExitReason"], "SAME_BAR_AMBIGUITY_STOP")
        self.assertEqual(exit_row["Outcome"], "LOSS")
        self.assertAlmostEqual(exit_row["ExitPrice"], exit_row["StopPrice"])

    def test_expiry_uses_final_close_and_holding_day_five(self) -> None:
        """A trade without barriers through T+6 must expire at that close."""
        dataset = _dataset()
        dataset.loc[11, "Close"] = 130.0
        dataset.loc[11, "Adj Close"] = 130.0

        result = self.simulator.simulate(dataset, _trade_setups(dataset))

        exit_row = result.iloc[0]
        self.assertEqual(exit_row["ExitReason"], "EXPIRED")
        self.assertEqual(exit_row["Outcome"], "EXPIRED")
        self.assertEqual(exit_row["HoldingDays"], 5)
        self.assertEqual(exit_row["ExitPrice"], 130.0)
        self.assertAlmostEqual(exit_row["ExitFill"], 129.87)

    def test_observation_window_unavailable_does_not_expire(self) -> None:
        """Fewer than five same-ticker candles must leave the outcome unresolved."""
        dataset = _dataset().iloc[:-1].copy()

        result = self.simulator.simulate(dataset, _trade_setups(dataset))

        exit_row = result.iloc[0]
        self.assertIsNone(exit_row["Outcome"])
        self.assertEqual(exit_row["ExitReason"], "Observation window unavailable.")

    def test_cross_ticker_rows_do_not_complete_observation_window(self) -> None:
        """Another ticker's rows cannot supply missing active candles."""
        first_ticker = _dataset().iloc[:8].copy()
        second_ticker = _dataset().iloc[:4].copy()
        second_ticker["Ticker"] = "OTHER.NS"
        dataset = pd.concat([first_ticker, second_ticker], ignore_index=True)

        result = self.simulator.simulate(dataset, _trade_setups(dataset))

        exit_row = result.loc[result["Ticker"] == "TEST.NS"].iloc[0]
        self.assertIsNone(exit_row["Outcome"])
        self.assertEqual(exit_row["ExitReason"], "Observation window unavailable.")

    def test_invalid_entry_index_raises_error(self) -> None:
        """An unknown EntryIndex must not be resolved silently."""
        dataset = _dataset()
        setups = _trade_setups(dataset)
        setups.loc[setups.index[0], "EntryIndex"] = 999

        with self.assertRaises(TradeSimulationInputError):
            self.simulator.simulate(dataset, setups)

    def test_ineligible_trade_is_not_simulated(self) -> None:
        """Ineligible rows must receive only the required non-simulation reason."""
        dataset = _dataset()
        setups = _trade_setups(dataset)
        setups.loc[setups.index[0], "TradeEligible"] = False

        result = self.simulator.simulate(dataset, setups)

        exit_row = result.iloc[0]
        self.assertIsNone(exit_row["Outcome"])
        self.assertEqual(exit_row["ExitReason"], "Trade was not eligible.")

    def test_evaluation_preserves_inputs_and_columns(self) -> None:
        """Simulation must append only approved fields and not mutate inputs."""
        dataset = _dataset()
        setups = _trade_setups(dataset)
        original_dataset = dataset.copy(deep=True)
        original_setups = setups.copy(deep=True)

        result = self.simulator.simulate(dataset, setups)

        self.assertEqual(tuple(result.columns), TRADE_SIMULATION_COLUMNS)
        assert_frame_equal(dataset, original_dataset)
        assert_frame_equal(setups, original_setups)

    def test_repeated_execution_is_deterministic(self) -> None:
        """Identical source data and setups must yield identical exit records."""
        dataset = _dataset()
        setups = _trade_setups(dataset)

        first_result = self.simulator.simulate(dataset, setups)
        second_result = self.simulator.simulate(dataset, setups)

        assert_frame_equal(first_result, second_result)


if __name__ == "__main__":
    unittest.main()
