"""Read-only Version 1 downtrend evaluation for detected Bullish Engulfing patterns."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS
from patterns.bullish_engulfing import DETECTION_COLUMNS


DOWNTREND_COLUMNS: tuple[str, ...] = (*DETECTION_COLUMNS, "DowntrendPassed", "DowntrendRejectionReason")
"""Required output columns and order after Version 1 downtrend evaluation."""

_INSUFFICIENT_HISTORY_REASON = "Insufficient prior candles: requires five candles from T-5 through T-1."
"""Frozen Version 1 rejection reason for unavailable prior history."""


class DowntrendInputError(ValueError):
    """Raised when source data and detected patterns cannot be evaluated safely."""


class DowntrendEvaluator:
    """Evaluate the frozen three-of-four price-action downtrend rule per pattern."""

    def evaluate(self, dataset: pd.DataFrame, detected_patterns: pd.DataFrame) -> pd.DataFrame:
        """Append downtrend decisions to detected patterns without mutating inputs.

        For every detected pattern at Day T, this method retrieves only the
        five preceding candles for the same ticker, T-5 through T-1. It never
        uses the pattern candle or any later candle to determine the trend.

        Args:
            dataset: Validated canonical OHLCV data in chronological order
                within each ticker. Its index must be unique.
            detected_patterns: Output from ``BullishEngulfingDetector`` for
                the same dataset.

        Returns:
            A new DataFrame retaining all detector columns and their order,
            with ``DowntrendPassed`` and ``DowntrendRejectionReason`` appended.

        Raises:
            DowntrendInputError: If required input columns are unavailable,
                source indexes are ambiguous, or pattern metadata does not
                match the supplied dataset.
        """
        self._validate_inputs(dataset, detected_patterns)
        source_positions, ticker_positions, ticker_ranks = self._build_source_lookup(dataset)

        passed_values: list[bool] = []
        rejection_reasons: list[str | None] = []
        pattern_indexes = detected_patterns["PatternIndex"].to_numpy()
        pattern_tickers = detected_patterns["Ticker"].to_numpy()
        pattern_dates = detected_patterns["Date"].to_numpy()

        for pattern_index, pattern_ticker, pattern_date in zip(
            pattern_indexes,
            pattern_tickers,
            pattern_dates,
            strict=True,
        ):
            source_position = source_positions.get(pattern_index)
            if source_position is None:
                raise DowntrendInputError(f"PatternIndex does not exist in dataset: {pattern_index!r}")

            source_candle = dataset.iloc[source_position]
            if source_candle["Ticker"] != pattern_ticker or source_candle["Date"] != pattern_date:
                raise DowntrendInputError(
                    f"Pattern metadata does not match dataset row at PatternIndex {pattern_index!r}."
                )

            ticker_position = ticker_ranks[source_position]
            prior_positions = ticker_positions[pattern_ticker][ticker_position - 5:ticker_position]
            if len(prior_positions) < 5:
                passed_values.append(False)
                rejection_reasons.append(_INSUFFICIENT_HISTORY_REASON)
                continue

            prior_candles = dataset.iloc[prior_positions]
            comparison_count = self._count_lower_high_lower_low_comparisons(prior_candles)
            if comparison_count >= 3:
                passed_values.append(True)
                rejection_reasons.append(None)
                continue

            passed_values.append(False)
            rejection_reasons.append(
                "Downtrend rejected: "
                f"{comparison_count} of 4 lower-high/lower-low comparisons; requires at least 3."
            )

        evaluated_patterns = detected_patterns.copy()
        evaluated_patterns["DowntrendPassed"] = pd.Series(
            passed_values,
            index=evaluated_patterns.index,
            dtype="bool",
        )
        evaluated_patterns["DowntrendRejectionReason"] = pd.Series(
            rejection_reasons,
            index=evaluated_patterns.index,
            dtype="object",
        )
        return evaluated_patterns.loc[:, DOWNTREND_COLUMNS]

    @staticmethod
    def _count_lower_high_lower_low_comparisons(prior_candles: pd.DataFrame) -> int:
        """Count qualifying consecutive comparisons in five prior candles.

        Args:
            prior_candles: Exactly five same-ticker candles from T-5 through
                T-1, in chronological order.

        Returns:
            Number of comparisons where both High and Low are lower than the
            immediately preceding prior candle.
        """
        lower_highs = prior_candles["High"].iloc[1:].to_numpy() < prior_candles["High"].iloc[:-1].to_numpy()
        lower_lows = prior_candles["Low"].iloc[1:].to_numpy() < prior_candles["Low"].iloc[:-1].to_numpy()
        return int((lower_highs & lower_lows).sum())

    @staticmethod
    def _build_source_lookup(
        dataset: pd.DataFrame,
    ) -> tuple[dict[object, int], dict[object, list[int]], dict[int, int]]:
        """Build index and ticker-position lookups without calculating trends.

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
    def _validate_inputs(dataset: pd.DataFrame, detected_patterns: pd.DataFrame) -> None:
        """Validate structural requirements for independent pattern evaluation.

        Args:
            dataset: Canonical OHLCV source data.
            detected_patterns: Detector output to evaluate.

        Returns:
            None.

        Raises:
            DowntrendInputError: If input columns are missing or ambiguous, the
                source index is non-unique, or PatternIndex is missing.
        """
        DowntrendEvaluator._require_unique_columns(dataset, CANONICAL_OHLCV_COLUMNS, "dataset")
        DowntrendEvaluator._require_unique_columns(detected_patterns, DETECTION_COLUMNS, "detected_patterns")
        if not dataset.index.is_unique:
            raise DowntrendInputError("Dataset index must be unique to resolve PatternIndex values.")
        if detected_patterns["PatternIndex"].isna().any():
            raise DowntrendInputError("PatternIndex must not contain missing values.")

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
            DowntrendInputError: If a required column is missing or duplicated.
        """
        missing_columns = [column for column in columns if column not in dataset.columns]
        duplicate_columns = [column for column in columns if (dataset.columns == column).sum() > 1]
        if missing_columns or duplicate_columns:
            details: list[str] = []
            if missing_columns:
                details.append("missing: " + ", ".join(missing_columns))
            if duplicate_columns:
                details.append("duplicated: " + ", ".join(duplicate_columns))
            raise DowntrendInputError(f"Invalid {label} columns (" + "; ".join(details) + ").")
