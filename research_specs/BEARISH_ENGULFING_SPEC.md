# Bearish Engulfing Strategy Specification

Version: 1.0  
Status: FROZEN FOR IMPLEMENTATION

## 1. Purpose and Isolation

Bearish Engulfing is an independent daily short-strategy research experiment
for NSE equities. It must not combine candidates, signals, trade histories,
statistics, or result files with Bullish Engulfing.

- CLI name: `bearish-engulfing`
- Filesystem slug: `bearish_engulfing`
- Future daily results: `results/bearish_engulfing/daily/`
- Future historical results: `results/bearish_engulfing/historical/`

No automatic fallback between strategies is permitted. A zero-result Bullish
Engulfing run must not cause Bearish Engulfing to run.

## 2. Dataset and Timeline

The strategy uses the existing validated canonical daily OHLCV dataset and
the same shared `datasets/` directory as Bullish Engulfing.

```text
Day T      Bearish Engulfing is detected after the close.
Day T+1    Confirmation is evaluated after the close.
Day T+2    Short entry occurs at the open with adverse entry adjustment.
T+2–T+6   Five-trading-day observation window, including entry day.
```

Pattern detection uses data through Day `T`; the uptrend uses only `T-5`
through `T-1`; confirmation uses only `T+1`; and simulation uses only `T+2`
through `T+6` after entry. No later candle may affect an earlier decision.

## 3. Strict Bearish Engulfing Pattern

The pattern candle is Day `T`; the prior candle is `T-1`. Only real bodies
are evaluated. Wick engulfing is neither required nor used.

```text
Close[T-1] > Open[T-1]      Previous candle is bullish.
Close[T] < Open[T]          Current candle is bearish.
Open[T] > Close[T-1]        Current body strictly engulfs above.
Close[T] < Open[T-1]        Current body strictly engulfs below.
```

All inequalities are strict. Equality never qualifies.

## 4. Prior Uptrend Filter

Evaluate the five immediately prior available trading candles, `T-5` through
`T-1`. For each of four adjacent comparisons, from `T-5 -> T-4` through
`T-2 -> T-1`, count one qualifying comparison only when both conditions hold:

```text
High[current] > High[previous]
AND
Low[current] > Low[previous]
```

An uptrend passes when at least three of four comparisons qualify. If fewer
than five prior candles exist, the pattern fails the uptrend requirement.
The pattern candle at `T` is never used for the trend calculation.

## 5. Confirmation

The confirmation candle is `T+1` and passes only when:

```text
Close[T+1] < Low[T]
```

The comparison is strict. If `T+1` is unavailable, confirmation fails. No
candle after `T+1` may be used to determine confirmation.

## 6. Short Entry, Risk, and Target

Entry occurs at the open of `T+2`.

```text
RawEntryPrice = Open[T+2]
EntryFill     = Open[T+2] x 0.999
StopPrice     = High[T]
Risk          = StopPrice - EntryFill
TargetPrice   = EntryFill - (2 x Risk)
```

The 0.1% entry adjustment is adverse for a short because it produces a lower
sale price. Reject the trade when `Risk <= 0`. A valid target must be below
`EntryFill`.

## 7. Observation Window and Short-Side Simulation

The fixed observation window is the five same-ticker candles `T+2` through
`T+6`, inclusive. Evaluate active candles chronologically and stop at the
first exit.

1. **Gap stop:** if `Open >= StopPrice`, exit at `Open`; outcome `LOSS`;
   exit reason `GAP_STOP`.
2. **Gap target:** if `Open <= TargetPrice`, exit at `Open`; outcome `WIN`;
   exit reason `GAP_TARGET`.
3. **Same-bar ambiguity:** if `High >= StopPrice` and `Low <= TargetPrice`,
   record `LOSS`; raw exit at `StopPrice`; exit reason `STOP`. This is the
   mandatory conservative policy.
4. **Intraday stop:** if `High >= StopPrice`, record `LOSS`; raw exit at
   `StopPrice`; exit reason `STOP`.
