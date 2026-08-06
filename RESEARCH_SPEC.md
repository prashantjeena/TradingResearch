# Trading Research Toolkit
# RESEARCH_SPEC.md
Version: 1.0 FINAL
Status: Frozen for Implementation

---

# 1. Objective

## Primary Research Question

Does a Bullish Engulfing candlestick pattern provide evidence of a trading edge in the Indian stock market under a fixed, realistic daily-data trading model?

This project uses historical data rather than opinions or anecdotal charts.

Version 1 is an exploratory research experiment. It reports descriptive outcomes under fixed rules. It does not, by itself, establish a statistically significant or tradeable edge.

---

# 2. Guiding Principles

- Every experiment must use pre-defined rules.
- No future candle may be used to identify the pattern or trend.
- The entry must be executable after the signal is known.
- Dataset validation errors exclude affected datasets from the experiment.
- Rules must not change during an experiment.
- A rule change creates a new experiment version.
- Results must record the data source, date range, configuration, and dataset version used.
- Version 1 results must be described as exploratory.

---

# 3. Version 1 Requirements

## 3.1 Market and Dataset

Market:

- NSE equities.

Universe:

- NIFTY 50 constituents selected at the start of the experiment.

Timeframe:

- Daily OHLCV candles.

Data source:

- Yahoo Finance, prototype only.

Research period:

- 2020-01-01 through 2025-12-31.

Dataset admission:

- A dataset must pass all Data Quality Engine error-level rules.
- Warning-level results are retained and reported.
- Any excluded ticker must be recorded with its exclusion reason.

Important limitation:

- Version 1 uses a static NIFTY 50 universe. This may contain survivorship bias and must be disclosed in every report.

## 3.2 Canonical Dataset Schema

Every dataset must use this column order:

1. `Date`
2. `Open`
3. `High`
4. `Low`
5. `Close`
6. `Adj Close`
7. `Volume`
8. `Ticker`

The Version 1 pattern and trade simulation use raw `Open`, `High`, `Low`, and `Close`.

`Adj Close` is retained for inspection only. It is not used to alter OHLC values in Version 1.

## 3.3 Pattern Under Study

Bullish Engulfing is the only pattern included in Version 1.

Previous candle, Day `T-1`:

```text
Close[T-1] < Open[T-1]
```

Current candle, Day `T`:

```text
Close[T] > Open[T]
Open[T] < Close[T-1]
Close[T] > Open[T-1]
```

Only the candle body is considered. Upper and lower shadows are ignored. All comparisons are strict; equality does not qualify.

## 3.4 Downtrend Definition

A Bullish Engulfing pattern at Day `T` is valid only if the five immediately preceding available trading candles, `T-5` through `T-1`, indicate a downtrend.

For each of the four consecutive comparisons in that sequence, evaluate:

```text
High[i] < High[i-1]
AND
Low[i] < Low[i-1]
```

for:

```text
i = T-4, T-3, T-2, T-1
```

A downtrend exists when at least three of the four comparisons satisfy both conditions.

The pattern candle at `T` is not used to determine the trend. If fewer than five preceding candles are available, the pattern is excluded.

## 3.5 Event Timeline

```text
Day T
Bullish Engulfing pattern is detected after Day T closes.

Day T+1
Confirmation candle closes.
Confirmation succeeds only if Close[T+1] > High[T].

Day T+2
Trade entry occurs at the opening price, adjusted for Version 1 entry slippage.

Days T+2 through T+6
Five-trading-day observation window, including the entry day.

Trade outcome
Target, stop loss, or expiry is determined using the fixed rules below.
```

The confirmation candle is not part of the active trade window. No trade is entered unless confirmation succeeds.

## 3.6 Entry, Stop Loss, Risk, and Target

Raw entry reference:

```text
Open[T+2]
```

Simulated long entry fill:

```text
Entry Fill = Open[T+2] x 1.001
```

Stop price:

```text
Stop Price = Low[T]
```

Risk:

```text
Risk (R) = Entry Fill - Stop Price
```

A candidate is excluded when `Risk <= 0`.

Target:

```text
Target Price = Entry Fill + (2 x Risk)
```

## 3.7 Default Version 1 Cost Model

Version 1 uses a simple all-in execution haircut:

- Entry slippage and costs: 0.10% adverse.
- Exit slippage and costs: 0.10% adverse.

For a long trade:

```text
Entry Fill = Raw Entry x 1.001
Exit Fill = Raw Exit x 0.999
```

This represents combined brokerage, fees, spread, and slippage. The same model must be used for every ticker and every trade in Version 1.

## 3.8 Observation Window

The observation window is a configurable experiment parameter.

