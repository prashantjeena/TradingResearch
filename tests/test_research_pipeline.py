"""Orchestration-only tests for the completed daily research workflow."""

from __future__ import annotations

import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from pipeline.research_pipeline import PipelineError, ResearchPipeline


class _PhaseDouble:
    """Test double that records forwarding and returns a predetermined output."""

    def __init__(
        self,
        output: object,
        calls: list[str],
        name: str,
        expected_input: object | None = None,
        expected_sizing_inputs: tuple[float, float] | None = None,
        expected_latest_trading_date: pd.Timestamp | None = None,
    ) -> None:
        """Store deterministic output and optional forwarding expectations.

        Args:
            output: Object returned by the phase method.
            calls: Shared execution-order recorder.
            name: Name appended when the phase executes.
            expected_input: Optional object that must be forwarded by identity.
            expected_sizing_inputs: Optional account and risk inputs required by
                the position-sizer call.
            expected_latest_trading_date: Optional dataset maximum date expected
                by the daily scanner.
        """
        self._output = output
        self._calls = calls
        self._name = name
        self._expected_input = expected_input
        self._expected_sizing_inputs = expected_sizing_inputs
        self._expected_latest_trading_date = expected_latest_trading_date
        self.received_latest_trading_date: pd.Timestamp | None = None

    def detect(self, dataset: pd.DataFrame) -> object:
        """Record detector execution and return the configured output.

        Args:
            dataset: Original pipeline input.

        Returns:
            Predetermined detector output.
        """
        self._record()
        return self._output

    def evaluate(self, *inputs: object) -> object:
        """Record evaluator execution and verify prior-output forwarding.

        Args:
            inputs: Phase-specific inputs supplied by the pipeline.

        Returns:
            Predetermined evaluator output.
        """
        self._record(inputs[-1])
        return self._output

    def simulate(self, dataset: pd.DataFrame, trade_setup: object) -> object:
        """Record simulation execution and verify setup forwarding.

        Args:
            dataset: Original pipeline input.
            trade_setup: Setup output from the preceding phase.

        Returns:
            Predetermined simulation output.
        """
        self._record(trade_setup)
        return self._output

    def scan(self, performance: object, latest_trading_date: pd.Timestamp) -> object:
        """Record daily-scanner execution and verify performance forwarding.

        Args:
            performance: Completed performance DataFrame.
            latest_trading_date: Dataset maximum date supplied by the pipeline.

        Returns:
            Predetermined scanner output.
        """
        self._record(performance)
        self.received_latest_trading_date = latest_trading_date
        if (
            self._expected_latest_trading_date is not None
            and latest_trading_date != self._expected_latest_trading_date
        ):
            raise AssertionError("Daily Scanner did not receive the dataset maximum date.")
        return self._output

    def rank(self, signals: object) -> object:
        """Record ranking execution and verify signal forwarding.

        Args:
            signals: Scanner output.

        Returns:
            Predetermined ranking output.
        """
        self._record(signals)
        return self._output

    def enrich(self, ranked_signals: object) -> object:
        """Record enrichment execution and verify ranking forwarding.

        Args:
            ranked_signals: Ranker output.

        Returns:
            Predetermined enrichment output.
        """
        self._record(ranked_signals)
        return self._output

    def size_positions(
        self,
        enriched_signals: object,
        account_size: float,
        risk_per_trade_percent: float,
    ) -> object:
        """Record sizing execution and verify forwarded immutable settings.

        Args:
            enriched_signals: News-enricher output.
            account_size: Injected account capital.
            risk_per_trade_percent: Injected per-trade risk percentage.

        Returns:
            Predetermined sizing output.
        """
        self._record(enriched_signals)
        if self._expected_sizing_inputs is not None:
            if (account_size, risk_per_trade_percent) != self._expected_sizing_inputs:
                raise AssertionError("Position sizing settings were not forwarded unchanged.")
        return self._output

    def generate(self, sized_positions: object) -> object:
        """Record report generation and verify sized-position forwarding.

        Args:
            sized_positions: Position-sizer output.

        Returns:
            Predetermined daily report output.
        """
        self._record(sized_positions)
        return self._output

    def _record(self, supplied_input: object | None = None) -> None:
        """Record this phase and optionally assert identity-preserving forwarding.

        Args:
            supplied_input: Object supplied by the preceding phase.

        Returns:
            None.

        Raises:
            AssertionError: If the supplied object is not the expected object.
        """
        self._calls.append(self._name)
        if self._expected_input is not None and supplied_input is not self._expected_input:
            raise AssertionError(f"{self._name} did not receive prior output unchanged.")


