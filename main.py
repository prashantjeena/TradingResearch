"""Command-line entry point for the historical-data download workflow."""

from __future__ import annotations

import argparse
import logging
from importlib import import_module
from pathlib import Path

import pandas as pd

from config import (
    ACCOUNT_SIZE,
    DOWNLOAD_SETTINGS,
    LOGGING_SETTINGS,
    PROVIDER_SETTINGS,
    RISK_PER_TRADE_PERCENT,
    TICKER_UNIVERSE_FILES,
)
from data.ticker_universe import load_ticker_universes, load_tickers
from data.providers.base_provider import MarketDataProvider, ProviderError
from logging_config import configure_logging
from pipeline.research_pipeline import PipelineError, ResearchPipeline
from pipeline.bearish_research_pipeline import BearishResearchPipeline
from reporting.bearish_daily_candidates import (
    BEARISH_DAILY_CANDIDATE_COLUMNS,
    BEARISH_DAILY_CANDIDATE_PRICE_COLUMNS,
    BearishDailyCandidatesReportGenerator,
)
from reporting.daily_candidates import (
    DAILY_CANDIDATE_COLUMNS,
    DAILY_CANDIDATE_PRICE_COLUMNS,
    DailyCandidatesReportGenerator,
)
from reporting.csv_export import CSVExportError, CSVExporter
from scanner.daily_scanner import DailySignalScanner
from strategies.registry import StrategyDefinition, StrategyRegistry


LOGGER = logging.getLogger(__name__)


_DAILY_SIGNAL_COLUMNS: tuple[str, ...] = (
    "Universe",
    "Ticker",
    "Rank",
    "RankScore",
    "EntryDate",
    "EntryPrice",
    "StopLoss",
    "TargetPrice",
    "RiskPercent",
    "Shares",
    "CapitalRequired",
    "Confirmation",
    "Downtrend",
    "NewsSentiment",
    "NewsHeadline",
)

_UNIVERSE_ORDER: tuple[str, ...] = tuple(universe for universe, _ in TICKER_UNIVERSE_FILES)
_BULLISH_ENGULFING_RESULTS_DIRECTORY = Path("results") / "bullish_engulfing"
_DAILY_REPORT_DIRECTORY = _BULLISH_ENGULFING_RESULTS_DIRECTORY / "daily"
_DAILY_SIGNALS_PATH = _DAILY_REPORT_DIRECTORY / "daily_signals.csv"
_DAILY_CANDIDATES_PATH = _DAILY_REPORT_DIRECTORY / "daily_candidates.csv"
_HISTORICAL_RESULTS_DIRECTORY = _BULLISH_ENGULFING_RESULTS_DIRECTORY / "historical"
_SIGNALS_RESULTS_DIRECTORY = _BULLISH_ENGULFING_RESULTS_DIRECTORY / "signals"
_BEARISH_ENGULFING_RESULTS_DIRECTORY = Path("results") / "bearish_engulfing"
_BEARISH_DAILY_REPORT_DIRECTORY = _BEARISH_ENGULFING_RESULTS_DIRECTORY / "daily"
_BEARISH_DAILY_SIGNALS_PATH = _BEARISH_DAILY_REPORT_DIRECTORY / "daily_signals.csv"
_BEARISH_DAILY_CANDIDATES_PATH = _BEARISH_DAILY_REPORT_DIRECTORY / "daily_candidates.csv"
_BEARISH_HISTORICAL_RESULTS_DIRECTORY = _BEARISH_ENGULFING_RESULTS_DIRECTORY / "historical"
_BEARISH_SIGNALS_RESULTS_DIRECTORY = _BEARISH_ENGULFING_RESULTS_DIRECTORY / "signals"
_RUN_DATASET_CACHE: dict[str, pd.DataFrame] = {}


