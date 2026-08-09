"""Thin orchestration pipeline for the frozen Bearish Engulfing experiment."""
from __future__ import annotations
import logging
from typing import Any
import pandas as pd
from analysis.bearish_confirmation import BearishConfirmationEvaluator
from analysis.bearish_performance import BearishTradePerformanceEvaluator
from analysis.bearish_trade_setup import BearishTradeSetupEvaluator
from analysis.bearish_trade_simulation import BearishTradeSimulator
from analysis.bearish_uptrend import UptrendEvaluator
from analysis.statistics import StatisticsEvaluator
from news.news_enrichment import NewsEnricher
from patterns.bearish_engulfing import BearishEngulfingDetector
from portfolio.position_sizing import PositionSizer
from ranking.signal_ranker import SignalRanker
from reporting.daily_report import DailyReportGenerator
from scanner.daily_scanner import DailySignalScanner
from pipeline.research_pipeline import PipelineError

LOGGER=logging.getLogger(__name__)
class BearishResearchPipeline:
    """Coordinate Bearish-only phases while reusing direction-neutral services."""
    def __init__(self,account_size:float,risk_per_trade_percent:float,**overrides:Any)->None:
        """Construct the pipeline with optional compatible test doubles."""
        self._account_size=account_size;self._risk=risk_per_trade_percent
        self._detector=overrides.get("detector") or BearishEngulfingDetector();self._uptrend=overrides.get("uptrend_evaluator") or UptrendEvaluator()
        self._confirmation=overrides.get("confirmation_evaluator") or BearishConfirmationEvaluator();self._setup=overrides.get("trade_setup_evaluator") or BearishTradeSetupEvaluator();self._simulator=overrides.get("trade_simulator") or BearishTradeSimulator();self._performance=overrides.get("performance_evaluator") or BearishTradePerformanceEvaluator();self._statistics=overrides.get("statistics_evaluator") or StatisticsEvaluator();self._scanner=overrides.get("daily_signal_scanner") or DailySignalScanner();self._ranker=overrides.get("signal_ranker") or SignalRanker();self._news=overrides.get("news_enricher") or NewsEnricher();self._sizer=overrides.get("position_sizer") or PositionSizer();self._report=overrides.get("daily_report_generator") or DailyReportGenerator()
    def run(self,dataset:pd.DataFrame)->dict[str,Any]:
        """Run frozen Bearish stages in sequence without mutating the dataset.
        Raises: PipelineError: When any stage fails, preserving its cause.
        """
        phase="Bearish Engulfing detection"
        try:
            LOGGER.info("Running Bearish Engulfing detection...");patterns=self._detector.detect(dataset);LOGGER.info("Bearish Engulfing patterns: %s",len(patterns))
            phase="Uptrend evaluation";uptrend=self._uptrend.evaluate(dataset,patterns);LOGGER.info("Uptrend qualified: %s",int(uptrend["UptrendPassed"].sum()))
            phase="Confirmation evaluation";confirmation=self._confirmation.evaluate(dataset,uptrend);LOGGER.info("Confirmed: %s",int(confirmation["ConfirmationPassed"].sum()))
            phase="Trade Setup";trade_setup=self._setup.evaluate(dataset,confirmation);LOGGER.info("Eligible short trades: %s",int(trade_setup["TradeEligible"].sum()))
            phase="Trade Simulation";trade_simulation=self._simulator.simulate(dataset,trade_setup)
            phase="Performance evaluation";performance=self._performance.evaluate(dataset,trade_simulation)
            phase="Statistics evaluation";statistics=self._statistics.evaluate(performance,trend_column="UptrendPassed")
            phase="Daily Scanner";signals=self._scanner.scan(performance,dataset["Date"].max())
            if signals.empty: ranked_signals=sized_positions=daily_report=final_report=pd.DataFrame()
            else:
                phase="Signal Ranking";ranked_signals=self._ranker.rank(signals,trend_column="UptrendPassed")
                phase="News Enrichment";enriched=self._news.enrich(ranked_signals)
                phase="Position Sizing";sized_positions=self._sizer.size_positions(enriched,self._account_size,self._risk)
                phase="Daily Report";daily_report=self._report.generate(sized_positions);final_report=daily_report
        except Exception as error: raise PipelineError(f"Bearish research pipeline failed during {phase}.") from error
        return {"patterns":patterns,"uptrend":uptrend,"confirmation":confirmation,"trade_setup":trade_setup,"trade_simulation":trade_simulation,"performance":performance,"statistics":statistics,"signals":signals,"ranked_signals":ranked_signals,"sized_positions":sized_positions,"daily_report":daily_report,"final_report":final_report}
    def run_candidate_stages(self,dataset:pd.DataFrame)->dict[str,pd.DataFrame]:
        """Run only frozen stages required for a Bearish candidate snapshot.
        Raises: PipelineError: If detection, uptrend, confirmation, or setup fails.
        """
        phase="Bearish Engulfing detection"
        try:
            patterns=self._detector.detect(dataset);phase="Uptrend evaluation";uptrend=self._uptrend.evaluate(dataset,patterns);phase="Confirmation evaluation";confirmation=self._confirmation.evaluate(dataset,uptrend);phase="Trade Setup";trade_setup=self._setup.evaluate(dataset,confirmation)
        except Exception as error:raise PipelineError(f"Bearish research pipeline failed during {phase}.") from error
        return {"patterns":patterns,"uptrend":uptrend,"confirmation":confirmation,"trade_setup":trade_setup}
