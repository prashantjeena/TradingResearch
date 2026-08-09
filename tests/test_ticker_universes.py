"""Tests for ordered multi-file ticker-universe loading."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal

from config import TICKER_UNIVERSE_FILES
from main import _load_ticker_universes


class TickerUniverseLoaderTests(unittest.TestCase):
    """Verify independent bucket loading without membership inference."""

    def test_loads_all_four_files_in_configured_and_file_order(self) -> None:
        """Attach exact universe labels while preserving source file order.

        Returns:
            None.

        Raises:
            None.
        """
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            files = (
                ("NIFTY50", root / "nifty50.txt"),
                ("NIFTY100", root / "nifty100.txt"),
                ("NIFTY150", root / "nifty150.txt"),
                ("NIFTY200", root / "nifty200.txt"),
            )
            files[0][1].write_text("RELIANCE.NS\nINFY.NS\n", encoding="utf-8")
            files[1][1].write_text("POLYCAB.NS\n", encoding="utf-8")
            files[2][1].write_text("TRENT.NS\n", encoding="utf-8")
            files[3][1].write_text("CAMS.NS\n", encoding="utf-8")

            result = _load_ticker_universes(files)

        expected = pd.DataFrame(
            {
                "Ticker": ["RELIANCE.NS", "INFY.NS", "POLYCAB.NS", "TRENT.NS", "CAMS.NS"],
                "Universe": ["NIFTY50", "NIFTY50", "NIFTY100", "NIFTY150", "NIFTY200"],
            }
        )
        assert_frame_equal(result, expected)

    def test_empty_universe_contributes_zero_rows_without_affecting_others(self) -> None:
        """Keep populated buckets when one independent universe is empty.

        Returns:
            None.

        Raises:
            None.
        """
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            empty_file = root / "empty.txt"
            populated_file = root / "populated.txt"
            empty_file.write_text("# no tickers\n", encoding="utf-8")
            populated_file.write_text("TCS.NS\n", encoding="utf-8")

            result = _load_ticker_universes(
                (("NIFTY100", empty_file), ("NIFTY150", populated_file))
            )

        expected = pd.DataFrame({"Ticker": ["TCS.NS"], "Universe": ["NIFTY150"]})
        assert_frame_equal(result, expected)

    def test_master_nifty200_csv_is_not_a_scanner_input(self) -> None:
        """Ensure only the four authoritative text files are configured to scan.

        Returns:
            None.

        Raises:
            None.
        """
        configured_paths = [path for _, path in TICKER_UNIVERSE_FILES]

        self.assertEqual([label for label, _ in TICKER_UNIVERSE_FILES], [
            "NIFTY50",
            "NIFTY100",
            "NIFTY150",
            "NIFTY200",
        ])
        self.assertTrue(all(path.suffix == ".txt" for path in configured_paths))
        self.assertNotIn(Path("datasets/tickers/nifty200.csv"), configured_paths)


if __name__ == "__main__":
    unittest.main()