def _load_provider(class_path: str) -> MarketDataProvider:
    """Instantiate the provider class named by a dotted import path.

    Args:
        class_path: Dotted class path, for example
            ``"data.providers.yfinance_provider.YFinanceProvider"``.

    Returns:
        An instance implementing ``MarketDataProvider``.

    Raises:
        ValueError: If the configured class path is invalid or does not name a
            ``MarketDataProvider`` implementation.
        ImportError: If the provider module cannot be imported.
        AttributeError: If the provider class is absent from its module.
    """
    module_path, separator, class_name = class_path.rpartition(".")
    if not separator or not module_path or not class_name:
        raise ValueError(f"Invalid provider class path: {class_path!r}")

    provider_module = import_module(module_path)
    provider_class = getattr(provider_module, class_name)
    if not isinstance(provider_class, type) or not issubclass(provider_class, MarketDataProvider):
        raise ValueError(f"Configured provider does not implement MarketDataProvider: {class_path}")

    return provider_class()


def _dataset_path(output_directory: Path, ticker: str, interval: str) -> Path:
    """Build a portable CSV file path for one ticker and interval.

    Args:
        output_directory: Directory configured for raw datasets.
        ticker: Provider-recognized ticker symbol.
        interval: Bar interval included in the output file name.

    Returns:
        The CSV path to use for the requested dataset.

    Raises:
        None.
    """
    safe_ticker = ticker.replace(".", "_").replace("/", "_").replace("\\", "_")
    return output_directory / f"{safe_ticker}_{interval}.csv"


def _load_tickers(ticker_file_path: Path) -> tuple[str, ...]:
    """Load ticker symbols from a plain-text ticker universe file.

    Args:
        ticker_file_path: Path to a file containing one ticker per line.

    Returns:
        Ticker symbols in the same order as their non-empty, non-comment lines.

    Raises:
        OSError: If the ticker universe file cannot be read.
        UnicodeError: If the ticker universe file is not valid UTF-8 text.
    """
    return load_tickers(ticker_file_path)


def _load_ticker_universes(
    universe_files: tuple[tuple[str, Path], ...],
) -> pd.DataFrame:
    """Load all configured ticker buckets while isolating file-level failures.

    Args:
        universe_files: Ordered pairs of universe labels and ticker-file paths.

    Returns:
        A DataFrame with exactly ``Ticker`` and ``Universe`` columns in source
        file and line order.

    Raises:
        None.
    """
    return load_ticker_universes(universe_files)


def _daily_signal_rows(
    sized_positions: pd.DataFrame,
    ticker: str,
    universe: str,
) -> pd.DataFrame:
    """Project one ticker's already-sized signals into the daily CSV schema.

    Args:
        sized_positions: Existing post-position-sizing pipeline output.
        ticker: Ticker being processed, used only when source data lacks a
            ticker column.
        universe: Configured scanner bucket for the current ticker.

    Returns:
        A new DataFrame containing the consolidated daily-signal columns.

    Raises:
        KeyError: If required post-sizing columns are absent.
    """
    ticker_values = sized_positions["Ticker"] if "Ticker" in sized_positions else ticker
    return pd.DataFrame(
        {
            "Universe": universe,
            "Ticker": ticker_values,
            "Rank": sized_positions["Rank"],
            "RankScore": sized_positions["RankScore"],
            "EntryDate": sized_positions["EntryDate"],
            "EntryPrice": sized_positions["EntryFill"],
            "StopLoss": sized_positions["StopPrice"],
            "TargetPrice": sized_positions["TargetPrice"],
            "RiskPercent": sized_positions["RiskPercent"],
            "Shares": sized_positions["Quantity"],
            "CapitalRequired": sized_positions["CapitalRequired"],
            "Confirmation": sized_positions["ConfirmationPassed"],
            "Downtrend": sized_positions["DowntrendPassed"],
            "NewsSentiment": sized_positions["NewsSentiment"],
            "NewsHeadline": sized_positions["NewsHeadline"],
        },
        index=sized_positions.index,
    )


