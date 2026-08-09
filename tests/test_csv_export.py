"""Tests for the Phase 12 CSV research exporter."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from pandas.testing import assert_frame_equal

from reporting.csv_export import CSVExportError, CSVExporter


class CSVExporterTests(unittest.TestCase):
    """Verify faithful, filesystem-safe export of completed pipeline results."""

    def setUp(self) -> None:
        """Create an exporter and an ordered representative results DataFrame.

        Returns:
            None.

        Raises:
            None.
        """
        self.exporter = CSVExporter()
        self.trades = pd.DataFrame(
            {
                "Date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
                "Ticker": ["RELIANCE.NS", "RELIANCE.NS"],
                "Outcome": ["WIN", "LOSS"],
                "NetReturn": [1.25, -0.5],
            }
        )

    def test_export_writes_csv_creates_directory_and_returns_expected_path(self) -> None:
        """Write a ticker-specific CSV into a directory that does not yet exist.

        Returns:
            None.

        Raises:
            None.
        """
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory) / "nested" / "results"

            result = self.exporter.export(self.trades, "RELIANCE.NS", output_directory)

            self.assertEqual(result, output_directory / "RELIANCE_NS_trades.csv")
            self.assertTrue(result.is_file())

    def test_export_overwrites_existing_file(self) -> None:
        """Replace an existing ticker export rather than creating a new name.

        Returns:
            None.

        Raises:
            None.
        """
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            output_path = output_directory / "RELIANCE_NS_trades.csv"
            output_path.write_text("stale,data\n1,2\n", encoding="utf-8")

            result = self.exporter.export(self.trades, "RELIANCE.NS", output_directory)

            self.assertEqual(result, output_path)
            self.assertNotIn("stale,data", output_path.read_text(encoding="utf-8"))

    def test_export_preserves_row_column_order_and_values_after_round_trip(self) -> None:
        """Keep exported content faithful to the supplied DataFrame.

        Returns:
            None.

        Raises:
            None.
        """
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = self.exporter.export(self.trades, "RELIANCE.NS", Path(temporary_directory))

            reloaded = pd.read_csv(output_path, parse_dates=["Date"])

        assert_frame_equal(reloaded, self.trades)

    def test_export_handles_an_empty_dataframe(self) -> None:
        """Export a header-only CSV when the completed results are empty.

        Returns:
            None.

        Raises:
            None.
        """
        empty_trades = self.trades.iloc[0:0]
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = self.exporter.export(empty_trades, "INFY.NS", Path(temporary_directory))

            reloaded = pd.read_csv(output_path)

        self.assertEqual(list(reloaded.columns), list(empty_trades.columns))
        self.assertTrue(reloaded.empty)

    def test_export_wraps_filesystem_failures(self) -> None:
        """Convert output-directory filesystem errors to the public export error.

        Returns:
            None.

        Raises:
            None.
        """
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory) / "results"
            with patch.object(Path, "mkdir", side_effect=PermissionError("denied")):
                with self.assertRaises(CSVExportError) as context:
                    self.exporter.export(self.trades, "RELIANCE.NS", output_directory)

        self.assertIsInstance(context.exception.__cause__, PermissionError)

    def test_export_does_not_mutate_input(self) -> None:
        """Leave the supplied completed-results DataFrame unchanged.

        Returns:
            None.

        Raises:
            None.
        """
        original = self.trades.copy(deep=True)
        with tempfile.TemporaryDirectory() as temporary_directory:
            self.exporter.export(self.trades, "RELIANCE.NS", Path(temporary_directory))

        assert_frame_equal(self.trades, original)


if __name__ == "__main__":
    unittest.main()
