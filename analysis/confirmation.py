"""Read-only Version 1 confirmation evaluation for downtrend-qualified patterns."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from analysis.trend import DOWNTREND_COLUMNS
from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS


CONFIRMATION_COLUMNS: tuple[str, ...] = (
    *DOWNTREND_COLUMNS,
    "ConfirmationPassed",
    "ConfirmationDate",
    "ConfirmationIndex",
    "ConfirmationRejectionReason",
)
"""Required output columns and order after Version 1 confirmation evaluation."""

_DOWNTREND_REJECTION_REASON = "Pattern did not pass downtrend evaluation."
_MISSING_CANDLE_REASON = "Confirmation candle unavailable."
_FAILED_CONFIRMATION_REASON = "Confirmation failed: Close[T+1] <= High[T]."


class ConfirmationInputError(ValueError):
    """Raised when source data and downtrend output cannot be evaluated safely."""


class ConfirmationEvaluator:
    """Evaluate the frozen Day T+1 close-above-pattern-high confirmation rule."""

    def evaluate(self, dataset: pd.DataFrame, downtrend_patterns: pd.DataFrame) -> pd.DataFrame:
        """Append confirmation decisions without mutating either input DataFrame.

        Only patterns whose ``DowntrendPassed`` value is true are evaluated. A
        qualified pattern at Day T is confirmed only when the close of the next
        available same-ticker candle is strictly greater than High[T].

        Args:
            dataset: Validated canonical OHLCV data in chronological order
                within each ticker. Its index must be unique.
            downtrend_patterns: Exact output from ``DowntrendEvaluator`` for
                the same dataset.

        Returns:
            A new DataFrame preserving all downtrend columns and appending
            confirmation fields in ``CONFIRMATION_COLUMNS`` order.

        Raises:
            ConfirmationInputError: If required input columns are unavailable,
                source indexes are ambiguous, or pattern metadata does not
                match the supplied dataset.
        """
        self._validate_inputs(dataset, downtrend_patterns)
        source_positions, ticker_positions, ticker_ranks = self._build_source_lookup(dataset)

        passed_values: list[bool] = []
        confirmation_dates: list[object | None] = []
        confirmation_indexes: list[object | None] = []
        rejection_reasons: list[str | None] = []

        for pattern_index, pattern_ticker, pattern_date, downtrend_passed in zip(
            downtrend_patterns["PatternIndex"].to_numpy(),
            downtrend_patterns["Ticker"].to_numpy(),
            downtrend_patterns["Date"].to_numpy(),
            downtrend_patterns["DowntrendPassed"].to_numpy(),
            strict=True,
        ):
            if not bool(downtrend_passed):
                passed_values.append(False)
                confirmation_dates.append(None)
                confirmation_indexes.append(None)
                rejection_reasons.append(_DOWNTREND_REJECTION_REASON)
                continue

            source_position = source_positions.get(pattern_index)
            if source_position is None:
                raise ConfirmationInputError(f"PatternIndex does not exist in dataset: {pattern_index!r}")

            pattern_candle = dataset.iloc[source_position]
            if pattern_candle["Ticker"] != pattern_ticker or pattern_candle["Date"] != pattern_date:
                raise ConfirmationInputError(
                    f"Pattern metadata does not match dataset row at PatternIndex {pattern_index!r}."
                )

            ticker_position = ticker_ranks[source_position]
            same_ticker_positions = ticker_positions[pattern_ticker]
            if ticker_position + 1 >= len(same_ticker_positions):
                passed_values.append(False)
                confirmation_dates.append(None)
                confirmation_indexes.append(None)
                rejection_reasons.append(_MISSING_CANDLE_REASON)
                continue

            confirmation_position = same_ticker_positions[ticker_position + 1]
            confirmation_candle = dataset.iloc[confirmation_position]
            if confirmation_candle["Close"] > pattern_candle["High"]:
                passed_values.append(True)
                confirmation_dates.append(confirmation_candle["Date"])
                confirmation_indexes.append(dataset.index[confirmation_position])
                rejection_reasons.append(None)
                continue

            passed_values.append(False)
            confirmation_dates.append(None)
            confirmation_indexes.append(None)
            rejection_reasons.append(_FAILED_CONFIRMATION_REASON)

        confirmed_patterns = downtrend_patterns.copy()
        confirmed_patterns["ConfirmationPassed"] = pd.Series(
            passed_values,
            index=confirmed_patterns.index,
            dtype="bool",
        )
        confirmed_patterns["ConfirmationDate"] = pd.Series(
            confirmation_dates,
            index=confirmed_patterns.index,
            dtype="object",
        )
        confirmed_patterns["ConfirmationIndex"] = pd.Series(
            confirmation_indexes,
            index=confirmed_patterns.index,
            dtype="object",
        )
        confirmed_patterns["ConfirmationRejectionReason"] = pd.Series(
            rejection_reasons,
            index=confirmed_patterns.index,
            dtype="object",
        )
        return confirmed_patterns.loc[:, CONFIRMATION_COLUMNS]

    @staticmethod
    def _build_source_lookup(
        dataset: pd.DataFrame,
    ) -> tuple[dict[object, int], dict[object, list[int]], dict[int, int]]:
        """Build source and ticker-position lookups without evaluating confirmation.

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
    def _validate_inputs(dataset: pd.DataFrame, downtrend_patterns: pd.DataFrame) -> None:
        """Validate structural requirements for confirmation evaluation.

        Args:
            dataset: Canonical OHLCV source data.
            downtrend_patterns: Downtrend evaluation output to confirm.

        Returns:
            None.

        Raises:
            ConfirmationInputError: If input columns are missing or ambiguous,
                the source index is non-unique, or required values are missing.
        """
        ConfirmationEvaluator._require_unique_columns(dataset, CANONICAL_OHLCV_COLUMNS, "dataset")
        ConfirmationEvaluator._require_unique_columns(downtrend_patterns, DOWNTREND_COLUMNS, "downtrend_patterns")
        if not dataset.index.is_unique:
            raise ConfirmationInputError("Dataset index must be unique to resolve PatternIndex values.")
        if downtrend_patterns["PatternIndex"].isna().any():
            raise ConfirmationInputError("PatternIndex must not contain missing values.")
        if downtrend_patterns["DowntrendPassed"].isna().any():
            raise ConfirmationInputError("DowntrendPassed must not contain missing values.")

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
            ConfirmationInputError: If a required column is missing or duplicated.
        """
        missing_columns = [column for column in columns if column not in dataset.columns]
        duplicate_columns = [column for column in columns if (dataset.columns == column).sum() > 1]
        if missing_columns or duplicate_columns:
            details: list[str] = []
            if missing_columns:
                details.append("missing: " + ", ".join(missing_columns))
            if duplicate_columns:
                details.append("duplicated: " + ", ".join(duplicate_columns))
            raise ConfirmationInputError(f"Invalid {label} columns (" + "; ".join(details) + ").")
