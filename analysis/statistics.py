"""Experiment-level aggregation of completed trade performance results."""

from __future__ import annotations

from typing import Any

import pandas as pd

from analysis.performance import PERFORMANCE_COLUMNS


class StatisticsInputError(ValueError):
    """Raised when performance results do not satisfy the Phase 8 contract."""


class StatisticsEvaluator:
    """Aggregate Phase 8 trade-level metrics into one deterministic experiment summary."""

    def evaluate(self, performance_results: pd.DataFrame) -> dict[str, Any]:
        """Return the frozen Version 1 experiment-level statistics dictionary.

        Args:
            performance_results: Exact output from ``TradePerformanceEvaluator``.

        Returns:
            A dictionary containing exactly the specified experiment metrics,
            including nested ticker-level results.

        Raises:
            StatisticsInputError: If required Phase 8 columns are missing or
                duplicated.
        """
        self._validate_input(performance_results)
        summary = self._summarize(performance_results)
        return {
            "TotalCandidatePatterns": int(len(performance_results)),
            "ValidPatterns": int(performance_results["DowntrendPassed"].sum()),
            "ConfirmedPatterns": int(performance_results["ConfirmationPassed"].sum()),
            "TradeEligible": int(performance_results["TradeEligible"].sum()),
            "Wins": summary["wins"],
            "Losses": summary["losses"],
            "ExpiredTrades": summary["expired"],
            "UnresolvedTrades": summary["unresolved"],
            "ResolvedTrades": summary["resolved"],
            "WinRateResolved": self._rate(summary["wins"], summary["resolved"]),
            "LossRateResolved": self._rate(summary["losses"], summary["resolved"]),
            "AverageGrossReturn": self._mean(performance_results["GrossReturn"]),
            "AverageNetReturn": self._mean(performance_results["NetReturn"]),
            "AverageHoldingDays": self._mean(performance_results["HoldingDays"]),
            "AverageMFE": self._mean(performance_results["MFE"]),
            "AverageMAE": self._mean(performance_results["MAE"]),
            "AverageRiskPercent": self._mean(performance_results.loc[performance_results["TradeEligible"], "RiskPercent"]),
            "AverageRewardRiskRatio": self._average_reward_risk_ratio(performance_results),
            "ResultsByTicker": self._results_by_ticker(performance_results),
        }

    @staticmethod
    def _summarize(results: pd.DataFrame) -> dict[str, int]:
        """Calculate outcome counts used by overall and ticker-level summaries.

        Args:
            results: Performance rows to aggregate.

        Returns:
            Counts for wins, losses, expired, unresolved, and resolved trades.
        """
        wins = int(results["Outcome"].eq("WIN").sum())
        losses = int(results["Outcome"].eq("LOSS").sum())
        expired = int(results["Outcome"].eq("EXPIRED").sum())
        unresolved = int(results["Outcome"].isna().sum())
        return {
            "wins": wins,
            "losses": losses,
            "expired": expired,
            "unresolved": unresolved,
            "resolved": wins + losses,
        }

    @staticmethod
    def _rate(numerator: int, denominator: int) -> float | None:
        """Return a ratio or None when its denominator is zero.

        Args:
            numerator: Count used in the ratio numerator.
            denominator: Count used in the ratio denominator.

        Returns:
            Floating-point ratio, or None when no resolved trade exists.
        """
        return None if denominator == 0 else numerator / denominator

    @staticmethod
    def _mean(values: pd.Series) -> float | None:
        """Return a missing-value-safe mean as a plain float.

        Args:
            values: Numeric values that may contain missing entries.

        Returns:
            Mean of present values, or None when no present value exists.
        """
        present_values = pd.to_numeric(values, errors="coerce").dropna()
        return None if present_values.empty else float(present_values.mean())

    @staticmethod
    def _average_reward_risk_ratio(results: pd.DataFrame) -> float | None:
        """Return the mean gross-return-to-risk-percent ratio for eligible trades.

        Args:
            results: Complete Phase 8 performance data.

        Returns:
            Mean reward-risk ratio after excluding non-positive or missing risk
            percentages and missing gross returns.
        """
        risk_percent = pd.to_numeric(results["RiskPercent"], errors="coerce")
        gross_return = pd.to_numeric(results["GrossReturn"], errors="coerce")
        eligible = results["TradeEligible"] & (risk_percent > 0) & gross_return.notna()
        ratios = gross_return.loc[eligible] / risk_percent.loc[eligible]
        return None if ratios.empty else float(ratios.mean())

    def _results_by_ticker(self, results: pd.DataFrame) -> dict[str, dict[str, Any]]:
        """Build deterministic ticker-level summaries from completed performance rows.

        Args:
            results: Complete Phase 8 performance data.

        Returns:
            Nested dictionary keyed by ticker in ascending ticker order.
        """
        ticker_results: dict[str, dict[str, Any]] = {}
        for ticker, ticker_frame in results.groupby("Ticker", sort=True):
            summary = self._summarize(ticker_frame)
            ticker_results[str(ticker)] = {
                "Patterns": int(len(ticker_frame)),
                "Confirmed": int(ticker_frame["ConfirmationPassed"].sum()),
                "Eligible": int(ticker_frame["TradeEligible"].sum()),
                "Wins": summary["wins"],
                "Losses": summary["losses"],
                "Expired": summary["expired"],
                "WinRateResolved": self._rate(summary["wins"], summary["resolved"]),
                "AverageNetReturn": self._mean(ticker_frame["NetReturn"]),
                "AverageHoldingDays": self._mean(ticker_frame["HoldingDays"]),
            }
        return ticker_results

    @staticmethod
    def _validate_input(performance_results: pd.DataFrame) -> None:
        """Require each Phase 8 output column exactly once.

        Args:
            performance_results: DataFrame supplied for statistics aggregation.

        Returns:
            None.

        Raises:
            StatisticsInputError: If a Phase 8 column is missing or duplicated.
        """
        missing_columns = [column for column in PERFORMANCE_COLUMNS if column not in performance_results.columns]
        duplicate_columns = [column for column in PERFORMANCE_COLUMNS if (performance_results.columns == column).sum() > 1]
        if missing_columns or duplicate_columns:
            details: list[str] = []
            if missing_columns:
                details.append("missing: " + ", ".join(missing_columns))
            if duplicate_columns:
                details.append("duplicated: " + ", ".join(duplicate_columns))
            raise StatisticsInputError("Invalid performance_results columns (" + "; ".join(details) + ").")
