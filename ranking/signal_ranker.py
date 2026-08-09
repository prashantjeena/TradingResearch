"""Live-safe ranking metadata for daily eligible signals."""

from __future__ import annotations

import pandas as pd


_REQUIRED_COLUMNS = frozenset(
    {
        "DowntrendPassed",
        "ConfirmationPassed",
        "RiskPercent",
        "Ticker",
    }
)
_SENTIMENT_SCORES = {
    "positive": 10,
    "bullish": 10,
    "somewhat-bullish": 10,
    "neutral": 0,
    "negative": -10,
    "bearish": -10,
    "somewhat-bearish": -10,
}


class SignalRankingError(ValueError):
    """Raised when signal data cannot be ranked using live-safe inputs."""


class SignalRanker:
    """Append deterministic, pre-entry-only ranking metadata to daily signals."""

    def rank(self, signals: pd.DataFrame, trend_column: str = "DowntrendPassed") -> pd.DataFrame:
        """Score and rank supplied signals using only live-safe information.

        Args:
            signals: DataFrame returned by ``DailySignalScanner``. Optional
                news metadata may be present when available.
            trend_column: Boolean pre-entry trend field. Defaults to the
                Bullish ``DowntrendPassed`` contract.

        Returns:
            A new DataFrame with all source columns preserved and ``RankScore``
            and ``Rank`` appended, ordered by the Version 1 ranking keys.

        Raises:
            SignalRankingError: If a required ranking input is absent or
                ``RiskPercent`` cannot be interpreted as numeric.
        """
        required_columns = (_REQUIRED_COLUMNS - {"DowntrendPassed"}) | {trend_column}
        missing_columns = sorted(required_columns.difference(signals.columns))
        if missing_columns:
            raise SignalRankingError(
                f"Signals are missing required ranking columns: {', '.join(missing_columns)}."
            )

        try:
            risk_percent = pd.to_numeric(signals["RiskPercent"], errors="raise")
        except (TypeError, ValueError) as error:
            raise SignalRankingError("RiskPercent must contain numeric values.") from error

        news_sentiment = signals.get(
            "NewsSentiment",
            pd.Series(None, index=signals.index, dtype="object"),
        )
        sentiment_scores = (
            news_sentiment.astype("string")
            .str.strip()
            .str.casefold()
            .map(_SENTIMENT_SCORES)
            .fillna(0)
            .astype("int64")
        )

        rank_score = 100.0 - (risk_percent * 10)
        rank_score += signals["ConfirmationPassed"].eq(True).fillna(False).astype("int64") * 15
        rank_score += signals[trend_column].eq(True).fillna(False).astype("int64") * 10
        rank_score += sentiment_scores

        ranked_signals = signals.assign(RankScore=rank_score).sort_values(
            by=["RankScore", "RiskPercent", "Ticker"],
            ascending=[False, True, True],
            kind="stable",
        ).copy()
        ranked_signals["Rank"] = range(1, len(ranked_signals) + 1)
        return ranked_signals
