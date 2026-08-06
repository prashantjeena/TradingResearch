"""Read-only detection of the Version 1 Bullish Engulfing pattern."""

from __future__ import annotations

import pandas as pd

from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS


PATTERN_NAME = "Bullish Engulfing"
"""Stable name assigned to every detection produced by this module."""

DETECTION_COLUMNS: tuple[str, ...] = (*CANONICAL_OHLCV_COLUMNS, "PatternName", "PatternIndex", "PreviousDate")
"""Required output columns and their order for Bullish Engulfing detections."""


class DetectionInputError(ValueError):
    """Raised when a dataset cannot supply the fields required for detection."""


class BullishEngulfingDetector:
    """Detect strict body-only Bullish Engulfing candles without look-ahead data."""

    def detect(self, dataset: pd.DataFrame) -> pd.DataFrame:
        """Return Bullish Engulfing rows while preserving source observation order.

        The current candle is evaluated only against the immediately preceding
        available candle for the same ticker. The detector uses only the Open
        and Close fields needed by the frozen pattern definition; High and Low
        are preserved in the result but are not used to qualify the pattern.

        Args:
            dataset: Validated canonical OHLCV observations. Rows must already
                be in chronological order within each ticker.

        Returns:
            A new DataFrame containing canonical columns plus ``PatternName``,
            ``PatternIndex``, and ``PreviousDate``. Its rows retain the order
            in which qualifying observations appeared in ``dataset``.

        Raises:
            DetectionInputError: If a canonical input column is missing or
                appears more than once.
        """
        self._validate_required_columns(dataset)

        grouped_dataset = dataset.groupby("Ticker", sort=False)
        previous_open = grouped_dataset["Open"].shift(1)
        previous_close = grouped_dataset["Close"].shift(1)
        previous_date = grouped_dataset["Date"].shift(1)

        pattern_mask = (
            (previous_close < previous_open)
            & (dataset["Close"] > dataset["Open"])
            & (dataset["Open"] < previous_close)
            & (dataset["Close"] > previous_open)
        )

        detections = dataset.loc[pattern_mask, CANONICAL_OHLCV_COLUMNS].copy()
        detections["PatternName"] = PATTERN_NAME
        detections["PatternIndex"] = dataset.index[pattern_mask].to_numpy()
        detections["PreviousDate"] = previous_date[pattern_mask].to_numpy()
        return detections.loc[:, DETECTION_COLUMNS]

    @staticmethod
    def _validate_required_columns(dataset: pd.DataFrame) -> None:
        """Ensure every canonical input column exists exactly once.

        Args:
            dataset: DataFrame supplied for pattern detection.

        Returns:
            None.

        Raises:
            DetectionInputError: If a canonical input column is missing or
                duplicated.
        """
        missing_columns = [column for column in CANONICAL_OHLCV_COLUMNS if column not in dataset.columns]
        duplicate_columns = [
            column
            for column in CANONICAL_OHLCV_COLUMNS
            if (dataset.columns == column).sum() > 1
        ]
        if missing_columns or duplicate_columns:
            details: list[str] = []
            if missing_columns:
                details.append("missing: " + ", ".join(missing_columns))
            if duplicate_columns:
                details.append("duplicated: " + ", ".join(duplicate_columns))
            raise DetectionInputError("Invalid detection input columns (" + "; ".join(details) + ").")
