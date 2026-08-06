"""Unit tests for the read-only data quality engine."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS
from data.quality.models import RuleOutcome, ValidationStatus
from data.quality.rules import HighLowOrderRule, MissingTradingDaysRule
from data.quality.validator import DataQualityValidator


def _valid_dataset() -> pd.DataFrame:
    """Return a compact canonical dataset suitable for validation tests.

    Returns:
        Valid canonical OHLCV sample data.
    """
    return pd.DataFrame(
        [
            ["2024-01-01", 100.0, 105.0, 95.0, 102.0, 101.0, 1_000, "TEST.NS"],
            ["2024-01-02", 102.0, 108.0, 100.0, 106.0, 105.0, 1_200, "TEST.NS"],
        ],
        columns=CANONICAL_OHLCV_COLUMNS,
    )


class DataQualityValidatorTests(unittest.TestCase):
    """Verify representative validator and rule behavior."""

    def test_valid_dataset_passes_all_error_rules(self) -> None:
        """A valid dataset must pass without errors."""
        result = DataQualityValidator().validate_dataframe(_valid_dataset())

        self.assertEqual(result.status, ValidationStatus.PASS)
        self.assertEqual(result.error_count, 0)

    def test_high_below_low_is_reported_as_error(self) -> None:
        """An impossible High-Low relationship must fail its independent rule."""
        dataset = _valid_dataset()
        dataset.loc[0, "High"] = 90.0

        result = HighLowOrderRule().evaluate(dataset)

        self.assertEqual(result.outcome, RuleOutcome.FAIL)

    def test_missing_weekday_is_warning_not_dataset_failure(self) -> None:
        """A suspected weekday gap must add a warning without failing the dataset."""
        dataset = _valid_dataset()
        dataset.loc[1, "Date"] = "2024-01-03"

        result = DataQualityValidator(rules=(MissingTradingDaysRule(),)).validate_dataframe(dataset)

        self.assertEqual(result.status, ValidationStatus.PASS)
        self.assertEqual(result.warning_count, 1)

    def test_enabled_rule_configuration_limits_execution(self) -> None:
        """Selecting enabled rules must avoid executing unselected rules."""
        result = DataQualityValidator(enabled_rule_names={"non_empty"}).validate_dataframe(_valid_dataset())

        self.assertEqual(tuple(rule.name for rule in result.rule_results), ("non_empty",))

    def test_duplicate_column_names_return_failure_without_crashing(self) -> None:
        """Ambiguous columns must produce a result instead of a summary crash."""
        dataset = pd.DataFrame([["2024-01-01", "2024-01-01"]], columns=["Date", "Date"])

        result = DataQualityValidator().validate_dataframe(dataset)

        self.assertEqual(result.status, ValidationStatus.FAIL)

    def test_directory_validation_reads_each_csv(self) -> None:
        """Directory validation must return one result for each direct CSV child."""
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            _valid_dataset().to_csv(directory / "first.csv", index=False)
            _valid_dataset().to_csv(directory / "second.csv", index=False)

            results = DataQualityValidator().validate_directory(directory)

        self.assertEqual(len(results), 2)
        self.assertTrue(all(result.status is ValidationStatus.PASS for result in results))


if __name__ == "__main__":
    unittest.main()
