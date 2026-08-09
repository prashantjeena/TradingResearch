"""Tests for explicit strategy selection and strategy-specific output paths."""

from __future__ import annotations

from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import patch

from main import (
    _BULLISH_ENGULFING_RESULTS_DIRECTORY,
    _DAILY_CANDIDATES_PATH,
    _DAILY_SIGNALS_PATH,
    _HISTORICAL_RESULTS_DIRECTORY,
    _SIGNALS_RESULTS_DIRECTORY,
    STRATEGY_REGISTRY,
    _parse_arguments,
    run,
)
from strategies.registry import StrategyDefinition, StrategyRegistry


class StrategyRunnerTests(unittest.TestCase):
    """Verify selection without downloading data or invoking research logic."""

    def _registry_with_recorders(self, calls: list[str]) -> StrategyRegistry:
        """Build an injected registry whose runners only record execution.

        Args:
            calls: Mutable strategy-execution recorder.

        Returns:
            A deterministic two-strategy test registry.
        """
        def bullish_runner(strategy: StrategyDefinition) -> int:
            """Record the bullish test runner invocation."""
            calls.append(strategy.name)
            return 0

        def other_runner(strategy: StrategyDefinition) -> int:
            """Record a second registered test runner invocation."""
            calls.append(strategy.name)
            return 0

        return StrategyRegistry(
            (
                StrategyDefinition("bullish-engulfing", "bullish_engulfing", "Bullish Engulfing", bullish_runner),
                StrategyDefinition("other", "other", "Other", other_runner),
            )
        )

    @patch("main._log_run_start")
    @patch("main._log_run_completion")
    @patch("main.configure_logging")
    def test_selected_strategy_runs_once_without_running_unselected_strategies(
        self,
        mock_logging: object,
        mock_completion: object,
        mock_start: object,
    ) -> None:
        """Run exactly one explicit strategy from an injected registry."""
        calls: list[str] = []

        result = run("bullish-engulfing", self._registry_with_recorders(calls))

        self.assertEqual(result, 0)
        self.assertEqual(calls, ["bullish-engulfing"])

    @patch("main._log_run_start")
    @patch("main._log_run_completion")
    @patch("main.configure_logging")
    def test_all_runs_each_registered_strategy_once(
        self,
        mock_logging: object,
        mock_completion: object,
        mock_start: object,
    ) -> None:
        """Run every registered strategy once in registration order."""
        calls: list[str] = []

        result = run("all", self._registry_with_recorders(calls))

        self.assertEqual(result, 0)
        self.assertEqual(calls, ["bullish-engulfing", "other"])

    def test_default_cli_strategy_is_bullish_engulfing(self) -> None:
        """Preserve the existing command's Bullish Engulfing behavior."""
        self.assertEqual(_parse_arguments([]).strategy, "bullish-engulfing")

    def test_supported_cli_values_include_bearish_engulfing_and_all(self) -> None:
        """Accept the only currently registered strategy and all-mode."""
        self.assertEqual(_parse_arguments(["--strategy", "bullish-engulfing"]).strategy, "bullish-engulfing")
        self.assertEqual(_parse_arguments(["--strategy", "bearish-engulfing"]).strategy, "bearish-engulfing")
        self.assertEqual(_parse_arguments(["--strategy", "all"]).strategy, "all")
        self.assertEqual(STRATEGY_REGISTRY.names, ("bullish-engulfing", "bearish-engulfing"))

    def test_invalid_cli_strategy_is_rejected_without_fallback(self) -> None:
        """Reject unavailable strategies and show the supported CLI values."""
        error_output = StringIO()
        with redirect_stderr(error_output), self.assertRaises(SystemExit):
            _parse_arguments(["--strategy", "invalid"])

        self.assertIn("bullish-engulfing", error_output.getvalue())
        self.assertIn("bearish-engulfing", error_output.getvalue())
        self.assertIn("all", error_output.getvalue())

    def test_bullish_outputs_are_strategy_specific_and_raw_data_remains_shared(self) -> None:
        """Keep results isolated while retaining the shared datasets directory."""
        self.assertEqual(_BULLISH_ENGULFING_RESULTS_DIRECTORY, Path("results") / "bullish_engulfing")
        self.assertEqual(_DAILY_CANDIDATES_PATH.parent, _BULLISH_ENGULFING_RESULTS_DIRECTORY / "daily")
        self.assertEqual(_DAILY_SIGNALS_PATH.parent, _BULLISH_ENGULFING_RESULTS_DIRECTORY / "daily")
        self.assertEqual(_HISTORICAL_RESULTS_DIRECTORY, _BULLISH_ENGULFING_RESULTS_DIRECTORY / "historical")
        self.assertEqual(_SIGNALS_RESULTS_DIRECTORY, _BULLISH_ENGULFING_RESULTS_DIRECTORY / "signals")
        self.assertNotEqual(_HISTORICAL_RESULTS_DIRECTORY, Path("datasets"))


if __name__ == "__main__":
    unittest.main()
