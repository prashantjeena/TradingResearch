"""Read-only consolidated daily report projection for ranked signals."""

from __future__ import annotations

import pandas as pd


DAILY_REPORT_COLUMNS: tuple[str, ...] = (
    "Rank",
    "Ticker",
    "EntryDate",
    "EntryFill",
    "StopPrice",
    "TargetPrice",
    "Risk",
    "RiskPercent",
    "RankScore",
)
"""Exact ordered columns exposed by the consolidated daily report."""


class DailyReportError(ValueError):
    """Raised when ranked signal data cannot produce the daily report."""


class DailyReportGenerator:
    """Project ranked signals into the fixed daily-report schema."""

    def generate(self, ranked_signals: pd.DataFrame) -> pd.DataFrame:
        """Copy approved report fields from ranked signals in their existing order.

        Args:
            ranked_signals: DataFrame returned by ``SignalRanker.rank``.

        Returns:
            A new DataFrame containing only ``DAILY_REPORT_COLUMNS`` in their
            defined order, while preserving input row order and values.

        Raises:
            DailyReportError: If a required daily-report column is absent.
        """
        missing_columns = [
            column for column in DAILY_REPORT_COLUMNS if column not in ranked_signals.columns
        ]
        if missing_columns:
            raise DailyReportError(
                f"Ranked signals are missing required report columns: {', '.join(missing_columns)}."
            )

        return ranked_signals.loc[:, DAILY_REPORT_COLUMNS].copy()
