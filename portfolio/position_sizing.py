"""Deterministic fixed-risk position sizing for ranked daily signals."""

from __future__ import annotations

import numpy as np
import pandas as pd


POSITION_SIZING_COLUMNS: tuple[str, ...] = (
    "RiskCapital",
    "RiskPerShare",
    "Quantity",
    "CapitalRequired",
    "ActualRisk",
    "TradeRecommended",
    "RecommendationReason",
)
"""Ordered position-sizing columns appended by ``PositionSizer``."""

_REQUIRED_COLUMNS = frozenset(
    {
        "Ticker",
        "EntryFill",
        "StopPrice",
        "Risk",
        "RiskPercent",
        "Rank",
        "TradeEligible",
    }
)


class PositionSizingError(ValueError):
    """Raised when ranked signals or fixed-risk sizing inputs are invalid."""


class PositionSizer:
    """Append fixed-risk position-sizing metadata without changing signal ranking."""

    def size_positions(
        self,
        ranked_signals: pd.DataFrame,
        account_size: float,
        risk_per_trade_percent: float,
    ) -> pd.DataFrame:
        """Calculate position sizes for eligible trades using fixed risk capital.

        Args:
            ranked_signals: Ranked signal DataFrame containing required trade
                setup inputs.
            account_size: Total account capital, which must be positive.
            risk_per_trade_percent: Maximum account risk per trade as a positive
                percentage.

        Returns:
            A new DataFrame with all input rows and columns preserved, plus
            ``POSITION_SIZING_COLUMNS``. Ineligible rows remain unrecommended
            and have no position metrics.

        Raises:
            PositionSizingError: If required columns are absent, an input
                parameter is non-positive, or an eligible trade has invalid
                risk or entry-fill data.
        """
        missing_columns = sorted(_REQUIRED_COLUMNS.difference(ranked_signals.columns))
        if missing_columns:
            raise PositionSizingError(
                f"Ranked signals are missing required sizing columns: {', '.join(missing_columns)}."
            )
        if account_size <= 0:
            raise PositionSizingError("account_size must be greater than zero.")
        if risk_per_trade_percent <= 0:
            raise PositionSizingError("risk_per_trade_percent must be greater than zero.")

        trade_eligible = ranked_signals["TradeEligible"].eq(True).fillna(False)
        risk_per_share = _numeric_series(ranked_signals["Risk"], "Risk")
        entry_fill = _numeric_series(ranked_signals["EntryFill"], "EntryFill")
        invalid_risk = trade_eligible & (risk_per_share.isna() | risk_per_share.le(0))
        if invalid_risk.any():
            raise PositionSizingError("Risk must be greater than zero for eligible trades.")
        invalid_entry_fill = trade_eligible & entry_fill.isna()
        if invalid_entry_fill.any():
            raise PositionSizingError("EntryFill must be numeric for eligible trades.")

        result = ranked_signals.copy()
        risk_capital_value = account_size * (risk_per_trade_percent / 100)
        risk_capital = pd.Series(pd.NA, index=result.index, dtype="Float64")
        quantity = pd.Series(pd.NA, index=result.index, dtype="Int64")
        capital_required = pd.Series(pd.NA, index=result.index, dtype="Float64")
        actual_risk = pd.Series(pd.NA, index=result.index, dtype="Float64")

        eligible_risk = risk_per_share.loc[trade_eligible]
        eligible_quantity = np.floor(risk_capital_value / eligible_risk).astype("int64")
        risk_capital.loc[trade_eligible] = risk_capital_value
        quantity.loc[trade_eligible] = eligible_quantity
        capital_required.loc[trade_eligible] = eligible_quantity * entry_fill.loc[trade_eligible]
        actual_risk.loc[trade_eligible] = eligible_quantity * eligible_risk

        trade_recommended = (trade_eligible & quantity.gt(0)).astype(bool)
        recommendation_reason = pd.Series([None] * len(result), index=result.index, dtype="object")
        recommendation_reason.loc[~trade_eligible] = "Trade was not eligible."
        recommendation_reason.loc[trade_eligible & quantity.eq(0)] = "Risk too large for account."

        result["RiskCapital"] = risk_capital
        result["RiskPerShare"] = risk_per_share.where(trade_eligible)
        result["Quantity"] = quantity
        result["CapitalRequired"] = capital_required
        result["ActualRisk"] = actual_risk
        result["TradeRecommended"] = trade_recommended
        result["RecommendationReason"] = recommendation_reason
        return result


def _numeric_series(values: pd.Series, name: str) -> pd.Series:
    """Convert a sizing input series to numeric values with clear errors.

    Args:
        values: Source values to interpret as numeric.
        name: Human-readable column name for validation errors.

    Returns:
        Numeric representation of ``values`` retaining the original index.

    Raises:
        PositionSizingError: If a non-null value cannot be interpreted as numeric.
    """
    try:
        return pd.to_numeric(values, errors="raise")
    except (TypeError, ValueError) as error:
        raise PositionSizingError(f"{name} must contain numeric values.") from error
