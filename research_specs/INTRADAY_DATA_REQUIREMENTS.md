# Intraday Data Requirements

Status: DESIGN REQUIREMENTS — PROVIDER NOT YET SELECTED

## Canonical Schema

Every intraday provider must normalize output to this exact ordered schema:

```text
Timestamp, Open, High, Low, Close, Volume, Ticker
```

`Timestamp` must be timezone-aware or explicitly normalized to
`Asia/Kolkata`. Trading date must be derivable without ambiguity.

## Quality and Session Requirements

- Include regular NSE cash-session candles only; exclude accidental pre/post
  market observations.
- Sort deterministically in chronological order within ticker.
- Detect duplicate rows and duplicate timestamps.
- Report missing expected five-minute candles; diagnostics must not silently
  manufacture data.
- Validate numeric OHLCV values and OHLC consistency: non-negative volume,
  high not below low, and open/close within the high-low range.
- Preserve raw provider timestamps alongside normalized timestamps when a
  provider format requires auditability.

## Interval and History Requirements

Five-minute OHLCV is the primary source interval. Fifteen-minute bars may be
downloaded directly or resampled only from complete, validated five-minute
bars, using session-aware boundaries. A serious study should target multiple
years spanning varied market conditions; a short retention window must be
labelled as a prototype limitation, not a long-term backtest.

## Retrieval, Storage, and Mapping

Providers must support chunked date-range retrieval, bounded retries, stable
instrument identifiers, and rate-limit-aware caching. Cache raw normalized
intraday data by provider, instrument identifier, interval, and time range;
never mix vendors silently. A durable NSE symbol-to-provider-instrument map
is required because Yahoo `.NS` symbols are not a universal provider key.

Corporate actions, symbol changes, suspensions, and revised history require
explicit provenance and reconciliation policy before cross-period results are
treated as comparable.

## Provider Abstraction Requirements

The future provider interface must distinguish daily and intraday capability
without breaking daily research. It must declare supported intervals,
historical retention, timezone semantics, exchange/instrument mapping,
authentication requirements, per-request limits, and data provenance.

Acceptance requires verified NSE equity 5-minute OHLCV, adequate multi-year
retention, reproducible historical retrieval, usable rate limits for the
configured universe, explicit timestamps, and a terms-of-use-compatible data
workflow.

## Provider Audit Conclusion

| Provider | Conclusion |
|---|---|
| yfinance | Suitable only for a short recent prototype; its intraday history is limited and is not multi-year research data. |
| Zerodha Kite Connect | Primary serious-research candidate to evaluate next; documented NSE historical candles include 5-minute intervals and multi-year archived coverage. |
| DhanHQ | Viable candidate, pending explicit verification of retention, rate limits, completeness, and corporate-action behavior. |
| Upstox | Current evidence is insufficient to establish the required multi-year intraday depth. |
| Official/specialist NSE data | Authoritative or specialist-grade option, but paid and operationally heavier. |

No provider is selected, subscribed to, configured, or implemented by this
document.
