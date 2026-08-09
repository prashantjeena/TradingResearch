"""Filtering of actionable setups for the latest completed trading day."""

from __future__ import annotations

import pandas as pd


class DailySignalScanner:
    """Select eligible pipeline trades actionable on a supplied trading date."""

    def scan(self, performance: pd.DataFrame, latest_trading_date: pd.Timestamp) -> pd.DataFrame:
        """Return eligible rows whose entry date equals the supplied latest date.

        Args:
            performance: The final trade-level DataFrame returned by
                ``ResearchPipeline``.
            latest_trading_date: Latest completed trading date from the source
                dataset. The scanner does not derive or alter this value.

        Returns:
            A new DataFrame containing only eligible entries for
            ``latest_trading_date``. If no rows qualify, the returned DataFrame
            is empty with the same columns as ``performance``.

        Raises:
            KeyError: If ``TradeEligible`` or ``EntryDate`` is absent from
                ``performance``.
        """
        entry_dates = pd.to_datetime(performance["EntryDate"], errors="coerce").dt.normalize()
        normalized_latest_date = pd.Timestamp(latest_trading_date).normalize()
        qualifying_rows = (
            performance["TradeEligible"].eq(True)
            & entry_dates.notna()
            & entry_dates.eq(normalized_latest_date)
        )

        return performance.loc[qualifying_rows].copy()
