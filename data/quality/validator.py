"""Read-only orchestration for CSV data quality validation."""

from __future__ import annotations

from collections.abc import Collection, Iterable
from pathlib import Path

import pandas as pd

from data.quality.models import (
    BasicSummary,
    DatasetValidationResult,
    RuleOutcome,
    RuleResult,
    RuleSeverity,
    ValidationStatus,
)
from data.quality.rules import DEFAULT_RULES, ValidationRule


class DataQualityValidator:
    """Validate canonical OHLCV CSV files without modifying source datasets."""

    def __init__(
        self,
        rules: Iterable[ValidationRule] | None = None,
        enabled_rule_names: Collection[str] | None = None,
    ) -> None:
        """Create a validator with an independently configurable rule set.

        Args:
            rules: Rule implementations to register. Defaults to the standard
                quality rule set.
            enabled_rule_names: Optional names of rules to run. Supplying this
                value enables only named rules, allowing later configuration
                without editing rule implementations.

        Raises:
            ValueError: If registered rule names are duplicated or an enabled
                rule name is unknown.
        """
        registered_rules = tuple(rules if rules is not None else DEFAULT_RULES)
        rule_names = tuple(rule.name for rule in registered_rules)
        if len(set(rule_names)) != len(rule_names):
            raise ValueError("Validation rule names must be unique.")
        if enabled_rule_names is not None:
            unknown_names = set(enabled_rule_names).difference(rule_names)
            if unknown_names:
                raise ValueError(f"Unknown validation rules: {', '.join(sorted(unknown_names))}")
            registered_rules = tuple(rule for rule in registered_rules if rule.name in enabled_rule_names)
        self._rules = registered_rules

    def validate_csv(self, dataset_path: Path | str) -> DatasetValidationResult:
        """Validate one CSV file in read-only mode.

        Args:
            dataset_path: Path to the source CSV file.

        Returns:
            Complete result containing one result for each enabled rule. A file
            read failure is returned as an error result rather than raised.
        """
        path = Path(dataset_path)
        try:
            dataset = pd.read_csv(path)
        except (OSError, UnicodeDecodeError, pd.errors.ParserError) as error:
            return self._unreadable_file_result(path, error)
        return self.validate_dataframe(dataset, path)

    def validate_directory(self, directory_path: Path | str) -> tuple[DatasetValidationResult, ...]:
        """Validate every CSV file directly contained in one directory.

        Args:
            directory_path: Directory containing CSV datasets. The scan is
                deliberately non-recursive to keep scope explicit.

        Returns:
            Results ordered by file name.

        Raises:
            NotADirectoryError: If ``directory_path`` is not a directory.
        """
        directory = Path(directory_path)
        if not directory.is_dir():
            raise NotADirectoryError(f"Dataset directory does not exist: {directory}")
        return tuple(self.validate_csv(path) for path in sorted(directory.glob("*.csv")))

    def validate_dataframe(self, dataset: pd.DataFrame, dataset_path: Path | str = "<in-memory>") -> DatasetValidationResult:
        """Validate an in-memory dataset without changing its contents.

        Args:
            dataset: DataFrame to inspect. It is never modified by this method.
            dataset_path: Identifier shown in the resulting report.

        Returns:
            Complete validation result for the supplied DataFrame.
        """
        rule_results = tuple(rule.evaluate(dataset) for rule in self._rules)
        return self._build_result(Path(dataset_path), rule_results, self._basic_summary(dataset))

    @staticmethod
    def _basic_summary(dataset: pd.DataFrame) -> BasicSummary:
        """Calculate compact descriptive statistics without modifying a dataset.

        Args:
            dataset: Dataset under inspection.

        Returns:
            Summary statistics with unavailable fields represented as None.
        """
        date_values = DataQualityValidator._unique_column_or_empty(dataset, "Date", "datetime64[ns]")
        low_source = DataQualityValidator._unique_column_or_empty(dataset, "Low", "float64")
        high_source = DataQualityValidator._unique_column_or_empty(dataset, "High", "float64")
        volume_source = DataQualityValidator._unique_column_or_empty(dataset, "Volume", "float64")
        dates = pd.to_datetime(date_values, errors="coerce")
        low_values = pd.to_numeric(low_source, errors="coerce")
        high_values = pd.to_numeric(high_source, errors="coerce")
        volume_values = pd.to_numeric(volume_source, errors="coerce")
        return BasicSummary(
            row_count=len(dataset),
            first_date=dates.min().date().isoformat() if not dates.dropna().empty else None,
            last_date=dates.max().date().isoformat() if not dates.dropna().empty else None,
            minimum_low=float(low_values.min()) if not low_values.dropna().empty else None,
            maximum_high=float(high_values.max()) if not high_values.dropna().empty else None,
            average_volume=float(volume_values.mean()) if not volume_values.dropna().empty else None,
        )

    @staticmethod
    def _unique_column_or_empty(dataset: pd.DataFrame, column: str, dtype: str) -> pd.Series:
        """Return one uniquely named column or an empty Series of the given dtype.

        Args:
            dataset: Dataset under inspection.
            column: Column to retrieve when it appears exactly once.
            dtype: Dtype for the empty fallback Series.

        Returns:
            The uniquely named source column, or an empty Series when the
            column is absent or ambiguous.
        """
        if column in dataset.columns and (dataset.columns == column).sum() == 1:
            return dataset[column]
        return pd.Series(dtype=dtype)

    @staticmethod
    def _build_result(
        dataset_path: Path,
        rule_results: tuple[RuleResult, ...],
        summary: BasicSummary | None,
    ) -> DatasetValidationResult:
        """Aggregate independent rule outcomes into a dataset-level result.

        Args:
            dataset_path: Source dataset identifier.
            rule_results: Completed results from enabled independent rules.
            summary: Basic descriptive statistics for the dataset.

        Returns:
            Aggregate validation result.
        """
        error_count = sum(
            result.outcome is RuleOutcome.FAIL and result.severity is RuleSeverity.ERROR
            for result in rule_results
        )
        warning_count = sum(
            result.outcome is RuleOutcome.FAIL and result.severity is RuleSeverity.WARNING
            for result in rule_results
        )
        return DatasetValidationResult(
            dataset_path=dataset_path,
            status=ValidationStatus.FAIL if error_count else ValidationStatus.PASS,
            error_count=error_count,
            warning_count=warning_count,
            rule_results=rule_results,
            summary=summary,
        )

    @staticmethod
    def _unreadable_file_result(dataset_path: Path, error: Exception) -> DatasetValidationResult:
        """Create a structured error result for an unreadable CSV file.

        Args:
            dataset_path: File that could not be loaded.
            error: Exception raised while reading the file.

        Returns:
            Failed result containing the file-read error.
        """
        file_result = RuleResult(
            name="file_readable",
            description="Dataset must be readable as a CSV file.",
            severity=RuleSeverity.ERROR,
            outcome=RuleOutcome.FAIL,
            details=(f"{type(error).__name__}: {error}",),
        )
        return DataQualityValidator._build_result(dataset_path, (file_result,), None)