5. **Intraday target:** if `Low <= TargetPrice`, record `WIN`; raw exit at
   `TargetPrice`; exit reason `TARGET`.
6. **Expiry:** when no barrier is reached by `T+6`, record `EXPIRED`; raw
   exit at `Close[T+6]`; exit reason `EXPIRED`.

If fewer than five same-ticker observation candles are available, the trade
is unavailable and must not receive an expiry classification.

## 8. Exit Costs and Returns

For every short exit, the adverse 0.1% buy-back adjustment is:

```text
ExitFill = RawExit x 1.001
```

Returns use short-side direction and existing project percentage convention:

```text
GrossReturn = ((EntryFill - RawExit) / EntryFill) x 100
NetReturn   = ((EntryFill - ExitFill) / EntryFill) x 100
```

Expired trades remain separately identifiable and marked to market; they are
not reclassified as wins or losses.

## 9. MFE and MAE

MFE and MAE are stored in **price units for both Bullish and Bearish
strategies**. They are not percentages. This is required for future
strategy-comparison code to interpret both strategies consistently.

For a short trade:

```text
MFE = max(EntryFill - Low, 0)
MAE = max(High - EntryFill, 0)
```

Use only completed observation candles strictly before a resolved exit candle.
For an `EXPIRED` trade, use all five observation candles. If exit occurs on
the entry day, no completed candle exists and both values are `0.0`.

## 10. Exclusions and Data Integrity

Apply the existing Version 1 data-quality and exclusion policy directionally
without altering Bullish Engulfing behavior. Exclude or mark unavailable any
candidate requiring unavailable or invalid candles from `T-5` through `T+6`,
including missing confirmation or entry candles, incomplete observation
windows, invalid OHLCV, duplicate dates, non-positive volume, zero or negative
risk, or a calendar gap greater than seven days between required candles.

## 11. Future Reporting Contracts

The future daily candidate file is:

```text
results/bearish_engulfing/daily/daily_candidates.csv
```

It contains any Bearish Engulfing pattern on the latest completed date, even
when it fails the uptrend, confirmation, or trade-eligibility stages. Expected
diagnostic fields include `Universe`, `Ticker`, `PatternDate`, `PreviousDate`,
`UptrendPassed`, `UptrendScore`, `ConfirmationPassed`, `ConfirmationDate`,
`TradeEligible`, `EntryDate`, `EntryPrice`, `StopLoss`, `TargetPrice`, and
`RejectionReason`.

The future daily signal file is:

```text
results/bearish_engulfing/daily/daily_signals.csv
```

It contains only actual eligible current short trades. It must not mix with
Bullish Engulfing output.

## 12. Registry and Implementation Boundary

After this strategy is implemented, it may be registered as
`bearish-engulfing` in the strategy registry. It must not be registered before
implementation and must remain independently executable.

This document defines rules only. It authorizes no pattern detector, trend
evaluator, confirmation engine, trade setup, simulator, performance module,
strategy runner, registry entry, or CSV exporter.

## 13. Directional Mirror Cross-Check

| Bullish Engulfing | Bearish Engulfing |
|---|---|
| Previous candle bearish | Previous candle bullish |
| Current candle bullish | Current candle bearish |
| Three-of-four lower-high/lower-low downtrend | Three-of-four higher-high/higher-low uptrend |
| `Close[T+1] > High[T]` | `Close[T+1] < Low[T]` |
| `EntryFill = Open[T+2] x 1.001` | `EntryFill = Open[T+2] x 0.999` |
| `StopPrice = Low[T]` | `StopPrice = High[T]` |
| `Target = EntryFill + 2R` | `Target = EntryFill - 2R` |
| `ExitFill = RawExit x 0.999` | `ExitFill = RawExit x 1.001` |
| Favorable move is upward | Favorable move is downward |
| MFE/MAE stored in price units | MFE/MAE stored in price units |

No unresolved directional asymmetry remains. The only intentionally explicit
policy is same-bar ambiguity: the stop is recorded first as a conservative
loss on both sides.
