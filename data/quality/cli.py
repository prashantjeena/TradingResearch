"""Command-line interface for the read-only data quality engine."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from config import LOGGING_SETTINGS
from data.quality.models import DatasetValidationResult, ValidationStatus
from data.quality.terminal_report import format_validation_report
from data.quality.validator import DataQualityValidator
from logging_config import configure_logging


LOGGER = logging.getLogger(__name__)


def _parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for directory validation.

    Args:
        arguments: Optional argument sequence, primarily for tests. ``None``
            reads arguments supplied by the shell.

    Returns:
        Parsed command-line arguments.

    Raises:
        SystemExit: If required command-line arguments are invalid.
    """
    parser = argparse.ArgumentParser(description="Validate canonical OHLCV CSV datasets.")
    parser.add_argument("directory", help="Directory containing CSV datasets to validate.")
    return parser.parse_args(arguments)


def _exit_code(results: Sequence[DatasetValidationResult]) -> int:
    """Return the process exit code implied by completed validation results.

    Args:
        results: Completed validation results.

    Returns:
        One when any dataset failed; otherwise zero.
    """
    return 1 if any(result.status is ValidationStatus.FAIL for result in results) else 0


def main(arguments: Sequence[str] | None = None) -> None:
    """Run directory validation and emit a terminal report through logging.

    Args:
        arguments: Optional command-line argument sequence.

    Returns:
        None.

    Raises:
        SystemExit: Always, with an exit status based on validation errors.
        NotADirectoryError: If the requested dataset directory does not exist.
    """
    configure_logging(LOGGING_SETTINGS)
    parsed_arguments = _parse_arguments(arguments)
    results = DataQualityValidator().validate_directory(parsed_arguments.directory)
    LOGGER.info("\n%s", format_validation_report(results))
    raise SystemExit(_exit_code(results))


if __name__ == "__main__":
    main()
