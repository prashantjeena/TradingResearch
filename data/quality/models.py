"""Structured result models for the data quality engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class RuleSeverity(StrEnum):
    """Severity assigned to a validation rule."""

    ERROR = "ERROR"
    WARNING = "WARNING"


class RuleOutcome(StrEnum):
    """Outcome produced after a validation rule evaluates a dataset."""

    PASS = "PASS"
    FAIL = "FAIL"


class ValidationStatus(StrEnum):
    """Overall status assigned to a dataset validation result."""

    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class RuleResult:
    """Result returned by one independent validation rule."""

    name: str
    description: str
    severity: RuleSeverity
    outcome: RuleOutcome
    details: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BasicSummary:
    """Compact descriptive statistics calculated for one dataset."""

    row_count: int
    first_date: str | None
    last_date: str | None
    minimum_low: float | None
    maximum_high: float | None
    average_volume: float | None


@dataclass(frozen=True, slots=True)
class DatasetValidationResult:
    """Complete, read-only validation result for one dataset file."""

    dataset_path: Path
    status: ValidationStatus
    error_count: int
    warning_count: int
    rule_results: tuple[RuleResult, ...]
    summary: BasicSummary | None
