# Intraday Research Specification

Version: 0.1  
Status: DATA/RESEARCH DESIGN — NOT YET FROZEN FOR TRADING

## Purpose and Isolation

This document defines a future, independent intraday research family. It does
not change the frozen daily swing strategies or authorize executable strategy
registration, order placement, or intraday simulation.

Planned strategy identities are `bullish-engulfing-intraday` and
`bearish-engulfing-intraday`. They are not currently executable.

## Research Timeline

A completed daily setup is a stock-selection event, not an automatic trade.

```text
Day T close
  -> Daily setup qualifies for next-session watchlist
Day T+1 intraday
  -> Evaluate only information available at each completed intraday candle
  -> TRADE, SKIP, TRIGGER_NOT_REACHED, or EXPIRED_INTRADAY
  -> Mandatory same-day exit
```

Bullish and Bearish intraday experiments must remain separate from the
existing daily Bullish and Bearish swing experiments. The current swing
confirmation and T+2 entry rules do not apply to this new family.

## Data and Decision Boundaries

The primary research interval is five minutes. Fifteen-minute analysis may be
downloaded directly or derived from validated five-minute data. Every decision
at time X may use only daily information available by Day T close and
intraday candles completed at or before X. It must never use T+1 daily high,
low, close, future intraday candles, or future VWAP/volume values.

## Execution Models for Fair Comparison

All models should use the same daily setup population, universe, dates, cost
interface, capital assumptions, and risk constraints where applicable.

### Model A — Fixed Percentage Benchmark

Model A is a simple control: an independently defined intraday trigger with
percentage target and stop distances. Candidate target and stop percentages
are research parameters, not chosen values.

### Model B — ATR / Volatility

Model B derives target and stop distances from completed daily ATR, realised
volatility, previous-day range, and/or completed intraday volatility. Any
coefficient remains an experiment parameter.

### Model C — Structure + Volatility + Reward:Risk

Model C is the preferred explainable direction. Its limited feature set may
include daily setup context, support/resistance, completed ATR/volatility,
intraday structure or VWAP, volume confirmation, and a reward:risk gate.
It estimates available room rather than predicting an exact future extreme.

For all dynamic models, potential reward and risk must be known at decision
time. Insufficient room produces `NO TRADE`; the minimum reward:risk value is
not frozen.

## Candidate Entry Concepts

Future experiments may compare, rather than combine blindly:

- Bullish: break of pattern high, first-15-minute high, VWAP reclaim with
  bullish structure, or swing-high break with volume confirmation.
- Bearish: break of pattern low, first-15-minute low, VWAP rejection with
  bearish structure, or swing-low break with volume confirmation.

No trigger, VWAP rule, or volume threshold is selected by this document.

## Exit, Ambiguity, and Costs

Every intraday position must intentionally exit by a configurable end-of-day
cutoff; overnight holding is not planned. If stop and target are both touched
within one five-minute candle and ordering cannot be established, record a
conservative loss. Higher-resolution data may later resolve that ambiguity.

The future simulator must expose configurable adverse entry slippage, adverse
exit slippage, brokerage/fees/taxes, and long/short direction handling. No
current swing cost value is adopted automatically.

## Liquidity and Guardrails

Future research may reject trades using average traded value, average/current
volume, and spread where data permits. Safety guardrails may bound stop
distance, target distance, capital risk, reward:risk, and simultaneous
positions. Thresholds are not frozen.

## Research Design and Metrics

Parameter exploration must use chronological development data, then a
validation period, then an untouched final test period. If the history cannot
support those periods, results must state the limitation. The architecture
must permit future rolling walk-forward evaluation.

Required comparison metrics include trade count, win/loss rate, average
winner/loser, expectancy, gross/net P&L, profit factor, maximum drawdown,
average/median holding time, worst losing streak, and return on capital used.
Sharpe and Sortino are optional when statistically appropriate. Results should
eventually support year, direction, universe, ticker, and market-regime views.
Win rate alone is never a primary success criterion.

## Proposed Outputs

```text
results/intraday_research/
  fixed_percentage/
    trades.csv
    summary.csv
    period_breakdown.csv
  atr_volatility/
    trades.csv
    summary.csv
    period_breakdown.csv
  hybrid_structure/
    trades.csv
    summary.csv
    period_breakdown.csv
  model_comparison.csv
```

A future live/watchlist output should expose:

```text
Ticker, Side, SetupDate, EntryTrigger, Target, StopLoss,
PotentialRewardPercent, RiskPercent, RewardRisk, Decision, DecisionReason
```

## Explicitly Unresolved Parameters

This version does not freeze target/stop percentages, ATR coefficients,
minimum reward:risk, entry trigger, VWAP rule, volume threshold, end-of-day
cutoff, transaction-cost values, or liquidity thresholds.

## Non-Goals

No intraday pattern detector, entry engine, indicators, simulator, provider,
CLI command, strategy registration, or live trading behavior is implemented
by this specification.
