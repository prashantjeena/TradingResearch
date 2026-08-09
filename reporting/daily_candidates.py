"""Read-only diagnostic projection of latest-day Bullish Engulfing patterns."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from analysis.trade_setup import TRADE_SETUP_COLUMNS
from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS


DAILY_CANDIDATE_COLUMNS: tuple[str, ...] = (
    "Universe",
    "Ticker",
    "PatternDate",
    "DowntrendScore",
    "CandidateStatus",
    "Open",
    "High",
    "Low",
    "Close",
    "PreviousDate",
    "PreviousOpen",
    "PreviousHigh",
    "PreviousLow",
    "PreviousClose",
    "DowntrendPassed",
    "ConfirmationPassed",
    "ConfirmationDate",
    "TradeEligible",
    "EntryDate",
    "EntryPrice",
    "StopLoss",
    "TargetPrice",
    "RejectionReason",
)
"""Exact schema of the daily diagnostic candidates CSV."""

DAILY_CANDIDATE_PRICE_COLUMNS: tuple[str, ...] = (
    "Open",
    "High",
    "Low",
    "Close",
    "PreviousOpen",
    "PreviousHigh",
    "PreviousLow",
    "PreviousClose",
    "EntryPrice",
    "StopLoss",
    "TargetPrice",
)
"""Candidate price fields formatted to two decimal places only during CSV export."""


class DailyCandidatesReportError(ValueError):
    """Raised when source or phase output cannot safely form a report."""


class DailyCandidatesReportGenerator:
    """Project latest-day detected patterns into a non-actionable watchlist."""

    def generate(
        self,
        dataset: pd.DataFrame,
        trade_setups: pd.DataFrame,
        latest_trading_date: pd.Timestamp,
        universe: str,
    ) -> pd.DataFrame:
        """Return latest-day Bullish Engulfing candidates without changing eligibility.

        ``trade_setups`` contains one row for every detected pattern, including
        patterns rejected by downtrend or confirmation. ``DowntrendScore`` is
        diagnostic-only metadata: Phase 4 does not expose its structured count,
        so it is calculated directly from the same five prior source candles.
        It never affects any returned Phase 4--6 value or trade decision.

        Args:
            dataset: Canonical source OHLCV observations with a unique index.
            trade_setups: Exact output from ``TradeSetupEvaluator``.
            latest_trading_date: Latest completed date for this source dataset.
            universe: Configured scanner-universe label for the dataset.

        Returns:
            A new DataFrame in ``DAILY_CANDIDATE_COLUMNS`` order. Only pattern
            rows dated on ``latest_trading_date`` are present.

        Raises:
            DailyCandidatesReportError: If required columns or PatternIndex
                references are unavailable or inconsistent.
        """
        self._validate_inputs(dataset, trade_setups)
        normalized_dates = pd.to_datetime(trade_setups["Date"], errors="coerce").dt.normalize()
        target_date = pd.Timestamp(latest_trading_date).normalize()
        latest_patterns = trade_setups.loc[normalized_dates == target_date].copy()
        if latest_patterns.empty:
            return pd.DataFrame(columns=DAILY_CANDIDATE_COLUMNS)

        source_positions, ticker_positions, ticker_ranks = self._build_source_lookup(dataset)
        records: list[dict[str, object]] = []
        for pattern in latest_patterns.itertuples(index=False):
            source_position = source_positions.get(pattern.PatternIndex)
            if source_position is None:
                raise DailyCandidatesReportError(
                    f"PatternIndex does not exist in dataset: {pattern.PatternIndex!r}"
                )
            candle = dataset.iloc[source_position]
            if candle["Ticker"] != pattern.Ticker or candle["Date"] != pattern.Date:
                raise DailyCandidatesReportError(
                    f"Pattern metadata does not match dataset row at PatternIndex {pattern.PatternIndex!r}."
                )

            same_ticker_positions = ticker_positions[pattern.Ticker]
            ticker_rank = ticker_ranks[source_position]
            previous_candle = (
                dataset.iloc[same_ticker_positions[ticker_rank - 1]] if ticker_rank else None
            )
            downtrend_score = self._downtrend_score(dataset, same_ticker_positions, ticker_rank)
            records.append(
                {
                    "Universe": universe,
                    "Ticker": pattern.Ticker,
                    "PatternDate": pattern.Date,
                    "DowntrendScore": downtrend_score,
                    "CandidateStatus": self._candidate_status(downtrend_score),
                    "Open": candle["Open"],
                    "High": candle["High"],
                    "Low": candle["Low"],
                    "Close": candle["Close"],
                    "PreviousDate": pattern.PreviousDate,
                    "PreviousOpen": previous_candle["Open"] if previous_candle is not None else None,
                    "PreviousHigh": previous_candle["High"] if previous_candle is not None else None,
                    "PreviousLow": previous_candle["Low"] if previous_candle is not None else None,
                    "PreviousClose": previous_candle["Close"] if previous_candle is not None else None,
                    "DowntrendPassed": pattern.DowntrendPassed,
                    "ConfirmationPassed": pattern.ConfirmationPassed,
                    "ConfirmationDate": pattern.ConfirmationDate,
                    "TradeEligible": pattern.TradeEligible,
                    "EntryDate": pattern.EntryDate,
                    "EntryPrice": pattern.EntryFill,
                    "StopLoss": pattern.StopPrice,
                    "TargetPrice": pattern.TargetPrice,
                    "RejectionReason": self._rejection_reason(pattern),
                }
            )
        return pd.DataFrame(records, columns=DAILY_CANDIDATE_COLUMNS)

    @staticmethod
    def _candidate_status(downtrend_score: int | None) -> str | None:
        """Map existing diagnostic comparison counts to display-only status text.

        Args:
            downtrend_score: Existing or report-derived zero-through-four count.

        Returns:
            A diagnostic display label, or ``None`` if the score is unavailable.
        """
        if downtrend_score is None:
            return None
        if downtrend_score >= 3:
            return "PASSED DOWNTREND"
        if downtrend_score == 2:
            return "NEAR FILTER"
        return "REJECTED"

    @staticmethod
    def _downtrend_score(
        dataset: pd.DataFrame,
        same_ticker_positions: list[int],
        ticker_rank: int,
    ) -> int | None:
        """Calculate the report-only count for the five candles before Day T.

        Args:
            dataset: Canonical source data.
            same_ticker_positions: Source positions for one ticker in order.
            ticker_rank: Pattern candle position within that ticker.

        Returns:
            A zero-through-four comparison count, or ``None`` when the five
            required prior candles do not exist.
        """
        prior_positions = same_ticker_positions[ticker_rank - 5:ticker_rank]
        if len(prior_positions) < 5:
            return None
        prior = dataset.iloc[prior_positions]
        lower_highs = prior["High"].iloc[1:].to_numpy() < prior["High"].iloc[:-1].to_numpy()
        lower_lows = prior["Low"].iloc[1:].to_numpy() < prior["Low"].iloc[:-1].to_numpy()
        return int((lower_highs & lower_lows).sum())

    @staticmethod
    def _rejection_reason(pattern: object) -> object:
        """Return the first phase-specific reason that prevented a trade.

        Args:
            pattern: One named row from the Phase 6 output.

        Returns:
            The applicable existing rejection reason, or ``None`` for an
            eligible trade.
        """
        if not bool(pattern.DowntrendPassed):
            return pattern.DowntrendRejectionReason
        if not bool(pattern.ConfirmationPassed):
            return pattern.ConfirmationRejectionReason
        if not bool(pattern.TradeEligible):
            return pattern.TradeRejectionReason
        return None

    @staticmethod
    def _build_source_lookup(
        dataset: pd.DataFrame,
    ) -> tuple[dict[object, int], dict[object, list[int]], dict[int, int]]:
        """Build stable source-index and same-ticker position lookups.

        Args:
            dataset: Validated canonical source data.

        Returns:
            Source-index positions, same-ticker source positions, and ticker
            ranks keyed by source position.
        """
        source_positions: dict[object, int] = {}
        ticker_positions: dict[object, list[int]] = defaultdict(list)
        ticker_ranks: dict[int, int] = {}
        for position, (source_index, ticker) in enumerate(zip(dataset.index, dataset["Ticker"], strict=True)):
            source_positions[source_index] = position
            ticker_ranks[position] = len(ticker_positions[ticker])
            ticker_positions[ticker].append(position)
        return source_positions, dict(ticker_positions), ticker_ranks

    @staticmethod
    def _validate_inputs(dataset: pd.DataFrame, trade_setups: pd.DataFrame) -> None:
        """Validate required canonical and Phase 6 fields without mutation.

        Args:
            dataset: Canonical source OHLCV data.
            trade_setups: Phase 6 pattern rows.

        Returns:
            None.

        Raises:
            DailyCandidatesReportError: If fields are missing, duplicate, or
            source indexes cannot identify pattern rows safely.
        """
        DailyCandidatesReportGenerator._require_columns(dataset, CANONICAL_OHLCV_COLUMNS, "dataset")
        DailyCandidatesReportGenerator._require_columns(trade_setups, TRADE_SETUP_COLUMNS, "trade_setups")
        if not dataset.index.is_unique:
            raise DailyCandidatesReportError("Dataset index must be unique to resolve PatternIndex values.")
        if trade_setups["PatternIndex"].isna().any():
            raise DailyCandidatesReportError("PatternIndex must not contain missing values.")

    @staticmethod
    def _require_columns(dataset: pd.DataFrame, columns: tuple[str, ...], label: str) -> None:
        """Require each named column exactly once.

        Args:
            dataset: DataFrame to inspect.
            columns: Required column names.
            label: Input label for error messages.

        Returns:
            None.

        Raises:
            DailyCandidatesReportError: If a required column is missing or duplicated.
        """
        missing = [column for column in columns if column not in dataset.columns]
        duplicates = [column for column in columns if (dataset.columns == column).sum() > 1]
        if missing or duplicates:
            details: list[str] = []
            if missing:
                details.append("missing: " + ", ".join(missing))
            if duplicates:
                details.append("duplicated: " + ", ".join(duplicates))
            raise DailyCandidatesReportError(f"Invalid {label} columns (" + "; ".join(details) + ").")
