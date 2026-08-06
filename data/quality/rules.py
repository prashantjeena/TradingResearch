"""Independent validation rules for canonical OHLCV datasets."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

import pandas as pd

from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS
from data.quality.models import RuleOutcome, RuleResult, RuleSeverity


class ValidationRule(Protocol):
    """Contract implemented by every independent dataset validation rule."""

    name: str
    description: str
    severity: RuleSeverity

    def evaluate(self, dataset: pd.DataFrame) -> RuleResult:
        """Inspect a dataset and return a structured result without modifying it."""


def _result(
    name: str,
    description: str,
    severity: RuleSeverity,
    passed: bool,
    details: Iterable[str],
) -> RuleResult:
    """Create an immutable result for a validation rule.

    Args:
        name: Stable identifier of the rule.
        description: Human-readable explanation of the rule.
        severity: Severity applied when the rule fails.
        passed: Whether the dataset satisfied the rule.
        details: Concise observations produced by the rule.

    Returns:
        A structured rule result.
    """
    return RuleResult(
        name=name,
        description=description,
        severity=severity,
        outcome=RuleOutcome.PASS if passed else RuleOutcome.FAIL,
        details=tuple(details),
    )


def _has_unique_columns(dataset: pd.DataFrame, columns: Iterable[str]) -> bool:
    """Return whether every named column exists exactly once.

    Args:
        dataset: Dataset under inspection.
        columns: Column names required by a rule.

    Returns:
        True when every requested column is present and non-duplicated.
    """
    return all(column in dataset.columns and (dataset.columns == column).sum() == 1 for column in columns)


def _numeric_values(dataset: pd.DataFrame, column: str) -> pd.Series | None:
    """Return a non-mutating numeric view of one uniquely named column.

    Args:
        dataset: Dataset under inspection.
        column: Name of the column to convert.

    Returns:
        Numeric values with unparseable entries represented as missing, or None
        when the column does not exist exactly once.
    """
    if not _has_unique_columns(dataset, (column,)):
        return None
    return pd.to_numeric(dataset[column], errors="coerce")


def _parsed_dates(dataset: pd.DataFrame) -> pd.Series | None:
    """Return a non-mutating parsed-date view of the Date column.

    Args:
        dataset: Dataset under inspection.

    Returns:
        Parsed dates with invalid entries represented as missing, or None when
        the Date column does not exist exactly once.
    """
    if not _has_unique_columns(dataset, ("Date",)):
        return None
    return pd.to_datetime(dataset["Date"], errors="coerce")


class CanonicalSchemaRule:
    """Require exactly the canonical OHLCV columns in the canonical order."""

    name = "canonical_schema"
    description = "Dataset columns must exactly match the canonical OHLCV schema and order."
    severity = RuleSeverity.ERROR

    def evaluate(self, dataset: pd.DataFrame) -> RuleResult:
        """Validate the complete canonical schema and column order.

        Args:
            dataset: Dataset under inspection.

        Returns:
            Structured schema-validation result.
        """
        actual_columns = tuple(str(column) for column in dataset.columns)
        expected_columns = CANONICAL_OHLCV_COLUMNS
        if actual_columns == expected_columns:
            return _result(self.name, self.description, self.severity, True, ("Canonical schema is valid.",))

        missing_columns = [column for column in expected_columns if column not in actual_columns]
        unexpected_columns = [column for column in actual_columns if column not in expected_columns]
        details = ["Expected order: " + ", ".join(expected_columns)]
        details.append("Actual order: " + ", ".join(actual_columns))
        if missing_columns:
            details.append("Missing columns: " + ", ".join(missing_columns))
        if unexpected_columns:
            details.append("Unexpected columns: " + ", ".join(unexpected_columns))
        if len(set(actual_columns)) != len(actual_columns):
            details.append("Duplicate column names detected.")
        return _result(self.name, self.description, self.severity, False, details)


class DataTypesRule:
    """Require semantically parseable dates, numeric fields, and tickers."""

    name = "data_types"
    description = "Date, numeric OHLCV fields, and Ticker values must be semantically valid."
    severity = RuleSeverity.ERROR

    def evaluate(self, dataset: pd.DataFrame) -> RuleResult:
        """Validate field parseability without changing source values.

        Args:
            dataset: Dataset under inspection.

        Returns:
            Structured data-type validation result.
        """
        required_columns = ("Date", "Open", "High", "Low", "Close", "Adj Close", "Volume", "Ticker")
        if not _has_unique_columns(dataset, required_columns):
            return _result(self.name, self.description, self.severity, False, ("Required columns are absent or duplicated.",))

        details: list[str] = []
        parsed_dates = _parsed_dates(dataset)
        assert parsed_dates is not None
        invalid_dates = int(parsed_dates.notna().eq(False).sum() - dataset["Date"].isna().sum())
        if invalid_dates:
            details.append(f"Invalid Date values: {invalid_dates}.")

        for column in ("Open", "High", "Low", "Close", "Adj Close", "Volume"):
            numeric_values = _numeric_values(dataset, column)
            assert numeric_values is not None
            invalid_values = int(numeric_values.notna().eq(False).sum() - dataset[column].isna().sum())
            if invalid_values:
                details.append(f"Non-numeric {column} values: {invalid_values}.")

        ticker_values = dataset["Ticker"]
        invalid_tickers = int((ticker_values.notna() & ~ticker_values.astype("string").str.strip().ne("")).sum())
        if invalid_tickers:
            details.append(f"Blank Ticker values: {invalid_tickers}.")

        return _result(
            self.name,
            self.description,
            self.severity,
            not details,
            details or ("All non-missing values have valid semantic types.",),
        )


class EmptyDatasetRule:
    """Require at least one data row."""

    name = "non_empty"
    description = "Dataset must contain at least one row."
    severity = RuleSeverity.ERROR

    def evaluate(self, dataset: pd.DataFrame) -> RuleResult:
        """Validate that the dataset contains one or more rows.

        Args:
            dataset: Dataset under inspection.

        Returns:
            Structured empty-dataset validation result.
        """
        row_count = len(dataset)
        return _result(
            self.name,
            self.description,
            self.severity,
            row_count > 0,
            (f"Rows: {row_count}.",),
        )


class DuplicateRowsRule:
    """Reject duplicate complete records."""

    name = "duplicate_rows"
    description = "Dataset must not contain duplicate complete rows."
    severity = RuleSeverity.ERROR

    def evaluate(self, dataset: pd.DataFrame) -> RuleResult:
        """Validate that no complete records are duplicated.

        Args:
            dataset: Dataset under inspection.

        Returns:
            Structured duplicate-row validation result.
        """
        duplicate_count = int(dataset.duplicated().sum())
        return _result(
            self.name,
            self.description,
            self.severity,
            duplicate_count == 0,
            (f"Duplicate rows: {duplicate_count}.",),
        )


class DuplicateDatesRule:
    """Reject multiple rows carrying the same valid date."""

    name = "duplicate_dates"
    description = "Dataset must not contain duplicate valid dates."
    severity = RuleSeverity.ERROR

    def evaluate(self, dataset: pd.DataFrame) -> RuleResult:
        """Validate date uniqueness independently of other rules.

        Args:
            dataset: Dataset under inspection.

        Returns:
            Structured duplicate-date validation result.
        """
        dates = _parsed_dates(dataset)
        if dates is None:
            return _result(self.name, self.description, self.severity, False, ("Date column is absent or duplicated.",))
        duplicate_count = int(dates[dates.notna()].duplicated().sum())
        return _result(self.name, self.description, self.severity, duplicate_count == 0, (f"Duplicate valid dates: {duplicate_count}.",))


class DatesSortedRule:
    """Require valid dates to be in ascending order."""

    name = "dates_sorted"
    description = "Valid dates must be sorted in ascending order."
    severity = RuleSeverity.ERROR

    def evaluate(self, dataset: pd.DataFrame) -> RuleResult:
        """Validate date ordering independently of schema or duplicate checks.

        Args:
            dataset: Dataset under inspection.

        Returns:
            Structured date-order validation result.
        """
        dates = _parsed_dates(dataset)
        if dates is None:
            return _result(self.name, self.description, self.severity, False, ("Date column is absent or duplicated.",))
        valid_dates = dates.dropna()
        inversions = int((valid_dates.diff() < pd.Timedelta(0)).sum())
        return _result(self.name, self.description, self.severity, inversions == 0, (f"Date-order inversions: {inversions}.",))


class MissingValuesRule:
    """Reject missing values except for the permitted Adj Close field."""

    name = "missing_values"
    description = "Required fields must not be missing; Adj Close may be missing when unavailable from a provider."
    severity = RuleSeverity.ERROR

    def evaluate(self, dataset: pd.DataFrame) -> RuleResult:
        """Validate missing values and permitted adjusted-close NaNs.

        Args:
            dataset: Dataset under inspection.

        Returns:
            Structured missing-value validation result.
        """
        required_columns = ("Date", "Open", "High", "Low", "Close", "Volume", "Ticker")
        if not _has_unique_columns(dataset, required_columns):
            return _result(self.name, self.description, self.severity, False, ("Required columns are absent or duplicated.",))

        details: list[str] = []
        for column in required_columns:
            missing_count = int(dataset[column].isna().sum())
            if missing_count:
                details.append(f"Missing or NaN {column} values: {missing_count}.")
        if _has_unique_columns(dataset, ("Adj Close",)):
            adjusted_close_missing = int(dataset["Adj Close"].isna().sum())
            if adjusted_close_missing:
                details.append(f"Permitted missing Adj Close values: {adjusted_close_missing}.")

        has_required_missing = any(detail.startswith("Missing or NaN") for detail in details)
        return _result(
            self.name,
            self.description,
            self.severity,
            not has_required_missing,
            details or ("No missing values detected.",),
        )


class NegativePricesRule:
    """Reject negative Open, High, Low, Close, or Adj Close prices."""

    name = "negative_prices"
    description = "Price fields must not contain negative values."
    severity = RuleSeverity.ERROR

    def evaluate(self, dataset: pd.DataFrame) -> RuleResult:
        """Validate non-negative values in all price columns.

        Args:
            dataset: Dataset under inspection.

        Returns:
            Structured negative-price validation result.
        """
        details: list[str] = []
        for column in ("Open", "High", "Low", "Close", "Adj Close"):
            values = _numeric_values(dataset, column)
            if values is None:
                details.append(f"{column} column is absent or duplicated.")
                continue
            negative_count = int((values < 0).sum())
            if negative_count:
                details.append(f"Negative {column} values: {negative_count}.")
        return _result(self.name, self.description, self.severity, not details, details or ("No negative prices detected.",))


class NegativeVolumeRule:
    """Reject negative trading volumes."""

    name = "negative_volume"
    description = "Volume must not contain negative values."
    severity = RuleSeverity.ERROR

    def evaluate(self, dataset: pd.DataFrame) -> RuleResult:
        """Validate non-negative volume values.

        Args:
            dataset: Dataset under inspection.

        Returns:
            Structured negative-volume validation result.
        """
        values = _numeric_values(dataset, "Volume")
        if values is None:
            return _result(self.name, self.description, self.severity, False, ("Volume column is absent or duplicated.",))
        negative_count = int((values < 0).sum())
        return _result(self.name, self.description, self.severity, negative_count == 0, (f"Negative Volume values: {negative_count}.",))


class HighLowOrderRule:
    """Reject rows where High is less than Low."""

    name = "high_not_below_low"
    description = "High must be greater than or equal to Low for every comparable row."
    severity = RuleSeverity.ERROR

    def evaluate(self, dataset: pd.DataFrame) -> RuleResult:
        """Validate the High >= Low relationship.

        Args:
            dataset: Dataset under inspection.

        Returns:
            Structured high-low ordering validation result.
        """
        high_values = _numeric_values(dataset, "High")
        low_values = _numeric_values(dataset, "Low")
        if high_values is None or low_values is None:
            return _result(self.name, self.description, self.severity, False, ("High or Low column is absent or duplicated.",))
        invalid_count = int((high_values < low_values).sum())
        return _result(self.name, self.description, self.severity, invalid_count == 0, (f"Rows with High < Low: {invalid_count}.",))


class OpenCloseRangeRule:
    """Require Open and Close to lie within the High-Low range."""

    name = "open_close_within_range"
    description = "Open and Close must lie within the inclusive Low-to-High range."
    severity = RuleSeverity.ERROR

    def evaluate(self, dataset: pd.DataFrame) -> RuleResult:
        """Validate core per-candle OHLC relationships.

        Args:
            dataset: Dataset under inspection.

        Returns:
            Structured Open/Close range validation result.
        """
        values = {column: _numeric_values(dataset, column) for column in ("Open", "High", "Low", "Close")}
        if any(value is None for value in values.values()):
            return _result(self.name, self.description, self.severity, False, ("One or more OHLC columns are absent or duplicated.",))
        open_values = values["Open"]
        high_values = values["High"]
        low_values = values["Low"]
        close_values = values["Close"]
        assert open_values is not None and high_values is not None and low_values is not None and close_values is not None
        invalid_open = int(((open_values < low_values) | (open_values > high_values)).sum())
        invalid_close = int(((close_values < low_values) | (close_values > high_values)).sum())
        invalid_count = invalid_open + invalid_close
        return _result(
            self.name,
            self.description,
            self.severity,
            invalid_count == 0,
            (f"Out-of-range Open values: {invalid_open}. Out-of-range Close values: {invalid_close}.",),
        )


class MissingTradingDaysRule:
    """Report weekdays absent between the first and last valid dataset dates."""

    name = "missing_trading_days"
    description = "Missing weekdays are reported for review and never fail the dataset."
    severity = RuleSeverity.WARNING

    def evaluate(self, dataset: pd.DataFrame) -> RuleResult:
        """Report suspected missing weekdays without assuming an exchange calendar.

        Args:
            dataset: Dataset under inspection.

        Returns:
            Structured warning result. Exchange holidays may be included in the
            reported count and require later calendar-aware validation.
        """
        dates = _parsed_dates(dataset)
        if dates is None:
            return _result(self.name, self.description, self.severity, False, ("Date column is absent or duplicated.",))
        valid_dates = pd.DatetimeIndex(dates.dropna().drop_duplicates())
        if len(valid_dates) < 2:
            return _result(self.name, self.description, self.severity, True, ("Fewer than two valid dates; no gap analysis performed.",))
        expected_dates = pd.bdate_range(valid_dates.min(), valid_dates.max())
        missing_dates = expected_dates.difference(valid_dates)
        if missing_dates.empty:
            return _result(self.name, self.description, self.severity, True, ("No missing weekdays detected.",))
        examples = ", ".join(date.strftime("%Y-%m-%d") for date in missing_dates[:5])
        details = (
            f"Suspected missing weekdays: {len(missing_dates)} (exchange holidays may be included).",
            f"First examples: {examples}.",
        )
        return _result(self.name, self.description, self.severity, False, details)


DEFAULT_RULES: tuple[ValidationRule, ...] = (
    CanonicalSchemaRule(),
    DataTypesRule(),
    EmptyDatasetRule(),
    DuplicateRowsRule(),
    DuplicateDatesRule(),
    DatesSortedRule(),
    MissingValuesRule(),
    NegativePricesRule(),
    NegativeVolumeRule(),
    HighLowOrderRule(),
    OpenCloseRangeRule(),
    MissingTradingDaysRule(),
)
"""Default independent rule set for canonical OHLCV datasets."""