class _FailingDetector:
    """Detector test double that raises a known failure."""

    def __init__(self, error: Exception) -> None:
        """Store the exception to raise.

        Args:
            error: Underlying error raised during detection.
        """
        self._error = error

    def detect(self, dataset: pd.DataFrame) -> pd.DataFrame:
        """Raise the configured detector failure.

        Args:
            dataset: Original pipeline input.

        Raises:
            Exception: The configured underlying error.
        """
        raise self._error


class ResearchPipelineTests(unittest.TestCase):
    """Verify orchestration, forwarding, and failure behavior only."""

    _ACCOUNT_SIZE = 100_000.0
    _RISK_PER_TRADE_PERCENT = 1.0

    def _pipeline_with_doubles(
        self,
        signals: pd.DataFrame | None = None,
    ) -> tuple[ResearchPipeline, pd.DataFrame, dict[str, object], list[str]]:
        """Build a pipeline whose phases expose orchestration behavior.

        Args:
            signals: Optional scanner output; defaults to one current signal.

        Returns:
            Pipeline, input data, expected outputs, and execution-order list.
        """
        calls: list[str] = []
        dataset = pd.DataFrame({"Date": pd.to_datetime(["2024-01-01", "2024-01-03"])})
        patterns = pd.DataFrame({"PatternName": ["Bullish Engulfing"]})
        downtrend = pd.DataFrame({"DowntrendPassed": [True]})
        confirmation = pd.DataFrame({"ConfirmationPassed": [True]})
        trade_setup = pd.DataFrame({"TradeEligible": [True]})
        simulation = pd.DataFrame({"Outcome": ["WIN"]})
        performance = pd.DataFrame({"NetReturn": [1.0]})
        statistics = {"Wins": 1}
        scanner_output = signals if signals is not None else pd.DataFrame({"Ticker": ["INFY.NS"]})
        ranked_signals = pd.DataFrame({"Rank": [1], "Ticker": ["INFY.NS"]})
        enriched_signals = pd.DataFrame({"Rank": [1], "Ticker": ["INFY.NS"], "NewsAvailable": [False]})
        sized_positions = pd.DataFrame({"Rank": [1], "Ticker": ["INFY.NS"], "Quantity": [10]})
        daily_report = pd.DataFrame({"Rank": [1], "Ticker": ["INFY.NS"]})
        pipeline = ResearchPipeline(
            account_size=self._ACCOUNT_SIZE,
            risk_per_trade_percent=self._RISK_PER_TRADE_PERCENT,
            detector=_PhaseDouble(patterns, calls, "detector"),
            downtrend_evaluator=_PhaseDouble(downtrend, calls, "downtrend", patterns),
            confirmation_evaluator=_PhaseDouble(confirmation, calls, "confirmation", downtrend),
            trade_setup_evaluator=_PhaseDouble(trade_setup, calls, "trade_setup", confirmation),
            trade_simulator=_PhaseDouble(simulation, calls, "simulation", trade_setup),
            performance_evaluator=_PhaseDouble(performance, calls, "performance", simulation),
            statistics_evaluator=_PhaseDouble(statistics, calls, "statistics", performance),
            daily_signal_scanner=_PhaseDouble(
                scanner_output,
                calls,
                "scanner",
                performance,
                expected_latest_trading_date=dataset["Date"].max(),
            ),
            signal_ranker=_PhaseDouble(ranked_signals, calls, "ranker", scanner_output),
            news_enricher=_PhaseDouble(enriched_signals, calls, "news", ranked_signals),
            position_sizer=_PhaseDouble(
                sized_positions,
                calls,
                "sizer",
                enriched_signals,
                (self._ACCOUNT_SIZE, self._RISK_PER_TRADE_PERCENT),
            ),
            daily_report_generator=_PhaseDouble(daily_report, calls, "report", sized_positions),
        )
        outputs = {
            "patterns": patterns,
            "downtrend": downtrend,
            "confirmation": confirmation,
            "trade_setup": trade_setup,
            "trade_simulation": simulation,
            "performance": performance,
            "statistics": statistics,
            "signals": scanner_output,
            "ranked_signals": ranked_signals,
            "sized_positions": sized_positions,
            "daily_report": daily_report,
            "final_report": daily_report,
        }
        return pipeline, dataset, outputs, calls

    def test_pipeline_runs_complete_workflow_in_order_and_returns_exact_outputs(self) -> None:
        """Run every stage in order and retain returned-object identity.

        Returns:
            None.

        Raises:
            None.
        """
        pipeline, dataset, outputs, calls = self._pipeline_with_doubles()

        result = pipeline.run(dataset)

        self.assertEqual(
            calls,
            [
                "detector",
                "downtrend",
                "confirmation",
                "trade_setup",
                "simulation",
                "performance",
                "statistics",
                "scanner",
                "ranker",
                "news",
                "sizer",
                "report",
            ],
        )
        self.assertEqual(tuple(result), tuple(outputs))
        for key, output in outputs.items():
            self.assertIs(result[key], output)

    def test_empty_scanner_skips_downstream_stages_and_returns_empty_reports(self) -> None:
        """Keep statistics while skipping downstream work for no current signals.

        Returns:
            None.

        Raises:
            None.
        """
        pipeline, dataset, outputs, calls = self._pipeline_with_doubles(pd.DataFrame())

        result = pipeline.run(dataset)

        self.assertEqual(
            calls,
            [
                "detector",
                "downtrend",
                "confirmation",
                "trade_setup",
                "simulation",
                "performance",
                "statistics",
                "scanner",
            ],
        )
        self.assertIs(result["statistics"], outputs["statistics"])
        for key in ("signals", "ranked_signals", "sized_positions", "daily_report", "final_report"):
            self.assertTrue(result[key].empty)

    def test_pipeline_does_not_mutate_input_dataset(self) -> None:
        """Forward the pipeline input without changing it.

        Returns:
            None.

        Raises:
            None.
        """
        pipeline, dataset, _, _ = self._pipeline_with_doubles()
        original_dataset = dataset.copy(deep=True)

        pipeline.run(dataset)

        assert_frame_equal(dataset, original_dataset)

    def test_pipeline_forwards_dataset_maximum_date_to_scanner(self) -> None:
        """Supply the scanner the unchanged maximum date from the source dataset.

        Returns:
            None.

        Raises:
            None.
        """
        pipeline, dataset, _, _ = self._pipeline_with_doubles()
        scanner = pipeline._daily_signal_scanner

        pipeline.run(dataset)

        self.assertEqual(scanner.received_latest_trading_date, dataset["Date"].max())

    def test_pipeline_wraps_phase_failure_with_original_cause(self) -> None:
        """Halt execution and retain the root exception when a phase fails.

        Returns:
            None.

        Raises:
            None.
        """
        root_error = ValueError("detector failed")
        pipeline = ResearchPipeline(
            account_size=self._ACCOUNT_SIZE,
            risk_per_trade_percent=self._RISK_PER_TRADE_PERCENT,
            detector=_FailingDetector(root_error),
        )

        with self.assertRaises(PipelineError) as context:
            pipeline.run(pd.DataFrame())

        self.assertIs(context.exception.__cause__, root_error)
        self.assertIn("Bullish Engulfing detection", str(context.exception))

    def test_orchestration_logs_downstream_sequence(self) -> None:
        """Emit informative orchestration logs for each downstream stage.

        Returns:
            None.

        Raises:
            None.
        """
        pipeline, dataset, _, _ = self._pipeline_with_doubles()

        with self.assertLogs("pipeline.research_pipeline", level="INFO") as captured_logs:
            pipeline.run(dataset)

        messages = [record.getMessage() for record in captured_logs.records]
        self.assertEqual(
            messages[-7:],
            [
                "Running Daily Scanner...",
                "Found 1 signals.",
                "Running Signal Ranking...",
                "Running News Enrichment...",
                "Running Position Sizing...",
                "Running Daily Report...",
                "Final report generated.",
            ],
        )

    def test_repeated_execution_with_identical_input_is_deterministic(self) -> None:
        """Return identical workflow outputs for identical input.

        Returns:
            None.

        Raises:
            None.
        """
        pipeline, dataset, outputs, _ = self._pipeline_with_doubles()

        first_result = pipeline.run(dataset)
        second_result = pipeline.run(dataset)

        for key, output in outputs.items():
            self.assertIs(first_result[key], output)
            self.assertIs(second_result[key], output)


if __name__ == "__main__":
    unittest.main()
