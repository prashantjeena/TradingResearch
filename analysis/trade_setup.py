"""Read-only Version 1 trade setup calculation for confirmed patterns."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from analysis.confirmation import CONFIRMATION_COLUMNS
from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS


TRADE_SETUP_FIELDS: tuple[str, ...] = (
    "EntryDate",
    "EntryIndex",
    "RawEntryPrice",
    "EntryFill",
    "StopPrice",
    "Risk",
    "RiskPercent",
    "TargetPrice",
    "TradeEligible",
    "TradeRejectionReason",
)
"""Fields appended by the Version 1 Trade Setup Engine."""

TRADE_SETUP_COLUMNS: tuple[str, ...] = (*CONFIRMATION_COLUMNS, *TRADE_SETUP_FIELDS)
"""Required output columns and order after Version 1 trade setup evaluation."""


class TradeSetupInputError(ValueError):
    """Raised when source data and confirmation output cannot form a safe setup."""


class TradeSetupEvaluator:
    """Calculate Version 1 entry, risk, and target data without trade simulation."""

    def evaluate(self, dataset: pd.DataFrame, confirmation_patterns: pd.DataFrame) -> pd.DataFrame:
        """Append trade setup fields without modifying either input DataFrame.

        Only patterns that passed both downtrend and confirmation evaluation can
        form a setup. The evaluator accesses Day T through ``PatternIndex``,
        Day T+1 through ``ConfirmationIndex``, and only the next same-ticker
        candle, Day T+2, for the entry reference.

        Args:
            dataset: Validated canonical OHLCV data in chronological order
                within each ticker. Its index must be unique.
            confirmation_patterns: Exact output from ``ConfirmationEvaluator``
                for the same dataset.

        Returns:
            A new DataFrame preserving all Phase 5 columns and appending the
            fields specified by ``TRADE_SETUP_FIELDS``.

        Raises:
            TradeSetupInputError: If source indexes are ambiguous, required
                columns are unavailable, or pattern metadata conflicts with
                the supplied dataset.
        """
        self._validate_inputs(dataset, confirmation_patterns)
        source_positions, ticker_positions, ticker_ranks = self._build_source_lookup(dataset)
        setup_records: list[tuple[object | None, ...]] = []

        for pattern in confirmation_patterns.itertuples(index=False):
            pattern_index = pattern.PatternIndex
            source_position = source_positions.get(pattern_index)
            if source_position is None:
                raise TradeSetupInputError(f"PatternIndex does not exist in dataset: {pattern_index!r}")

            pattern_candle = dataset.iloc[source_position]
            if pattern_candle["Ticker"] != pattern.Ticker or pattern_candle["Date"] != pattern.Date:
                raise TradeSetupInputError(
                    f"Pattern metadata does not match dataset row at PatternIndex {pattern_index!r}."
                )

            if not bool(pattern.DowntrendPassed):
                setup_records.append(self._rejected_setup("Pattern did not pass downtrend evaluation."))
                continue
            if not bool(pattern.ConfirmationPassed):
                setup_records.append(self._rejected_setup("Pattern did not pass confirmation evaluation."))
                continue

            confirmation_position = source_positions.get(pattern.ConfirmationIndex)
            if confirmation_position is None:
                raise TradeSetupInputError(
                    f"ConfirmationIndex does not exist in dataset: {pattern.ConfirmationIndex!r}"
                )
            confirmation_candle = dataset.iloc[confirmation_position]
            if (
                confirmation_candle["Ticker"] != pattern.Ticker
                or confirmation_candle["Date"] != pattern.ConfirmationDate
            ):
                raise TradeSetupInputError(
                    f"Confirmation metadata does not match dataset row at ConfirmationIndex {pattern.ConfirmationIndex!r}."
                )

            pattern_ticker_position = ticker_ranks[source_position]
            same_ticker_positions = ticker_positions[pattern.Ticker]
            expected_confirmation_position = pattern_ticker_position + 1
            if (
                expected_confirmation_position >= len(same_ticker_positions)
                or same_ticker_positions[expected_confirmation_position] != confirmation_position
            ):
                raise TradeSetupInputError("ConfirmationIndex is not the immediate next same-ticker candle after PatternIndex.")

            entry_ticker_position = expected_confirmation_position + 1
            if entry_ticker_position >= len(same_ticker_positions):
                setup_records.append(self._rejected_setup("Entry candle unavailable."))
                continue

            entry_position = same_ticker_positions[entry_ticker_position]
            entry_candle = dataset.iloc[entry_position]
            raw_entry_price = float(entry_candle["Open"])
            entry_fill = raw_entry_price * 1.001
            stop_price = float(pattern_candle["Low"])
            risk = entry_fill - stop_price
            risk_percent = (risk / entry_fill) * 100 if entry_fill != 0 else None

            if risk <= 0:
                setup_records.append(
                    (
                        entry_candle["Date"],
                        dataset.index[entry_position],
                        raw_entry_price,
                        entry_fill,
                        stop_price,
                        risk,
                        risk_percent,
                        None,
                        False,
                        "Trade rejected: Risk must be greater than zero.",
                    )
                )
                continue

            target_price = entry_fill + (2 * risk)
            setup_records.append(
                (
                    entry_candle["Date"],
                    dataset.index[entry_position],
                    raw_entry_price,
                    entry_fill,
                    stop_price,
                    risk,
                    risk_percent,
                    target_price,
                    True,
                    None,
                )
            )

        result = confirmation_patterns.copy()
        setup_frame = pd.DataFrame(setup_records, columns=TRADE_SETUP_FIELDS, index=result.index)
        for field in TRADE_SETUP_FIELDS:
            result[field] = setup_frame[field]
        return result.loc[:, TRADE_SETUP_COLUMNS]

    @staticmethod
    def _rejected_setup(reason: str) -> tuple[object | None, ...]:
        """Return an empty setup record with a clear eligibility rejection reason.

        Args:
            reason: Explanation for why no trade setup can be formed.

        Returns:
            Values matching ``TRADE_SETUP_FIELDS`` for an ineligible pattern.
        """
        return (None, None, None, None, None, None, None, None, False, reason)

    @staticmethod
    def _build_source_lookup(
        dataset: pd.DataFrame,
    ) -> tuple[dict[object, int], dict[object, list[int]], dict[int, int]]:
        """Build source and ticker-position lookups without simulating trades.

        Args:
            dataset: Validated canonical source data with a unique index.

        Returns:
            A mapping from source index to row position, same-ticker row
            positions, and each source position's rank within its ticker.
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
    def _validate_inputs(dataset: pd.DataFrame, confirmation_patterns: pd.DataFrame) -> None:
        """Validate structural requirements before any setup calculation occurs.

        Args:
            dataset: Canonical OHLCV source data.
            confirmation_patterns: Confirmation evaluation output to process.

        Returns:
            None.

        Raises:
            TradeSetupInputError: If input columns or required reference values
                are missing or ambiguous.
        """
        TradeSetupEvaluator._require_unique_columns(dataset, CANONICAL_OHLCV_COLUMNS, "dataset")
        TradeSetupEvaluator._require_unique_columns(confirmation_patterns, CONFIRMATION_COLUMNS, "confirmation_patterns")
        if not dataset.index.is_unique:
            raise TradeSetupInputError("Dataset index must be unique to resolve PatternIndex values.")
        if confirmation_patterns["PatternIndex"].isna().any():
            raise TradeSetupInputError("PatternIndex must not contain missing values.")
        if confirmation_patterns[["DowntrendPassed", "ConfirmationPassed"]].isna().any().any():
            raise TradeSetupInputError("DowntrendPassed and ConfirmationPassed must not contain missing values.")
        confirmed_without_index = confirmation_patterns["ConfirmationPassed"] & confirmation_patterns["ConfirmationIndex"].isna()
        if confirmed_without_index.any():
            raise TradeSetupInputError("Confirmed patterns must contain ConfirmationIndex values.")

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
            TradeSetupInputError: If a required column is missing or duplicated.
        """
        missing_columns = [column for column in columns if column not in dataset.columns]
        duplicate_columns = [column for column in columns if (dataset.columns == column).sum() > 1]
        if missing_columns or duplicate_columns:
            details: list[str] = []
            if missing_columns:
                details.append("missing: " + ", ".join(missing_columns))
            if duplicate_columns:
                details.append("duplicated: " + ", ".join(duplicate_columns))
            raise TradeSetupInputError(f"Invalid {label} columns (" + "; ".join(details) + ").")