def _consolidate_daily_signals(signal_frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Combine already-sized signals while preserving configured universe order.

    Args:
        signal_frames: Per-ticker daily-signal projections.

    Returns:
        A new consolidated DataFrame in input order, including a header-only
        schema when no current signals exist.

    Raises:
        None.
    """
    if not signal_frames:
        return pd.DataFrame(columns=_DAILY_SIGNAL_COLUMNS)

    return pd.concat(signal_frames, ignore_index=True)


def _export_daily_signals(daily_signals: pd.DataFrame, output_path: Path) -> None:
    """Write the consolidated daily signal CSV, including empty headers.

    Args:
        daily_signals: Consolidated current-day signal DataFrame.
        output_path: Exact CSV destination path.

    Returns:
        None.

    Raises:
        OSError: If the destination directory or CSV cannot be written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    daily_signals.to_csv(output_path, index=False)


def _consolidate_daily_candidates(candidate_frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Combine diagnostic candidate frames in configured universe and file order.

    Args:
        candidate_frames: Per-ticker candidate DataFrames appended while the
            configured universe files are processed in their stable order.

    Returns:
        A new diagnostic DataFrame, or the required header-only schema when no
        latest-day patterns were detected.

    Raises:
        None.
    """
    populated_frames = [frame for frame in candidate_frames if not frame.empty]
    if not populated_frames:
        return pd.DataFrame(columns=DAILY_CANDIDATE_COLUMNS)
    candidates = pd.concat(populated_frames, ignore_index=True)
    candidates["Universe"] = pd.Categorical(
        candidates["Universe"], categories=_UNIVERSE_ORDER, ordered=True
    )
    candidates = candidates.sort_values(
        ["Universe", "DowntrendScore"],
        ascending=[True, False],
        kind="stable",
        na_position="last",
    ).reset_index(drop=True)
    candidates["Universe"] = candidates["Universe"].astype("object")
    return candidates.loc[:, DAILY_CANDIDATE_COLUMNS]


def _export_daily_candidates(daily_candidates: pd.DataFrame, output_path: Path) -> None:
    """Write human-readable diagnostic candidates without mutating their values.

    Args:
        daily_candidates: Numeric diagnostic candidate DataFrame.
        output_path: Exact daily-candidates CSV destination path.

    Returns:
        None.

    Raises:
        OSError: If the destination directory or CSV cannot be written.
    """
    formatted_candidates = daily_candidates.copy()
    for column in DAILY_CANDIDATE_PRICE_COLUMNS:
        if column in formatted_candidates.columns:
            formatted_candidates[column] = formatted_candidates[column].map(
                lambda value: value if pd.isna(value) else f"{float(value):.2f}"
            )
    _export_daily_signals(formatted_candidates, output_path)


def _log_daily_candidates_summary(
    daily_candidates: pd.DataFrame,
    stocks_scanned: int,
    latest_trading_date: pd.Timestamp | None,
) -> None:
    """Log the diagnostic latest-pattern funnel without changing trade results.

    Args:
        daily_candidates: Consolidated latest-day pattern candidates.
        stocks_scanned: Number of datasets that completed the research pipeline.
        latest_trading_date: Latest available completed date among those datasets.

    Returns:
        None.

    Raises:
        None.
    """
    downtrend_passed = int(daily_candidates["DowntrendPassed"].sum()) if not daily_candidates.empty else 0
    confirmation_passed = int(daily_candidates["ConfirmationPassed"].sum()) if not daily_candidates.empty else 0
    trade_eligible = int(daily_candidates["TradeEligible"].sum()) if not daily_candidates.empty else 0
    LOGGER.info("----------------------------------------")
    LOGGER.info("Daily Candidates Summary")
    LOGGER.info("----------------------------------------")
    LOGGER.info("Latest trading date: %s", latest_trading_date.date() if latest_trading_date is not None else None)
    LOGGER.info("Stocks scanned: %s", stocks_scanned)
    LOGGER.info("Bullish Engulfing candidates: %s", len(daily_candidates))
    LOGGER.info("Downtrend passed: %s", downtrend_passed)
    LOGGER.info("Downtrend rejected: %s", len(daily_candidates) - downtrend_passed)
    LOGGER.info("Confirmation passed: %s", confirmation_passed)
    LOGGER.info("Trade eligible: %s", trade_eligible)
    for universe in _UNIVERSE_ORDER:
        candidate_count = int((daily_candidates["Universe"] == universe).sum()) if not daily_candidates.empty else 0
        LOGGER.info("%s candidates: %s", universe, candidate_count)


def _log_run_start() -> None:
    """Write an identifiable separator at the beginning of an application run.

    Returns:
        None.

    Raises:
        None.
    """
    LOGGER.info("=" * 60)
    LOGGER.info("TradingResearch run started.")
    LOGGER.info("=" * 60)


def _log_run_completion(exit_code: int) -> None:
    """Write an identifiable completion entry for an application run.

    Args:
        exit_code: Application exit status being returned to the shell.

    Returns:
        None.

    Raises:
        None.
    """
    LOGGER.info("TradingResearch run completed with exit code %s.", exit_code)
    LOGGER.info("=" * 60)


def _run_bullish_engulfing(strategy: StrategyDefinition) -> int:
    """Run the existing Bullish Engulfing workflow and its strategy-specific exports.

    Returns:
        Zero when every ticker downloads successfully; otherwise one.

    Raises:
        ValueError: If configuration identifies an invalid provider class.
        ImportError: If the configured provider module is unavailable.
        AttributeError: If the configured provider class is unavailable.
    """
    try:
        ticker_universes = _load_ticker_universes(TICKER_UNIVERSE_FILES)
    except Exception as error:
        LOGGER.error("Could not load configured ticker universes: %s", error)
        return 1

    if ticker_universes.empty:
        LOGGER.error("Configured ticker universe files contain no ticker symbols.")
        return 1

    provider = _load_provider(PROVIDER_SETTINGS.class_path)
    pipeline = ResearchPipeline(
        account_size=ACCOUNT_SIZE,
        risk_per_trade_percent=RISK_PER_TRADE_PERCENT,
    )
    exporter = CSVExporter()
    scanner = DailySignalScanner()
    candidates_generator = DailyCandidatesReportGenerator()
    DOWNLOAD_SETTINGS.output_directory.mkdir(parents=True, exist_ok=True)

    failures = 0
    daily_signal_frames: list[pd.DataFrame] = []
    daily_candidate_frames: list[pd.DataFrame] = []
    latest_trading_dates: list[pd.Timestamp] = []
    stocks_scanned = 0
    for ticker_record in ticker_universes.itertuples(index=False):
        ticker = ticker_record.Ticker
        universe = ticker_record.Universe
        try:
            dataset = _RUN_DATASET_CACHE.get(ticker)
            if dataset is None:
                dataset = provider.fetch_ohlcv(
                    ticker=ticker,
                    start_date=DOWNLOAD_SETTINGS.start_date,
                    end_date=DOWNLOAD_SETTINGS.end_date,
                    interval=DOWNLOAD_SETTINGS.interval,
                )
                _RUN_DATASET_CACHE[ticker] = dataset.copy(deep=True)
            output_path = _dataset_path(
                DOWNLOAD_SETTINGS.output_directory,
                ticker,
                DOWNLOAD_SETTINGS.interval,
            )
            dataset.to_csv(output_path, index=False)
            LOGGER.info("Saved %s rows for %s to %s", len(dataset), ticker, output_path)

            latest_trading_date = pd.Timestamp(dataset["Date"].max()).normalize()
            try:
                candidate_stages = pipeline.run_candidate_stages(dataset)
                daily_candidate_frames.append(
                    candidates_generator.generate(
                        dataset,
                        candidate_stages["trade_setup"],
                        latest_trading_date,
                        universe,
                    )
                )
            except (PipelineError, Exception) as error:
                LOGGER.error("Daily candidate stages failed for %s: %s", ticker, error)

            try:
                LOGGER.info("Running research pipeline for %s...", ticker)
                pipeline_results = pipeline.run(dataset)
                statistics = pipeline_results["statistics"]
                LOGGER.info("Bullish Engulfing patterns: %s", len(pipeline_results["patterns"]))
                LOGGER.info("Downtrend qualified: %s", statistics["ValidPatterns"])
                LOGGER.info("Confirmed: %s", statistics["ConfirmedPatterns"])
                LOGGER.info("Eligible trades: %s", statistics["TradeEligible"])
                LOGGER.info("Statistics successfully calculated.")
                LOGGER.info("Research pipeline complete for %s.", ticker)
            except PipelineError as error:
                LOGGER.error("Research pipeline failed for %s: %s", ticker, error)
                continue

            latest_trading_dates.append(latest_trading_date)
            stocks_scanned += 1

            if not pipeline_results["sized_positions"].empty:
                daily_signal_frames.append(
                    _daily_signal_rows(pipeline_results["sized_positions"], ticker, universe)
                )

            try:
                export_path = exporter.export(
                    pipeline_results["performance"],
                    ticker,
                    _HISTORICAL_RESULTS_DIRECTORY,
                )
                LOGGER.info("Research results exported to %s", export_path)
            except CSVExportError as error:
                LOGGER.error("Research results export failed for %s: %s", ticker, error)

            try:
                current_signals = scanner.scan(
                    pipeline_results["performance"],
                    dataset["Date"].max(),
                )
            except Exception as error:
                LOGGER.error("Daily signal scanner failed for %s: %s", ticker, error)
                continue

            LOGGER.info("Current eligible signals for %s: %s", ticker, len(current_signals))
            if current_signals.empty:
                LOGGER.info("No current eligible signals for %s.", ticker)
                continue

            try:
                signal_export_path = exporter.export(
                    current_signals,
                    ticker,
                    _SIGNALS_RESULTS_DIRECTORY,
                )
                LOGGER.info("Current signals exported to %s", signal_export_path)
            except CSVExportError as error:
                LOGGER.error("Current signals export failed for %s: %s", ticker, error)
        except ProviderError as error:
            failures += 1
            LOGGER.error("Could not download %s: %s", ticker, error)

    daily_signals = _consolidate_daily_signals(daily_signal_frames)
    daily_signal_path = _DAILY_SIGNALS_PATH
    try:
        _export_daily_signals(daily_signals, daily_signal_path)
        LOGGER.info("%s daily signals exported to %s", strategy.display_name, daily_signal_path)
    except OSError as error:
        LOGGER.error("Could not export consolidated daily signals: %s", error)

    daily_candidates = _consolidate_daily_candidates(daily_candidate_frames)
    daily_candidates_path = _DAILY_CANDIDATES_PATH
    try:
        _export_daily_candidates(daily_candidates, daily_candidates_path)
        LOGGER.info("%s daily candidates exported to %s", strategy.display_name, daily_candidates_path)
    except OSError as error:
        LOGGER.error("Could not export consolidated daily candidates: %s", error)

    _log_daily_candidates_summary(
        daily_candidates,
        stocks_scanned,
        max(latest_trading_dates) if latest_trading_dates else None,
    )

    LOGGER.info("----------------------------------------")
    LOGGER.info("Daily Signals Summary")
    LOGGER.info("----------------------------------------")
    LOGGER.info("Total signals: %s", len(daily_signals))
    if daily_signals.empty:
        LOGGER.info("No eligible trades for today.")
    else:
        LOGGER.info("Rank  Ticker  Entry  Stop  Target")
        for _, signal in daily_signals.iterrows():
            LOGGER.info(
                "%s  %s  %s  %s  %s",
                signal["Rank"],
                signal["Ticker"],
                signal["EntryPrice"],
                signal["StopLoss"],
                signal["TargetPrice"],
            )

    exit_code = 1 if failures else 0
    return exit_code


def _run_bearish_engulfing(strategy: StrategyDefinition) -> int:
    """Run the isolated frozen Bearish Engulfing workflow.

    Returns:
        Zero when all ticker downloads or shared-cache reads succeed.
    """
    universes = _load_ticker_universes(TICKER_UNIVERSE_FILES)
    if universes.empty:
        LOGGER.error("Configured ticker universe files contain no ticker symbols.")
        return 1
    provider = _load_provider(PROVIDER_SETTINGS.class_path)
    pipeline = BearishResearchPipeline(ACCOUNT_SIZE, RISK_PER_TRADE_PERCENT)
    exporter, scanner, candidates = CSVExporter(), DailySignalScanner(), BearishDailyCandidatesReportGenerator()
    signal_frames: list[pd.DataFrame] = []; candidate_frames: list[pd.DataFrame] = []; dates: list[pd.Timestamp] = []; failures = 0
    DOWNLOAD_SETTINGS.output_directory.mkdir(parents=True, exist_ok=True)
    for record in universes.itertuples(index=False):
        ticker, universe = record.Ticker, record.Universe
        try:
            dataset = _RUN_DATASET_CACHE.get(ticker)
            if dataset is None:
                dataset = provider.fetch_ohlcv(ticker, DOWNLOAD_SETTINGS.start_date, DOWNLOAD_SETTINGS.end_date, DOWNLOAD_SETTINGS.interval)
                _RUN_DATASET_CACHE[ticker] = dataset.copy(deep=True)
                dataset.to_csv(_dataset_path(DOWNLOAD_SETTINGS.output_directory, ticker, DOWNLOAD_SETTINGS.interval), index=False)
            dataset = dataset.copy(deep=True)
            latest_date = pd.Timestamp(dataset["Date"].max()).normalize()
            try:
                candidate_stages = pipeline.run_candidate_stages(dataset)
                candidate_frames.append(candidates.generate(dataset, candidate_stages["trade_setup"], latest_date, universe))
            except (PipelineError, Exception) as error:
                LOGGER.error("Bearish daily candidate stages failed for %s: %s", ticker, error)
            results = pipeline.run(dataset); dates.append(latest_date)
            LOGGER.info("Bearish Engulfing patterns: %s", len(results["patterns"])); LOGGER.info("Uptrend qualified: %s", results["statistics"]["ValidPatterns"]); LOGGER.info("Confirmed: %s", results["statistics"]["ConfirmedPatterns"]); LOGGER.info("Eligible short trades: %s", results["statistics"]["TradeEligible"])
            if not results["sized_positions"].empty:
                sized = results["sized_positions"]
                signal_frames.append(pd.DataFrame({"Universe":universe,"Ticker":sized["Ticker"],"Rank":sized["Rank"],"RankScore":sized["RankScore"],"EntryDate":sized["EntryDate"],"EntryPrice":sized["EntryFill"],"StopLoss":sized["StopPrice"],"TargetPrice":sized["TargetPrice"],"RiskPercent":sized["RiskPercent"],"Shares":sized["Quantity"],"CapitalRequired":sized["CapitalRequired"],"Confirmation":sized["ConfirmationPassed"],"Uptrend":sized["UptrendPassed"],"NewsSentiment":sized["NewsSentiment"],"NewsHeadline":sized["NewsHeadline"]}))
            exporter.export(results["performance"], ticker, _BEARISH_HISTORICAL_RESULTS_DIRECTORY)
            current = scanner.scan(results["performance"], dataset["Date"].max())
            if not current.empty: exporter.export(current, ticker, _BEARISH_SIGNALS_RESULTS_DIRECTORY)
        except (ProviderError, PipelineError, CSVExportError, Exception) as error:
            failures += 1; LOGGER.error("Bearish workflow failed for %s: %s", ticker, error)
    daily_signals = pd.concat(signal_frames, ignore_index=True) if signal_frames else pd.DataFrame(columns=_DAILY_SIGNAL_COLUMNS)
    _export_daily_signals(daily_signals, _BEARISH_DAILY_SIGNALS_PATH)
    daily_candidates = pd.concat([f for f in candidate_frames if not f.empty], ignore_index=True) if any(not f.empty for f in candidate_frames) else pd.DataFrame(columns=BEARISH_DAILY_CANDIDATE_COLUMNS)
    if not daily_candidates.empty:
        daily_candidates["Universe"] = pd.Categorical(daily_candidates["Universe"], categories=_UNIVERSE_ORDER, ordered=True)
        daily_candidates = daily_candidates.sort_values(["Universe", "UptrendScore"], ascending=[True, False], kind="stable").reset_index(drop=True)
    formatted = daily_candidates.copy()
    for column in BEARISH_DAILY_CANDIDATE_PRICE_COLUMNS:
        if column in formatted: formatted[column] = formatted[column].map(lambda value: value if pd.isna(value) else f"{float(value):.2f}")
    _export_daily_signals(formatted, _BEARISH_DAILY_CANDIDATES_PATH)
    LOGGER.info("%s daily signals exported to %s", strategy.display_name, _BEARISH_DAILY_SIGNALS_PATH)
    LOGGER.info("%s daily candidates exported to %s", strategy.display_name, _BEARISH_DAILY_CANDIDATES_PATH)
    return 1 if failures else 0


STRATEGY_REGISTRY = StrategyRegistry(
    (
        StrategyDefinition(
            name="bullish-engulfing",
            output_slug="bullish_engulfing",
            display_name="Bullish Engulfing",
            runner=_run_bullish_engulfing,
        ),
        StrategyDefinition(
            name="bearish-engulfing",
            output_slug="bearish_engulfing",
            display_name="Bearish Engulfing",
            runner=_run_bearish_engulfing,
        ),
    )
)
"""All strategies explicitly available to the command-line application."""


def _parse_arguments(arguments: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line strategy selection without any implicit fallback.

    Args:
        arguments: Optional argument sequence; uses process arguments when None.

    Returns:
        Parsed namespace containing the selected strategy.

    Raises:
        SystemExit: If argparse receives an unsupported command-line value.
    """
    parser = argparse.ArgumentParser(description="Run selected TradingResearch strategies.")
    parser.add_argument(
        "--strategy",
        choices=(*STRATEGY_REGISTRY.names, "all"),
        default="bullish-engulfing",
        help="Strategy to run; defaults to bullish-engulfing.",
    )
    return parser.parse_args(arguments)


def run(
    strategy_name: str = "bullish-engulfing",
    registry: StrategyRegistry | None = None,
) -> int:
    """Run only the strategy or strategies explicitly selected by the caller.

    Args:
        strategy_name: Registered strategy name or ``"all"``.
        registry: Optional registry injection used for orchestration tests.

    Returns:
        Zero only when every selected strategy succeeds.

    Raises:
        ValueError: If ``strategy_name`` is unsupported by the active registry.
    """
    active_registry = registry or STRATEGY_REGISTRY
    selected_strategies = active_registry.select(strategy_name)
    configure_logging(LOGGING_SETTINGS)
    _log_run_start()
    if strategy_name == "all":
        LOGGER.info("Selected strategy mode: all")
    else:
        LOGGER.info("Selected strategy: %s", strategy_name)

    _RUN_DATASET_CACHE.clear()
    exit_codes: list[int] = []
    for strategy in selected_strategies:
        LOGGER.info("Running strategy: %s", strategy.name)
        exit_codes.append(strategy.runner(strategy))

    exit_code = 1 if any(exit_codes) else 0
    _log_run_completion(exit_code)
    return exit_code


def main(arguments: list[str] | None = None) -> None:
    """Execute the application and expose its exit status to the shell.

    Returns:
        None.

    Raises:
        SystemExit: Always, with the status returned by ``run``.
    """
    parsed_arguments = _parse_arguments(arguments)
    raise SystemExit(run(parsed_arguments.strategy))


if __name__ == "__main__":
    main()
