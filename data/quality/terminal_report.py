"""Terminal presentation for completed data quality validation results."""

from __future__ import annotations

from collections.abc import Sequence

from data.quality.models import DatasetValidationResult, RuleOutcome


def format_validation_report(results: Sequence[DatasetValidationResult]) -> str:
    """Format completed validation results for terminal display.

    Args:
        results: Validation results already computed by the quality engine.

    Returns:
        Human-readable, plain-text terminal report.
    """
    lines = ["DATA QUALITY VALIDATION REPORT", "=" * 30]
    if not results:
        return "\n".join([*lines, "No CSV datasets found."])

    for result in results:
        lines.extend(
            (
                "",
                f"Dataset: {result.dataset_path}",
                f"Status: {result.status} | Errors: {result.error_count} | Warnings: {result.warning_count}",
            )
        )
        if result.summary is not None:
            lines.append(
                "Summary: "
                f"rows={result.summary.row_count}, "
                f"first_date={result.summary.first_date or 'n/a'}, "
                f"last_date={result.summary.last_date or 'n/a'}, "
                f"min_low={result.summary.minimum_low if result.summary.minimum_low is not None else 'n/a'}, "
                f"max_high={result.summary.maximum_high if result.summary.maximum_high is not None else 'n/a'}, "
                f"avg_volume={result.summary.average_volume if result.summary.average_volume is not None else 'n/a'}"
            )
        for rule_result in result.rule_results:
            if rule_result.outcome is RuleOutcome.FAIL:
                lines.append(f"  [{rule_result.severity}] {rule_result.name}: {rule_result.description}")
                lines.extend(f"    - {detail}" for detail in rule_result.details)
    return "\n".join(lines)
