"""Thin orchestration layer for the completed Version 1 research engine."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd

from analysis.confirmation import ConfirmationEvaluator
from analysis.performance import TradePerformanceEvaluator
from analysis.statistics import StatisticsEvaluator
from analysis.trade_setup import TradeSetupEvaluator
from analysis.trade_simulation import TradeSimulator
from analysis.trend import DowntrendEvaluator
from news.news_enrichment import NewsEnricher
from patterns.bullish_engulfing import BullishEngulfingDetector
from portfolio.position_sizing import PositionSizer
from ranking.signal_ranker import SignalRanker
from reporting.daily_report import DailyReportGenerator
from scanner.daily_scanner import DailySignalScanner


LOGGER = logging.getLogger(__name__)


class PipelineError(RuntimeError):
    """Raised when a research phase fails during pipeline orchestration."""


@dataclass(frozen=True, slots=True)
class _PositionSizingSettings:
    """Immutable constructor-injected inputs for portfolio position sizing."""

    account_size: float
    risk_per_trade_percent: float


class ResearchPipeline:
    """Coordinate completed research phases without implementing research logic."""

    def __init__(
        self,
        account_size: float,
        risk_per_trade_percent: float,
        detector: Any | None = None,
        downtrend_evaluator: Any | None = None,
        confirmation_evaluator: Any | None = None,
        trade_setup_evaluator: Any | None = None,
        trade_simulator: Any | None = None,
        performance_evaluator: Any | None = None,
        statistics_evaluator: Any | None = None,
        daily_signal_scanner: Any | None = None,
        signal_ranker: Any | None = None,
        news_enricher: Any | None = None,
        position_sizer: Any | None = None,
        daily_report_generator: Any | None = None,
    ) -> None:
        """Create default phases or accept compatible test doubles.

        Args:
            account_size: Total account capital forwarded unchanged to
                ``PositionSizer``.
            risk_per_trade_percent: Per-trade account-risk percentage forwarded
                unchanged to ``PositionSizer``.
            detector: Object exposing ``detect(dataset)``.
            downtrend_evaluator: Object exposing ``evaluate(dataset, patterns)``.
            confirmation_evaluator: Object exposing ``evaluate(dataset, downtrend)``.
            trade_setup_evaluator: Object exposing ``evaluate(dataset, confirmation)``.
            trade_simulator: Object exposing ``simulate(dataset, trade_setup)``.
            performance_evaluator: Object exposing ``evaluate(dataset, simulation)``.
            statistics_evaluator: Object exposing ``evaluate(performance)``.
            daily_signal_scanner: Object exposing
                ``scan(performance, latest_trading_date)``.
            signal_ranker: Object exposing ``rank(signals)``.
            news_enricher: Object exposing ``enrich(ranked_signals)``.
            position_sizer: Object exposing
                ``size_positions(signals, account_size, risk_per_trade_percent)``.
            daily_report_generator: Object exposing ``generate(sized_positions)``.
        """
        self._position_sizing_settings = _PositionSizingSettings(
            account_size=account_size,
            risk_per_trade_percent=risk_per_trade_percent,
        )
        self._detector = detector or BullishEngulfingDetector()
        self._downtrend_evaluator = downtrend_evaluator or DowntrendEvaluator()
        self._confirmation_evaluator = confirmation_evaluator or ConfirmationEvaluator()
        self._trade_setup_evaluator = trade_setup_evaluator or TradeSetupEvaluator()
        self._trade_simulator = trade_simulator or TradeSimulator()
        self._performance_evaluator = performance_evaluator or TradePerformanceEvaluator()
        self._statistics_evaluator = statistics_evaluator or StatisticsEvaluator()
        self._daily_signal_scanner = daily_signal_scanner or DailySignalScanner()
        self._signal_ranker = signal_ranker or SignalRanker()
        self._news_enricher = news_enricher or NewsEnricher()
        self._position_sizer = position_sizer or PositionSizer()
        self._daily_report_generator = daily_report_generator or DailyReportGenerator()

    def run(self, dataset: pd.DataFrame) -> dict[str, Any]:
        """Run all completed research phases in frozen Version 1 order.

        Args:
            dataset: Validated canonical OHLCV data. Validation is not repeated
                because it belongs exclusively to the Data Quality Engine.

        Returns:
            Exact objects returned by every completed research phase.

        Raises:
            PipelineError: If any phase raises an exception; the original error
                is retained as the exception cause.
        """
        phase_name = "Bullish Engulfing detection"
        try:
            LOGGER.info("Running Bullish Engulfing detection...")
            patterns = self._detector.detect(dataset)
            LOGGER.info("Detected %s patterns.", len(patterns))

            phase_name = "Downtrend evaluation"
            LOGGER.info("Running Downtrend evaluation...")
            downtrend = self._downtrend_evaluator.evaluate(dataset, patterns)
            LOGGER.info("%s patterns passed.", int(downtrend["DowntrendPassed"].sum()))

            phase_name = "Confirmation evaluation"
            LOGGER.info("Running Confirmation evaluation...")
            confirmation = self._confirmation_evaluator.evaluate(dataset, downtrend)
            LOGGER.info("%s patterns confirmed.", int(confirmation["ConfirmationPassed"].sum()))

            phase_name = "Trade Setup"
            LOGGER.info("Running Trade Setup...")
            trade_setup = self._trade_setup_evaluator.evaluate(dataset, confirmation)
            LOGGER.info("%s eligible trades.", int(trade_setup["TradeEligible"].sum()))

            phase_name = "Trade Simulation"
            LOGGER.info("Running Trade Simulation...")
            trade_simulation = self._trade_simulator.simulate(dataset, trade_setup)
            LOGGER.info("Simulation complete.")

            phase_name = "Performance evaluation"
            LOGGER.info("Running Performance evaluation...")
            performance = self._performance_evaluator.evaluate(dataset, trade_simulation)
            LOGGER.info("Performance calculated.")

            phase_name = "Statistics evaluation"
            LOGGER.info("Running Statistics evaluation...")
            statistics = self._statistics_evaluator.evaluate(performance)
            LOGGER.info("Statistics complete.")

            phase_name = "Daily Scanner"
            LOGGER.info("Running Daily Scanner...")
            latest_trading_date = dataset["Date"].max()
            signals = self._daily_signal_scanner.scan(performance, latest_trading_date)
            LOGGER.info("Found %s signals.", len(signals))

            if signals.empty:
                ranked_signals = pd.DataFrame()
                sized_positions = pd.DataFrame()
                daily_report = pd.DataFrame()
                final_report = pd.DataFrame()
            else:
                phase_name = "Signal Ranking"
                LOGGER.info("Running Signal Ranking...")
                ranked_signals = self._signal_ranker.rank(signals)

                phase_name = "News Enrichment"
                LOGGER.info("Running News Enrichment...")
                enriched_signals = self._news_enricher.enrich(ranked_signals)

                phase_name = "Position Sizing"
                LOGGER.info("Running Position Sizing...")
                sized_positions = self._position_sizer.size_positions(
                    enriched_signals,
                    self._position_sizing_settings.account_size,
                    self._position_sizing_settings.risk_per_trade_percent,
                )

                phase_name = "Daily Report"
                LOGGER.info("Running Daily Report...")
                daily_report = self._daily_report_generator.generate(sized_positions)
                final_report = daily_report
                LOGGER.info("Final report generated.")
        except Exception as error:
            raise PipelineError(f"Research pipeline failed during {phase_name}.") from error

        return {
            "patterns": patterns,
            "downtrend": downtrend,
            "confirmation": confirmation,
            "trade_setup": trade_setup,
            "trade_simulation": trade_simulation,
            "performance": performance,
            "statistics": statistics,
            "signals": signals,
            "ranked_signals": ranked_signals,
            "sized_positions": sized_positions,
            "daily_report": daily_report,
            "final_report": final_report,
        }

    def run_candidate_stages(self, dataset: pd.DataFrame) -> dict[str, pd.DataFrame]:
        """Run only stages needed to form a latest-day candidate snapshot.

        Args:
            dataset: Validated canonical OHLCV data.

        Returns:
            Pattern, downtrend, confirmation, and setup outputs.

        Raises:
            PipelineError: If a required candidate stage fails.
        """
        phase_name = "Bullish Engulfing detection"
        try:
            patterns = self._detector.detect(dataset)
            phase_name = "Downtrend evaluation"
            downtrend = self._downtrend_evaluator.evaluate(dataset, patterns)
            phase_name = "Confirmation evaluation"
            confirmation = self._confirmation_evaluator.evaluate(dataset, downtrend)
            phase_name = "Trade Setup"
            trade_setup = self._trade_setup_evaluator.evaluate(dataset, confirmation)
        except Exception as error:
            raise PipelineError(f"Research pipeline failed during {phase_name}.") from error
        return {"patterns": patterns, "downtrend": downtrend, "confirmation": confirmation, "trade_setup": trade_setup}
