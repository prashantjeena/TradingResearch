"""Read-only Version 1 exit simulation for eligible trade setups."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from analysis.trade_setup import TRADE_SETUP_COLUMNS
from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS


TRADE_SIMULATION_FIELDS: tuple[str, ...] = (
    "ExitDate",
    "ExitIndex",
    "ExitReason",
    "ExitPrice",
    "ExitFill",
    "Outcome",
    "HoldingDays",
)
"""Fields appended by the Version 1 Trade Simulation Engine."""

TRADE_SIMULATION_COLUMNS: tuple[str, ...] = (*TRADE_SETUP_COLUMNS, *TRADE_SIMULATION_FIELDS)
"""Required output columns and order after Version 1 trade simulation."""


class TradeSimulationInputError(ValueError):
    """Raised when eligible trade setup references cannot be simulated safely."""


class TradeSimulator:
    """Simulate only Version 1 exits over the fixed five-session window."""

    def simulate(self, dataset: pd.DataFrame, trade_setups: pd.DataFrame) -> pd.DataFrame:
        """Append deterministic exit data without modifying either input DataFrame.

        Eligible trades inspect only the five immediate same-ticker candles from
        EntryIndex through T+6. Ineligible rows are not simulated.

        Args:
            dataset: Validated canonical OHLCV source data, ordered within each
                ticker and carrying a unique DataFrame index.
            trade_setups: Exact output from ``TradeSetupEvaluator`` for the
                same dataset.

        Returns:
            A new DataFrame preserving all Phase 6 columns and appending the
            fields specified by ``TRADE_SIMULATION_FIELDS``.

        Raises:
            TradeSimulationInputError: If required columns are unavailable or
                an eligible setup's EntryIndex conflicts with source data.
        """
        self._validate_inputs(dataset, trade_setups)
        source_positions, ticker_positions, ticker_ranks = self._build_source_lookup(dataset)
        simulation_records: list[tuple[object | None, ...]] = []

        for setup in trade_setups.itertuples(index=False):
            if not bool(setup.TradeEligible):
                simulation_records.append((None, None, "Trade was not eligible.", None, None, None, None))
                continue

            entry_position = source_positions.get(setup.EntryIndex)
            if entry_position is None:
                raise TradeSimulationInputError(f"EntryIndex does not exist in dataset: {setup.EntryIndex!r}")

            entry_candle = dataset.iloc[entry_position]
            if (
                entry_candle["Ticker"] != setup.Ticker
                or entry_candle["Date"] != setup.EntryDate
                or float(entry_candle["Open"]) != float(setup.RawEntryPrice)
            ):
                raise TradeSimulationInputError(
                    f"Entry metadata does not match dataset row at EntryIndex {setup.EntryIndex!r}."
                )

            ticker_position = ticker_ranks[entry_position]
            same_ticker_positions = ticker_positions[setup.Ticker]
            observation_positions = same_ticker_positions[ticker_position:ticker_position + 5]
            if len(observation_positions) < 5:
                simulation_records.append((None, None, "Observation window unavailable.", None, None, None, None))
                continue

            simulation_records.append(self._simulate_window(dataset, observation_positions, setup))

        result = trade_setups.copy()
        simulation_frame = pd.DataFrame(simulation_records, columns=TRADE_SIMULATION_FIELDS, index=result.index)
        for field in TRADE_SIMULATION_FIELDS:
            result[field] = simulation_frame[field]
        return result.loc[:, TRADE_SIMULATION_COLUMNS]

    @staticmethod
    def _simulate_window(
        dataset: pd.DataFrame,
        observation_positions: list[int],
        setup: object,
    ) -> tuple[object | None, ...]:
        """Evaluate one complete five-candle observation window in priority order.

        Args:
            dataset: Canonical source data.
            observation_positions: Five same-ticker row positions from T+2 to
                T+6, inclusive.
            setup: Eligible trade setup row supplied by ``itertuples``.

        Returns:
            Values matching ``TRADE_SIMULATION_FIELDS`` for the resolved exit.
        """
        for holding_days, source_position in enumerate(observation_positions, start=1):
            candle = dataset.iloc[source_position]
            if candle["Open"] <= setup.StopPrice:
                return TradeSimulator._exit_record(candle, source_position, dataset, "STOP_GAP_OPEN", candle["Open"], "LOSS", holding_days)
            if candle["Open"] >= setup.TargetPrice:
                return TradeSimulator._exit_record(candle, source_position, dataset, "TARGET_GAP_OPEN", candle["Open"], "WIN", holding_days)
            if candle["Low"] <= setup.StopPrice and candle["High"] >= setup.TargetPrice:
                return TradeSimulator._exit_record(candle, source_position, dataset, "SAME_BAR_AMBIGUITY_STOP", setup.StopPrice, "LOSS", holding_days)
            if candle["Low"] <= setup.StopPrice and candle["High"] < setup.TargetPrice:
                return TradeSimulator._exit_record(candle, source_position, dataset, "STOP_INTRADAY", setup.StopPrice, "LOSS", holding_days)
            if candle["High"] >= setup.TargetPrice and candle["Low"] > setup.StopPrice:
                return TradeSimulator._exit_record(candle, source_position, dataset, "TARGET_INTRADAY", setup.TargetPrice, "WIN", holding_days)

        expiry_position = observation_positions[-1]
        expiry_candle = dataset.iloc[expiry_position]
        return TradeSimulator._exit_record(expiry_candle, expiry_position, dataset, "EXPIRED", expiry_candle["Close"], "EXPIRED", 5)

    @staticmethod
    def _exit_record(
        candle: pd.Series,
        source_position: int,
        dataset: pd.DataFrame,
        reason: str,
        exit_price: float,
        outcome: str,
        holding_days: int,
    ) -> tuple[object | None, ...]:
        """Build one Version 1 exit record with adverse exit fill.

        Args:
            candle: Source candle on which the exit occurs.
            source_position: Integer source-row position of the exit candle.
            dataset: Canonical source data used to recover original index.
            reason: Stable reason describing the resolved exit.
            exit_price: Raw exit price dictated by the frozen rules.
            outcome: WIN, LOSS, or EXPIRED.
            holding_days: Active-session count including the entry day.

        Returns:
            Values matching ``TRADE_SIMULATION_FIELDS``.
        """
        raw_exit_price = float(exit_price)
        return (
            candle["Date"],
            dataset.index[source_position],
            reason,
            raw_exit_price,
            raw_exit_price * 0.999,
            outcome,
            holding_days,
        )

    @staticmethod
    def _build_source_lookup(
        dataset: pd.DataFrame,
    ) -> tuple[dict[object, int], dict[object, list[int]], dict[int, int]]:
        """Build index and per-ticker position lookups without simulation output.

        Args:
            dataset: Validated canonical source data with a unique index.

        Returns:
            Source-index positions, same-ticker positions, and ticker-relative
            ranks for each source position.
        """
        source_positions: dict[object, int] = {}
        ticker_positions: dict[object, list[int]] = defaultdict(list)
        ticker_ranks: dict[int, int] = {}
        for source_position, (source_index, ticker) in enumerate(zip(dataset.index, dataset["Ticker"], strict=True)):
            source_positions[source_index] = source_position
            ticker_ranks[source_position] = len(ticker_positions[ticker])
            ticker_positions[ticker].append(source_position)
        return source_positions, dict(ticker_positions), ticker_ranks

    @staticmethod
    def _validate_inputs(dataset: pd.DataFrame, trade_setups: pd.DataFrame) -> None:
        """Validate structural requirements before any simulation occurs.

        Args:
            dataset: Canonical OHLCV source data.
            trade_setups: Phase 6 output to simulate.

        Returns:
            None.

        Raises:
            TradeSimulationInputError: If input columns are missing or source
                indexes required for eligible setups are unavailable.
        """
        TradeSimulator._require_unique_columns(dataset, CANONICAL_OHLCV_COLUMNS, "dataset")
        TradeSimulator._require_unique_columns(trade_setups, TRADE_SETUP_COLUMNS, "trade_setups")
        if not dataset.index.is_unique:
            raise TradeSimulationInputError("Dataset index must be unique to resolve EntryIndex values.")
        if trade_setups["TradeEligible"].isna().any():
            raise TradeSimulationInputError("TradeEligible must not contain missing values.")
        eligible_missing_entry = trade_setups["TradeEligible"] & trade_setups["EntryIndex"].isna()
        if eligible_missing_entry.any():
            raise TradeSimulationInputError("Eligible trades must contain EntryIndex values.")

    @staticmethod
    def _require_unique_columns(dataset: pd.DataFrame, columns: tuple[str, ...], label: str) -> None:
        """Require every named column to be present exactly once.

        Args:
            dataset: DataFrame whose columns are checked.
            columns: Required column names.
            label: Name used in an error message.

        Returns:
            None.

        Raises:
            TradeSimulationInputError: If a required column is missing or duplicated.
        """
        missing_columns = [column for column in columns if column not in dataset.columns]
        duplicate_columns = [column for column in columns if (dataset.columns == column).sum() > 1]
        if missing_columns or duplicate_columns:
            details: list[str] = []
            if missing_columns:
                details.append("missing: " + ", ".join(missing_columns))
            if duplicate_columns:
                details.append("duplicated: " + ", ".join(duplicate_columns))
            raise TradeSimulationInputError(f"Invalid {label} columns (" + "; ".join(details) + ").")
