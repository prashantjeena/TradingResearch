"""Tests for the read-only latest-day Bullish Engulfing candidates report."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal

from analysis.trade_setup import TRADE_SETUP_COLUMNS
from main import (
    _DAILY_CANDIDATES_PATH,
    _DAILY_SIGNALS_PATH,
    _consolidate_daily_candidates,
    _export_daily_candidates,
    _export_daily_signals,
)
from reporting.daily_candidates import DAILY_CANDIDATE_COLUMNS, DailyCandidatesReportGenerator


class DailyCandidatesReportTests(unittest.TestCase):
    """Verify candidate inclusion, ordering, schema, and immutability."""

    def setUp(self) -> None:
        """Build a canonical seven-day source and two detected pattern rows.

        Returns:
            None.

        Raises:
            None.
        """
        dates = pd.date_range("2026-08-01", periods=7, freq="D")
        self.dataset = pd.DataFrame(
            {
                "Date": dates,
                "Open": [100.0] * 7,
                "High": [111.0, 110.0, 109.0, 108.0, 108.0, 109.0, 104.0],
                "Low": [91.0, 90.0, 89.0, 88.0, 88.0, 89.0, 84.0],
                "Close": [95.0] * 7,
                "Adj Close": [pd.NA] * 7,
                "Volume": [1_000] * 7,
                "Ticker": ["INFY.NS"] * 7,
            },
            index=[10, 11, 12, 13, 14, 15, 16],
        )
        self.trade_setups = self._trade_setups()
        self.generator = DailyCandidatesReportGenerator()

    def _trade_setups(self) -> pd.DataFrame:
        """Create Phase 6-compatible rows for one historical and one latest pattern.

        Returns:
            A DataFrame with the exact Phase 6 column schema.

        Raises:
            None.
        """
        rows: list[dict[str, object]] = []
        for index, downtrend_passed, confirmation_passed, eligible in (
            (15, True, True, True),
            (16, False, False, False),
        ):
            candle = self.dataset.loc[index]
            row = {column: None for column in TRADE_SETUP_COLUMNS}
            row.update(
                {
                    "Date": candle["Date"],
                    "Open": candle["Open"],
                    "High": candle["High"],
                    "Low": candle["Low"],
                    "Close": candle["Close"],
                    "Adj Close": candle["Adj Close"],
                    "Volume": candle["Volume"],
                    "Ticker": candle["Ticker"],
                    "PatternName": "Bullish Engulfing",
                    "PatternIndex": index,
                    "PreviousDate": self.dataset.loc[index - 1, "Date"],
                    "DowntrendPassed": downtrend_passed,
                    "DowntrendRejectionReason": "Downtrend rejected: 2 of 4 lower-high/lower-low comparisons; requires at least 3.",
                    "ConfirmationPassed": confirmation_passed,
                    "ConfirmationDate": self.dataset.loc[index, "Date"] if confirmation_passed else None,
                    "ConfirmationIndex": index if confirmation_passed else None,
                    "ConfirmationRejectionReason": "Pattern did not pass downtrend evaluation.",
                    "EntryDate": self.dataset.loc[index, "Date"] if eligible else None,
                    "EntryFill": 100.1 if eligible else None,
                    "StopPrice": 85.0 if eligible else None,
                    "TargetPrice": 130.3 if eligible else None,
                    "TradeEligible": eligible,
                    "TradeRejectionReason": "Pattern did not pass downtrend evaluation.",
                }
            )
            rows.append(row)
        return pd.DataFrame(rows, columns=TRADE_SETUP_COLUMNS)

    def test_includes_only_latest_day_pattern_even_if_downtrend_fails(self) -> None:
        """Include latest detections without requiring any later-stage approval.

        Returns:
            None.

        Raises:
            None.
        """
        result = self.generator.generate(
            self.dataset,
            self.trade_setups,
            pd.Timestamp("2026-08-07 15:30:00"),
            "NIFTY50",
        )

        self.assertEqual(list(result.columns), list(DAILY_CANDIDATE_COLUMNS))
        self.assertEqual(len(result), 1)
        self.assertEqual(result.loc[0, "PatternDate"], pd.Timestamp("2026-08-07"))
        self.assertFalse(result.loc[0, "DowntrendPassed"])
        self.assertFalse(result.loc[0, "ConfirmationPassed"])
        self.assertFalse(result.loc[0, "TradeEligible"])
        self.assertEqual(result.loc[0, "Universe"], "NIFTY50")
        self.assertEqual(result.loc[0, "DowntrendScore"], 2)
        self.assertEqual(result.loc[0, "CandidateStatus"], "NEAR FILTER")

    def test_uses_source_candles_for_previous_ohlc_and_diagnostic_score(self) -> None:
        """Expose existing source values and an unparsed 0--4 trend count.

        Returns:
            None.

        Raises:
            None.
        """
        latest_row = self.trade_setups.iloc[[1]].copy()
        latest_row["DowntrendPassed"] = True
        latest_row["DowntrendRejectionReason"] = None
        result = self.generator.generate(self.dataset, latest_row, pd.Timestamp("2026-08-07"), "NIFTY100")

        self.assertEqual(result.loc[0, "PreviousOpen"], 100.0)
        self.assertEqual(result.loc[0, "PreviousHigh"], 109.0)
        self.assertEqual(result.loc[0, "PreviousLow"], 89.0)
        self.assertEqual(result.loc[0, "PreviousClose"], 95.0)
        self.assertEqual(result.loc[0, "DowntrendScore"], 2)

    def test_candidate_status_mapping_is_presentation_only(self) -> None:
        """Map every available diagnostic score without changing eligibility.

        Returns:
            None.

        Raises:
            None.
        """
        status = self.generator._candidate_status

        self.assertEqual(status(4), "PASSED DOWNTREND")
        self.assertEqual(status(3), "PASSED DOWNTREND")
        self.assertEqual(status(2), "NEAR FILTER")
        self.assertEqual(status(1), "REJECTED")
        self.assertEqual(status(0), "REJECTED")

    def test_empty_candidates_export_as_headers_only(self) -> None:
        """Produce a daily snapshot schema even when no pattern is current.

        Returns:
            None.

        Raises:
            None.
        """
        result = self.generator.generate(self.dataset, self.trade_setups, pd.Timestamp("2026-08-08"), "NIFTY50")
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / _DAILY_CANDIDATES_PATH
            _export_daily_candidates(result, output_path)
            reloaded = pd.read_csv(output_path)

        self.assertTrue(result.empty)
        self.assertTrue(reloaded.empty)
        self.assertEqual(list(reloaded.columns), list(DAILY_CANDIDATE_COLUMNS))

    def test_candidate_csv_formats_prices_without_changing_source_precision(self) -> None:
        """Format only the exported values while retaining numeric source data.

        Returns:
            None.

        Raises:
            None.
        """
        candidates = self.generator.generate(
            self.dataset, self.trade_setups, pd.Timestamp("2026-08-07"), "NIFTY50"
        )
        candidates.loc[0, "Low"] = 1155.5999755859375
        original = candidates.copy(deep=True)
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / _DAILY_CANDIDATES_PATH
            _export_daily_candidates(candidates, output_path)
            reloaded = pd.read_csv(output_path, dtype=str)

        self.assertEqual(reloaded.loc[0, "Open"], "100.00")
        self.assertEqual(reloaded.loc[0, "Low"], "1155.60")
        assert_frame_equal(candidates, original)

    def test_consolidation_preserves_configured_universe_frame_order(self) -> None:
        """Keep diagnostics grouped by the caller's configured universe order.

        Returns:
            None.

        Raises:
            None.
        """
        def frame(universe: str, ticker: str, score: int) -> pd.DataFrame:
            """Build one candidate row with the report's exact schema.

            Returns:
                A one-row candidate DataFrame.
            """
            values = {column: None for column in DAILY_CANDIDATE_COLUMNS}
            values.update({"Universe": universe, "Ticker": ticker, "DowntrendScore": score})
            return pd.DataFrame([values], columns=DAILY_CANDIDATE_COLUMNS)

        frame_50_low = frame("NIFTY50", "INFY.NS", 1)
        frame_50_high = frame("NIFTY50", "RELIANCE.NS", 2)
        frame_50_high_equal = frame("NIFTY50", "TCS.NS", 2)
        frame_200 = frame("NIFTY200", "CAMS.NS", 4)

        result = _consolidate_daily_candidates(
            [
                frame_50_low,
                frame_50_high,
                frame_50_high_equal,
                pd.DataFrame(columns=DAILY_CANDIDATE_COLUMNS),
                frame_200,
            ]
        )

        self.assertEqual(list(result["Universe"]), ["NIFTY50", "NIFTY50", "NIFTY50", "NIFTY200"])
        self.assertEqual(list(result["Ticker"]), ["RELIANCE.NS", "TCS.NS", "INFY.NS", "CAMS.NS"])

    def test_daily_report_paths_use_the_dedicated_directory(self) -> None:
        """Keep daily-only snapshots separate from ticker-level trade history.

        Returns:
            None.

        Raises:
            None.
        """
        self.assertEqual(
            _DAILY_SIGNALS_PATH,
            Path("results") / "bullish_engulfing" / "daily" / "daily_signals.csv",
        )
        self.assertEqual(
            _DAILY_CANDIDATES_PATH,
            Path("results") / "bullish_engulfing" / "daily" / "daily_candidates.csv",
        )

    def test_empty_daily_signals_create_headers_in_the_daily_directory(self) -> None:
        """Keep the actionable-report snapshot available even with no signals.

        Returns:
            None.

        Raises:
            None.
        """
        empty_signals = pd.DataFrame(columns=["Ticker", "EntryDate"])
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / _DAILY_SIGNALS_PATH
            _export_daily_signals(empty_signals, output_path)
            reloaded = pd.read_csv(output_path)

        self.assertTrue(reloaded.empty)
        self.assertEqual(list(reloaded.columns), ["Ticker", "EntryDate"])

    def test_source_dataframes_are_not_mutated(self) -> None:
        """Keep source OHLCV and Phase 6 outputs read-only.

        Returns:
            None.

        Raises:
            None.
        """
        original_dataset = self.dataset.copy(deep=True)
        original_setups = self.trade_setups.copy(deep=True)

        self.generator.generate(self.dataset, self.trade_setups, pd.Timestamp("2026-08-07"), "NIFTY50")

        assert_frame_equal(self.dataset, original_dataset)
        assert_frame_equal(self.trade_setups, original_setups)


if __name__ == "__main__":
    unittest.main()
