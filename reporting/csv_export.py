"""CSV export for completed research-pipeline trade results."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


class CSVExportError(Exception):
    """Raised when completed research results cannot be written to CSV."""


class CSVExporter:
    """Write a completed pipeline DataFrame to a ticker-specific CSV file."""

    def export(self, trades: pd.DataFrame, ticker: str, output_directory: Path) -> Path:
        """Export trade results without changing their rows, columns, or values.

        Args:
            trades: Final DataFrame produced by the completed research pipeline.
            ticker: Source ticker used to construct the output file name.
            output_directory: Directory in which the CSV will be created.

        Returns:
            The path of the written CSV file.

        Raises:
            CSVExportError: If the destination directory or CSV cannot be written.
        """
        output_path = output_directory / f"{_safe_ticker(ticker)}_trades.csv"

        try:
            output_directory.mkdir(parents=True, exist_ok=True)
            trades.to_csv(output_path, index=False)
        except OSError as error:
            raise CSVExportError(f"Could not export research results to {output_path}.") from error

        return output_path


def _safe_ticker(ticker: str) -> str:
    """Convert a provider ticker symbol to the project's portable filename form.

    Args:
        ticker: Provider-recognized ticker symbol.

    Returns:
        A ticker string safe for use in the project output filenames.

    Raises:
        None.
    """
    return ticker.replace(".", "_").replace("/", "_").replace("\\", "_")
