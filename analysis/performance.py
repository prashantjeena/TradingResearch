"""Read-only trade-level performance metrics for completed simulations."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from analysis.trade_simulation import TRADE_SIMULATION_COLUMNS
from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS


PERFORMANCE_FIELDS: tuple[str, ...] = ("GrossReturn", "NetReturn", "MFE", "MAE")
"""Fields appended by the Trade Performance Engine."""

PERFORMANCE_COLUMNS: tuple[str, ...] = (*TRADE_SIMULATION_COLUMNS, *PERFORMANCE_FIELDS)
"""Required output columns and order after trade-level performance evaluation."""


class PerformanceInputError(ValueError):
    """Raised when simulated trade references cannot be measured safely."""


class TradePerformanceEvaluator:
    """Calculate trade-level returns and excursions without changing outcomes."""

    def evaluate(self, dataset: pd.DataFrame, simulated_trades: pd.DataFrame) -> pd.DataFrame:
        """Append trade-level performance metrics without modifying either input.

        WIN and LOSS trades use completed candles strictly before the exit
        candle for MFE and MAE. EXPIRED trades use all five active candles.
        Rows without an outcome retain empty performance fields.

        Args:
            dataset: Validated canonical OHLCV source data, ordered within each
                ticker and carrying a unique DataFrame index.
            simulated_trades: Exact output from ``TradeSimulator`` for the
                same dataset.

        Returns:
            A new DataFrame preserving all Phase 7 columns and appending
            ``GrossReturn``, ``NetReturn``, ``MFE``, and ``MAE``.

        Raises:
            PerformanceInputError: If required input columns are unavailable
                or a resolved trade's source references are invalid.
        """
        self._validate_inputs(dataset, simulated_trades)
        source_positions, ticker_positions, ticker_ranks = self._build_source_lookup(dataset)
        performance_records: list[tuple[float | None, ...]] = []

        for trade in simulated_trades.itertuples(index=False):
            if trade.Outcome is None:
                performance_records.append((None, None, None, None))
                continue

            entry_position = source_positions.get(trade.EntryIndex)
            exit_position = source_positions.get(trade.ExitIndex)
            if entry_position is None:
                raise PerformanceInputError(f"EntryIndex does not exist in dataset: {trade.EntryIndex!r}")
            if exit_position is None:
                raise PerformanceInputError(f"ExitIndex does not exist in dataset: {trade.ExitIndex!r}")

            entry_candle = dataset.iloc[entry_position]
            exit_candle = dataset.iloc[exit_position]
            if (
                entry_candle["Ticker"] != trade.Ticker
                or entry_candle["Date"] != trade.EntryDate
                or float(entry_candle["Open"]) != float(trade.RawEntryPrice)
            ):
                raise PerformanceInputError(f"Entry metadata does not match dataset row at EntryIndex {trade.EntryIndex!r}.")
            if exit_candle["Ticker"] != trade.Ticker or exit_candle["Date"] != trade.ExitDate:
                raise PerformanceInputError(f"Exit metadata does not match dataset row at ExitIndex {trade.ExitIndex!r}.")

            entry_ticker_position = ticker_ranks[entry_position]
            exit_ticker_position = ticker_ranks[exit_position]
            same_ticker_positions = ticker_positions[trade.Ticker]
            if exit_ticker_position < entry_ticker_position or exit_ticker_position > entry_ticker_position + 4:
                raise PerformanceInputError("ExitIndex must be between EntryIndex and T+6 for the same ticker.")

            gross_return = ((float(trade.ExitPrice) - float(trade.RawEntryPrice)) / float(trade.RawEntryPrice)) * 100
            net_return = ((float(trade.ExitFill) - float(trade.EntryFill)) / float(trade.EntryFill)) * 100
            active_positions = self._excursion_positions(
                same_ticker_positions,
                entry_ticker_position,
                exit_ticker_position,
                trade.Outcome,
            )
            mfe, mae = self._excursions(dataset, active_positions, float(trade.EntryFill))
            performance_records.append((gross_return, net_return, mfe, mae))

        result = simulated_trades.copy()
        performance_frame = pd.DataFrame(performance_records, columns=PERFORMANCE_FIELDS, index=result.index)
        for field in PERFORMANCE_FIELDS:
            result[field] = performance_frame[field]
        return result.loc[:, PERFORMANCE_COLUMNS]

    @staticmethod
    def _excursion_positions(
        same_ticker_positions: list[int],
        entry_ticker_position: int,
        exit_ticker_position: int,
        outcome: str,
    ) -> list[int]:
        """Select only candles allowed for Version 1 excursion measurement.

        Args:
            same_ticker_positions: Ordered source positions for one ticker.
            entry_ticker_position: Ticker-relative position of Day T+2.
            exit_ticker_position: Ticker-relative position of the exit candle.
            outcome: Resolved WIN, LOSS, or EXPIRED outcome.

        Returns:
            Source positions for candles used to measure MFE and MAE.
        """
        if outcome == "EXPIRED":
            return same_ticker_positions[entry_ticker_position:entry_ticker_position + 5]
        return same_ticker_positions[entry_ticker_position:exit_ticker_position]

    @staticmethod
    def _excursions(dataset: pd.DataFrame, source_positions: list[int], entry_fill: float) -> tuple[float, float]:
        """Measure positive favorable and adverse excursions from entry fill.

        Args:
            dataset: Canonical OHLCV source data.
            source_positions: Completed active-candle positions to inspect.
            entry_fill: Execution-adjusted entry price.

        Returns:
            Non-negative MFE and MAE values in price units.
        """
        if not source_positions:
            return 0.0, 0.0
        active_candles = dataset.iloc[source_positions]
        mfe = max(0.0, float(active_candles["High"].max()) - entry_fill)
        mae = max(0.0, entry_fill - float(active_candles["Low"].min()))
        return mfe, mae

    @staticmethod
    def _build_source_lookup(
        dataset: pd.DataFrame,
    ) -> tuple[dict[object, int], dict[object, list[int]], dict[int, int]]:
        """Build source-index and same-ticker position lookups.

        Args:
            dataset: Validated canonical source data with a unique index.

        Returns:
            Source-index positions, same-ticker positions, and ticker-relative
            ranks for every source row.
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
    def _validate_inputs(dataset: pd.DataFrame, simulated_trades: pd.DataFrame) -> None:
        """Validate structural requirements before measuring trade performance.

        Args:
            dataset: Canonical OHLCV source data.
            simulated_trades: Phase 7 output to measure.

        Returns:
            None.

        Raises:
            PerformanceInputError: If required columns are missing, source
                indexes are ambiguous, or resolved trades lack source indexes.
        """
        TradePerformanceEvaluator._require_unique_columns(dataset, CANONICAL_OHLCV_COLUMNS, "dataset")
        TradePerformanceEvaluator._require_unique_columns(simulated_trades, TRADE_SIMULATION_COLUMNS, "simulated_trades")
        if not dataset.index.is_unique:
            raise PerformanceInputError("Dataset index must be unique to resolve EntryIndex values.")
        resolved = simulated_trades["Outcome"].isin(("WIN", "LOSS", "EXPIRED"))
        if simulated_trades.loc[resolved, ["EntryIndex", "ExitIndex"]].isna().any().any():
            raise PerformanceInputError("Resolved trades must contain EntryIndex and ExitIndex values.")

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
            PerformanceInputError: If a required column is missing or duplicated.
        """
        missing_columns = [column for column in columns if column not in dataset.columns]
        duplicate_columns = [column for column in columns if (dataset.columns == column).sum() > 1]
        if missing_columns or duplicate_columns:
            details: list[str] = []
            if missing_columns:
                details.append("missing: " + ", ".join(missing_columns))
            if duplicate_columns:
                details.append("duplicated: " + ", ".join(duplicate_columns))
            raise PerformanceInputError(f"Invalid {label} columns (" + "; ".join(details) + ").")