Version 1 default:

```text
5 trading days
```

For Version 1, the five daily candles are `T+2` through `T+6`, including the entry day. Future experiment versions may use a different observation-window value without changing the implementation.

## 3.9 Trade Simulation and Outcome Rules

For each active trading day in the observation window:

### Gap-at-Open Handling

- If `Open <= Stop Price`, the stop is triggered at that day's open.
- If `Open >= Target Price`, the target is triggered at that day's open.

For either gap-at-open exit:

```text
Exit Fill = Triggered Open x 0.999
```

### Intraday Barrier Handling

If no gap-at-open barrier is triggered:

- If `Low <= Stop Price` and `High < Target Price`, outcome is `LOSS`.
- If `High >= Target Price` and `Low > Stop Price`, outcome is `WIN`.

For an intraday barrier exit:

```text
Exit Fill = Barrier Price x 0.999
```

### Same-Bar Ambiguity

If both conditions occur in the same daily candle:

```text
Low <= Stop Price
AND
High >= Target Price
```

Version 1 records the trade as `LOSS`.

Daily OHLC data cannot establish which price occurred first. Assuming the stop occurred first is the conservative policy and avoids optimistic bias.

### Trade Outcomes

- `WIN`: Target is reached before stop loss.
- `LOSS`: Stop loss is reached before target, or both barriers are touched in the same daily candle.
- `EXPIRED`: Neither barrier is reached during the observation window.

## 3.10 Expired Trade Handling

An expired trade remains classified as `EXPIRED`; it is not reclassified as a win or loss.

For descriptive reporting only:

```text
Expiry Exit Fill = Close[T+6] x 0.999
```

Reports must show wins, losses, expired trades, win rate among resolved trades, marked-to-market return for expired trades, and overall marked-to-market return including expired trades.

Win rate is:

```text
Wins / (Wins + Losses)
```

Expired trades are excluded from the win-rate denominator.

## 3.11 Exclusion Rules

A candidate pattern is excluded, and its exclusion reason is recorded, when any of the following applies:

- Required candles from `T-5` through `T` are unavailable.
- The confirmation candle at `T+1` is unavailable.
- The entry candle at `T+2` is unavailable.
- Fewer than five observation candles from `T+2` through `T+6` are available.
- Any required candle has missing OHLCV values.
- Any required candle has invalid OHLC relationships.
- The dataset fails an error-level Data Quality Engine rule.
- Duplicate rows or duplicate dates occur in the required evaluation range.
- Risk is zero or negative.
- Required candles have `Volume <= 0`.
- A gap of more than seven calendar days occurs between adjacent required candles.

The final rule is a practical Version 1 proxy for suspended or unavailable trading. It is not an official exchange-suspension classification.

## 3.12 Data Integrity and Look-Ahead Rules

- Pattern detection uses data only through the close of Day `T`.
- Trend detection uses data only through Day `T-1`.
- Confirmation uses only the close of Day `T+1`.
- Entry occurs only at the open of Day `T+2`.
- Trade outcomes use only candles from `T+2` through `T+6`.
- No future indicator, sector label, constituent change, adjustment factor, or market information may be used in Version 1 signal generation.

## 3.13 Statistics to Record

For each detected candidate, record:

- Ticker
- Pattern date
- Pattern detected
- Downtrend detected
- Confirmation status
- Entry date
- Raw entry price and entry fill
- Stop price, target price, and risk in price units and percentage
- Outcome and exit date
- Raw exit price and exit fill
- Days until outcome or expiry
- Gross return and net return
- MFE and MAE
- Pattern-day volume
- Exclusion reason, if excluded

MFE and MAE are measured from the Entry Fill price only, during the active observation window and before the trade exits.

For every experiment, record total candidates, exclusions by reason, valid and confirmed patterns, entered trades, wins, losses, expired trades, resolved-trade win/loss rates, marked-to-market returns, average holding period, average MFE/MAE, results by ticker, and dataset-quality warnings.

## 3.14 Experiment Reproducibility

Each experiment must save:

- Experiment version
- Research period
- Universe definition and ticker list
- Data source and download date
- Dataset file names and checksums where practical
- Research configuration values
- Cost model
- Rule names and versions
- Output generation date

A completed experiment must never be overwritten with changed rules.

---

# 4. Experiment Assumptions

Version 1 makes these assumptions:

