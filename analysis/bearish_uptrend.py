"""Frozen prior-uptrend evaluation for Bearish Engulfing patterns."""

from __future__ import annotations

from collections import defaultdict
import pandas as pd

from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS
from patterns.bearish_engulfing import DETECTION_COLUMNS

UPTREND_COLUMNS: tuple[str, ...] = (*DETECTION_COLUMNS, "UptrendPassed", "UptrendScore", "UptrendRejectionReason")


class UptrendInputError(ValueError):
    """Raised when bearish pattern references cannot be evaluated safely."""


class UptrendEvaluator:
    """Evaluate the frozen three-of-four higher-high/higher-low requirement."""

    def evaluate(self, dataset: pd.DataFrame, patterns: pd.DataFrame) -> pd.DataFrame:
        """Append independent uptrend diagnostics without modifying inputs.

        Args:
            dataset: Canonical source observations with unique index.
            patterns: Exact bearish detector output.

        Returns:
            A new frame with passed flag, structured score, and reason.

        Raises:
            UptrendInputError: If references are inconsistent or unavailable.
        """
        self._validate(dataset, patterns)
        positions, ticker_positions, ranks = self._lookup(dataset)
        values: list[tuple[bool, int | None, str | None]] = []
        for row in patterns.itertuples(index=False):
            pos = positions.get(row.PatternIndex)
            if pos is None or dataset.iloc[pos]["Ticker"] != row.Ticker or dataset.iloc[pos]["Date"] != row.Date:
                raise UptrendInputError(f"Invalid PatternIndex: {row.PatternIndex!r}.")
            prior_positions = ticker_positions[row.Ticker][ranks[pos] - 5:ranks[pos]]
            if len(prior_positions) < 5:
                values.append((False, None, "Insufficient prior candles: requires five candles from T-5 through T-1."))
                continue
            prior = dataset.iloc[prior_positions]
            score = int(((prior["High"].iloc[1:].to_numpy() > prior["High"].iloc[:-1].to_numpy()) & (prior["Low"].iloc[1:].to_numpy() > prior["Low"].iloc[:-1].to_numpy())).sum())
            values.append((score >= 3, score, None if score >= 3 else f"Uptrend rejected: {score} of 4 higher-high/higher-low comparisons; requires at least 3."))
        result = patterns.copy()
        result[["UptrendPassed", "UptrendScore", "UptrendRejectionReason"]] = pd.DataFrame(values, index=result.index)
        return result.loc[:, UPTREND_COLUMNS]

    @staticmethod
    def _lookup(dataset: pd.DataFrame) -> tuple[dict[object, int], dict[object, list[int]], dict[int, int]]:
        """Build source-index and same-ticker position mappings."""
        positions: dict[object, int] = {}; grouped: dict[object, list[int]] = defaultdict(list); ranks: dict[int, int] = {}
        for pos, (index, ticker) in enumerate(zip(dataset.index, dataset["Ticker"], strict=True)):
            positions[index] = pos; ranks[pos] = len(grouped[ticker]); grouped[ticker].append(pos)
        return positions, dict(grouped), ranks

    @staticmethod
    def _validate(dataset: pd.DataFrame, patterns: pd.DataFrame) -> None:
        """Validate source and detector contracts.

        Raises:
            UptrendInputError: If contracts are invalid.
        """
        required = (CANONICAL_OHLCV_COLUMNS, DETECTION_COLUMNS)
        for frame, columns in zip((dataset, patterns), required, strict=True):
            if any(column not in frame or (frame.columns == column).sum() != 1 for column in columns):
                raise UptrendInputError("Required input columns are missing or duplicated.")
        if not dataset.index.is_unique or patterns["PatternIndex"].isna().any():
            raise UptrendInputError("Dataset index and PatternIndex values must be unique and present.")
