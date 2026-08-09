"""Strict, read-only Bearish Engulfing pattern detection."""

from __future__ import annotations

import pandas as pd

from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS


PATTERN_NAME = "Bearish Engulfing"
DETECTION_COLUMNS: tuple[str, ...] = (*CANONICAL_OHLCV_COLUMNS, "PatternName", "PatternIndex", "PreviousDate")


class BearishDetectionInputError(ValueError):
    """Raised when a source frame cannot be evaluated safely."""


class BearishEngulfingDetector:
    """Detect strict real-body bearish engulfing candles without mutation."""

    def detect(self, dataset: pd.DataFrame) -> pd.DataFrame:
        """Return detected Day-T candles in source order.

        Args:
            dataset: Validated canonical daily OHLCV data, ordered per ticker.

        Returns:
            A new frame with canonical columns and immutable source references.

        Raises:
            BearishDetectionInputError: If canonical columns are unavailable.
        """
        self._validate(dataset)
        previous = dataset.groupby("Ticker", sort=False)[["Date", "Open", "Close"]].shift(1)
        mask = (
            previous["Close"].gt(previous["Open"])
            & dataset["Close"].lt(dataset["Open"])
            & dataset["Open"].gt(previous["Close"])
            & dataset["Close"].lt(previous["Open"])
        )
        result = dataset.loc[mask, CANONICAL_OHLCV_COLUMNS].copy()
        result["PatternName"] = PATTERN_NAME
        result["PatternIndex"] = result.index
        result["PreviousDate"] = previous.loc[mask, "Date"]
        return result.loc[:, DETECTION_COLUMNS]

    @staticmethod
    def _validate(dataset: pd.DataFrame) -> None:
        """Validate canonical columns are present exactly once.

        Args:
            dataset: Candidate source data.

        Raises:
            BearishDetectionInputError: If the input contract is violated.
        """
        missing = [column for column in CANONICAL_OHLCV_COLUMNS if column not in dataset]
        duplicate = [column for column in CANONICAL_OHLCV_COLUMNS if (dataset.columns == column).sum() > 1]
        if missing or duplicate:
            raise BearishDetectionInputError(f"Invalid dataset columns; missing={missing}, duplicated={duplicate}.")