1. Yahoo Finance daily OHLCV data is sufficient for exploratory research.
2. Current NIFTY 50 membership is used as a static universe and may introduce survivorship bias.
3. Raw OHLC prices are used without full corporate-action adjustment.
4. The next available dataset row is treated as the next trading session.
5. A gap of more than seven calendar days in required candles is treated as unavailable or suspended trading.
6. Entry is possible at the `T+2` open with a fixed 0.10% adverse entry adjustment.
7. Exit is possible at a barrier or gap-open price with a fixed 0.10% adverse exit adjustment.
8. If stop and target are both touched in one daily candle, the stop is assumed to occur first.
9. The observation-window length is configurable; Version 1 uses five trading days including the entry day.
10. Expired trades remain unresolved for win-rate reporting and are separately marked to market.
11. Results are exploratory and do not alone prove statistical significance or a tradeable edge.
12. No portfolio allocation, position sizing, capital limits, or overlapping-trade constraints are modeled in Version 1.

---

# 5. Future Enhancements

## Dataset and Universe

- Point-in-time NIFTY 50 and NIFTY 500 membership.
- Delisted securities and symbol-history support.
- Exchange-calendar validation.
- Official suspension and circuit-limit data.
- Corporate-action-aware adjusted OHLC data.
- Historical sector classifications.
- Institutional or audited market-data providers.

## Research Methodology

- Matched control groups and unconditional-return benchmarks.
- Confidence intervals and bootstrapping.
- Clustered statistical inference.
- Train, validation, and out-of-sample test periods.
- Multiple-testing controls.
- Market-regime analysis.
- Liquidity, turnover, and market-impact models.
- Portfolio-level overlapping-trade and position-sizing rules.

## Trading Rules

- Alternative targets and observation-window values.
- Alternative confirmation methods.
- EMA, ADX, ATR, RSI, MACD, VWAP, volume, support/resistance, sector, and market filters.
- Optimistic/conservative ambiguity bounds.
- Trailing stops.
- Additional candlestick patterns.

## Reporting

- Excel, HTML, and PDF reports.
- Charts for individual patterns.
- Interactive dashboards.

---

# 6. Experiment Versioning

Research rules must never be modified within an experiment.

Any change to pattern definition, downtrend definition, confirmation rule, entry timing, stop or target rule, cost model, observation-window value, universe, dataset period, or data-adjustment policy creates a new experiment version.

Version 1.0:

```text
Three-of-four comparison price-action downtrend
Confirmation required
T+2 open entry
2R target
Five-day default observation window
Conservative same-bar policy
```

---

# 7. Current Status

Completed:

- Phase 1: Project foundation
- Phase 2: Data Quality Engine

Next permitted phase:

- Bullish Engulfing detection based on this Version 1 specification.

---

# 8. Revision Summary

| Change | Why it improves the research |
|---|---|
| Replaced pattern-high entry with `T+2` open entry | Removes an impossible historical fill and prevents look-ahead bias. |
| Added an explicit `T -> T+1 -> T+2 -> T+6` timeline | Makes every signal, entry, and outcome event reproducible. |
| Defined conservative same-bar ambiguity as a loss | Avoids optimistic results that daily OHLC data cannot justify. |
| Defined the downtrend as at least three of four lower-high/lower-low comparisons | Retains an objective, testable definition while avoiding an unnecessarily strict all-four requirement. |
| Made the observation window configurable, with a five-day Version 1 default | Allows later experiments to vary holding duration without changing implementation structure. |
| Renamed the cost section to Default Version 1 Cost Model | Makes the fixed Version 1 model clear while leaving room for future cost models. |
| Added fixed 0.10% entry and exit execution haircuts | Produces more realistic exploratory results than frictionless fills. |
| Explicitly defined MFE and MAE from Entry Fill | Removes ambiguity in adverse and favorable excursion measurement. |
| Defined expired-trade treatment and marked-to-market reporting | Prevents unresolved trades from being hidden or misclassified. |
| Added explicit exclusions | Prevents incomplete, invalid, duplicate, zero-risk, or likely suspended data from silently affecting outcomes. |
| Added Version 1 assumptions | Makes limitations visible rather than implicit. |
| Fixed the historical range and documented static-universe bias | Improves reproducibility while keeping Version 1 practical. |
| Moved advanced methods to Future Enhancements | Keeps Version 1 implementable for a solo developer without losing the long-term roadmap. |
| Added reproducibility artifacts | Allows a completed experiment to be traced to its rules, data, and configuration. |

# 9. Version 1 Overall Score

**7/10**

Version 1 is sufficiently precise for an exploratory implementation: entries are executable, outcomes are deterministic, exclusions are defined, and major assumptions are disclosed.

It is not sufficient to make strong claims of statistical significance or a durable market edge. Those claims require the future enhancements listed above, especially point-in-time universe data, corporate-action handling, benchmarks, and formal statistical inference.
