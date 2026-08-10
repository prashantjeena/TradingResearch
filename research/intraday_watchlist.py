"""Daily-data-only prototype intraday watchlist command."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from analysis.bearish_uptrend import UptrendEvaluator
from analysis.trend import DowntrendEvaluator
from config import DOWNLOAD_SETTINGS, TICKER_UNIVERSE_FILES
from data.ticker_universe import load_ticker_universes
from intraday.watchlist import IntradayWatchlistGenerator, WATCHLIST_COLUMNS
from patterns.bearish_engulfing import BearishEngulfingDetector
from patterns.bullish_engulfing import BullishEngulfingDetector


WATCHLIST_DIRECTORY = Path("results") / "intraday_research" / "prototype" / "watchlists"
"""Isolated destination for prototype candidate watchlists."""

_PRICE_COLUMNS = ("PatternOpen", "PatternHigh", "PatternLow", "PatternClose")
_SIDES = ("LONG", "SHORT")


@dataclass(frozen=True, slots=True)
class WatchlistRunResult:
    """Outcome and freshness diagnostics from one watchlist generation run."""

    trading_date: pd.Timestamp
    setup_date: pd.Timestamp | None
    configured_tickers: int
    setup_date_tickers: int
    stale_tickers: tuple[str, ...]
    evaluated_tickers: int
    failed_tickers: tuple[str, ...]
    watchlist: pd.DataFrame


def resolve_trading_date(value: str | None) -> pd.Timestamp:
    """Resolve an optional ISO date or the current Asia/Kolkata calendar date.

    Args:
        value: Optional ``YYYY-MM-DD`` date text.

    Returns:
        A timezone-naive normalized calendar date used for daily comparisons.

    Raises:
        ValueError: If supplied date text is invalid.
    """
    if value is None:
        return pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None).normalize()
    try:
        return pd.Timestamp(date.fromisoformat(value)).normalize()
    except ValueError as error:
        raise ValueError("Trading date must use YYYY-MM-DD.") from error


def build_watchlist(
    trading_date: pd.Timestamp,
    ticker_universes: pd.DataFrame,
    daily_data_directory: Path,
) -> WatchlistRunResult:
    """Build one global-date LONG/SHORT watchlist from completed daily data.

    Every dataset is truncated to observations strictly earlier than
    ``trading_date`` before any detector is called. The single global setup
    date is the latest completed date observed across the configured datasets;
    tickers lacking that date are reported stale rather than backfilled.

    Args:
        trading_date: Requested intraday evaluation date.
        ticker_universes: Ordered DataFrame containing ``Ticker`` and
            ``Universe`` columns.
        daily_data_directory: Directory holding canonical daily CSV files.

    Returns:
        Watchlist rows and per-run freshness diagnostics.

    Raises:
        ValueError: If the universe table lacks its required columns.
    """
    _require_universe_columns(ticker_universes)
    target_date = pd.Timestamp(trading_date).normalize()
    completed: dict[int, pd.DataFrame] = {}
    latest_dates: list[pd.Timestamp] = []
    failed: list[str] = []

    for order, record in enumerate(ticker_universes.itertuples(index=False)):
        try:
            data = _read_completed_daily_data(daily_data_directory, record.Ticker, target_date)
        except (OSError, UnicodeError, ValueError, KeyError) as error:
            failed.append(f"{record.Ticker} ({record.Universe}): {error}")
            continue
        completed[order] = data
        if not data.empty:
            latest_dates.append(pd.Timestamp(data["Date"].max()).normalize())

    if not latest_dates:
        return WatchlistRunResult(target_date, None, len(ticker_universes), 0, tuple(), 0, tuple(failed), _empty_watchlist())

    setup_date = max(latest_dates)
    stale: list[str] = []
    frames: list[pd.DataFrame] = []
    evaluated = 0
    setup_date_tickers = 0
    universe_order = tuple(dict.fromkeys(ticker_universes["Universe"].tolist()))

    for order, record in enumerate(ticker_universes.itertuples(index=False)):
        data = completed.get(order)
        if data is None:
            continue
        if not (pd.to_datetime(data["Date"]).dt.normalize() == setup_date).any():
            stale.append(f"{record.Ticker} ({record.Universe})")
            continue
        setup_date_tickers += 1
        try:
            frames.extend(_evaluate_ticker(data, record.Ticker, record.Universe, target_date, setup_date))
            evaluated += 1
        except Exception as error:
            failed.append(f"{record.Ticker} ({record.Universe}): {error}")

    watchlist = _sort_watchlist(frames, ticker_universes, universe_order)
    return WatchlistRunResult(target_date, setup_date, len(ticker_universes), setup_date_tickers, tuple(stale), evaluated, tuple(failed), watchlist)


def export_watchlist(watchlist: pd.DataFrame, trading_date: pd.Timestamp, output_directory: Path = WATCHLIST_DIRECTORY) -> Path:
    """Export a display-formatted copy of a prototype watchlist.

    Args:
        watchlist: Watchlist rows in the canonical watchlist column order.
        trading_date: Date used in the deterministic file name.
        output_directory: Isolated prototype-watchlist destination.

    Returns:
        The written CSV path.

    Raises:
        ValueError: If the watchlist schema is invalid.
        OSError: If the destination cannot be created or written.
    """
    if tuple(watchlist.columns) != WATCHLIST_COLUMNS:
        raise ValueError("Watchlist schema is invalid.")
    formatted = watchlist.copy()
    for column in _PRICE_COLUMNS:
        formatted[column] = formatted[column].map(lambda value: value if pd.isna(value) else f"{float(value):.2f}")
    output_directory.mkdir(parents=True, exist_ok=True)
    path = output_directory / f"{pd.Timestamp(trading_date).date()}_watchlist.csv"
    formatted.to_csv(path, index=False)
    return path


def run(trading_date_text: str | None = None) -> WatchlistRunResult:
    """Load the configured universe, generate, export, and display a watchlist.

    Args:
        trading_date_text: Optional ISO trading date supplied by the CLI.

    Returns:
        The watchlist result and freshness diagnostics.

    Raises:
        ValueError: If the supplied trading date is invalid.
    """
    result = build_watchlist(
        resolve_trading_date(trading_date_text),
        load_ticker_universes(TICKER_UNIVERSE_FILES),
        DOWNLOAD_SETTINGS.output_directory,
    )
    path = export_watchlist(result.watchlist, result.trading_date)
    _print_summary(result, path)
    return result


def main(arguments: list[str] | None = None) -> None:
    """Parse CLI arguments and execute the research-only watchlist command.

    Args:
        arguments: Optional testable argument sequence.

    Returns:
        None.

    Raises:
        SystemExit: If date arguments are invalid.
    """
    parser = argparse.ArgumentParser(description="Generate an intraday research candidate watchlist.")
    parser.add_argument("--trading-date", help="Trading date in YYYY-MM-DD format.")
    parsed = parser.parse_args(arguments)
    try:
        run(parsed.trading_date)
    except ValueError as error:
        parser.error(str(error))


def _read_completed_daily_data(directory: Path, ticker: str, trading_date: pd.Timestamp) -> pd.DataFrame:
    """Read one daily CSV and remove target-date and future candles.

    Args:
        directory: Daily CSV directory.
        ticker: Configured ticker symbol.
        trading_date: Exclusive upper date bound.

    Returns:
        A new chronological completed-only daily DataFrame.

    Raises:
        OSError: If the source CSV cannot be read.
        ValueError: If dates cannot be parsed.
    """
    path = directory / f"{ticker.replace('.', '_').replace('/', '_').replace('\\', '_')}_1d.csv"
    data = pd.read_csv(path)
    data = data.copy()
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    if data["Date"].isna().any():
        raise ValueError("Daily dataset contains invalid dates.")
    return data.loc[data["Date"].dt.normalize() < trading_date].sort_values("Date", kind="stable").reset_index(drop=True)


def _evaluate_ticker(data: pd.DataFrame, ticker: str, universe: str, trading_date: pd.Timestamp, setup_date: pd.Timestamp) -> list[pd.DataFrame]:
    """Evaluate both directional pattern-plus-trend watchlist paths.

    Args:
        data: Completed-only daily source data for one ticker.
        ticker: Configured ticker symbol.
        universe: Configured universe label.
        trading_date: Requested next-session watchlist date.
        setup_date: Shared latest completed setup date.

    Returns:
        Zero, one, or two direction-specific watchlist frames.
    """
    generator = IntradayWatchlistGenerator()
    bullish_patterns = BullishEngulfingDetector().detect(data)
    bearish_patterns = BearishEngulfingDetector().detect(data)
    directions: list[tuple[pd.DataFrame, str, str]] = []
    if not bullish_patterns.empty:
        bullish = DowntrendEvaluator().evaluate(data, bullish_patterns)
        bullish["DowntrendScore"] = bullish["PatternIndex"].map(lambda index: _downtrend_score(data, index))
        directions.append((bullish, "LONG", "BULLISH_ENGULFING"))
    if not bearish_patterns.empty:
        bearish = UptrendEvaluator().evaluate(data, bearish_patterns)
        directions.append((bearish, "SHORT", "BEARISH_ENGULFING"))
    outputs: list[pd.DataFrame] = []
    for evaluated, side, label in directions:
        patterns = evaluated.loc[pd.to_datetime(evaluated["Date"]).dt.normalize() == setup_date].copy()
        generated = generator.generate(patterns, pd.Series([trading_date]), universe, side)
        if not generated.empty:
            generated["PatternName"] = label
            outputs.append(generated)
    return outputs


def _downtrend_score(data: pd.DataFrame, pattern_index: object) -> int | None:
    """Calculate display-only Bullish trend score without changing qualification.

    Args:
        data: One ticker's completed daily source data.
        pattern_index: Pattern row's source index.

    Returns:
        The frozen zero-through-four comparison count, or ``None`` when the
        prerequisite five prior candles are unavailable.
    """
    position = data.index.get_loc(pattern_index)
    prior = data.iloc[position - 5:position]
    if len(prior) < 5:
        return None
    return int(((prior["High"].iloc[1:].to_numpy() < prior["High"].iloc[:-1].to_numpy()) & (prior["Low"].iloc[1:].to_numpy() < prior["Low"].iloc[:-1].to_numpy())).sum())


def _sort_watchlist(frames: list[pd.DataFrame], universes: pd.DataFrame, universe_order: tuple[str, ...]) -> pd.DataFrame:
    """Sort candidate rows by side, configured universe, then file order.

    Args:
        frames: Per-ticker generated watchlist frames.
        universes: Ordered configured ticker universe table.
        universe_order: Ordered configured universe labels.

    Returns:
        A new watchlist in the required schema order.
    """
    if not frames:
        return _empty_watchlist()
    order = {ticker: position for position, ticker in enumerate(universes["Ticker"])}
    result = pd.concat(frames, ignore_index=True)
    result["_side"] = pd.Categorical(result["Side"], categories=_SIDES, ordered=True)
    result["_universe"] = pd.Categorical(result["Universe"], categories=universe_order, ordered=True)
    result["_ticker"] = result["Ticker"].map(order)
    result = result.sort_values(["_side", "_universe", "_ticker"], kind="stable").drop(columns=["_side", "_universe", "_ticker"])
    return result.loc[:, WATCHLIST_COLUMNS].reset_index(drop=True)


def _empty_watchlist() -> pd.DataFrame:
    """Return a header-only watchlist frame.

    Returns:
        Empty DataFrame in the exact watchlist schema.
    """
    return pd.DataFrame(columns=WATCHLIST_COLUMNS)


def _require_universe_columns(ticker_universes: pd.DataFrame) -> None:
    """Validate the configured ticker universe table.

    Args:
        ticker_universes: Candidate ordered universe table.

    Returns:
        None.

    Raises:
        ValueError: If the required columns are unavailable.
    """
    if tuple(ticker_universes.columns) != ("Ticker", "Universe"):
        raise ValueError("Ticker universes must contain exactly Ticker and Universe columns.")


def _print_summary(result: WatchlistRunResult, output_path: Path) -> None:
    """Print the explicit user-facing research-only watchlist summary.

    Args:
        result: Completed watchlist result.
        output_path: Written CSV path.

    Returns:
        None.
    """
    long_count = int((result.watchlist["Side"] == "LONG").sum())
    short_count = int((result.watchlist["Side"] == "SHORT").sum())
    print("Intraday Watchlist")
    print(f"Trading Date: {result.trading_date.date()}")
    print(f"Setup Date: {result.setup_date.date() if result.setup_date is not None else None}")
    print(f"Configured Universe: {result.configured_tickers}")
    print(f"Current SetupDate Data: {result.setup_date_tickers}")
    print(f"Stale/Missing: {len(result.stale_tickers)}")
    print(f"Successfully Evaluated: {result.evaluated_tickers}")
    print(f"Failed: {len(result.failed_tickers)}")
    print(f"LONG candidates: {long_count}")
    print(f"SHORT candidates: {short_count}")
    print(f"Total watchlist: {len(result.watchlist)}")
    if result.watchlist.empty:
        print("No qualifying intraday watchlist setups for this trading date.")
    else:
        print(result.watchlist[["Ticker", "Universe", "Side", "PatternName", "TrendScore"]].to_string(index=False))
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
