# TradingResearch Commands

## Run the default strategy

```powershell
py main.py
```

This defaults to `bullish-engulfing`.

## Run Bullish Engulfing explicitly

```powershell
py main.py --strategy bullish-engulfing
```

## Run every registered strategy

```powershell
py main.py --strategy all
```

`all` runs `bullish-engulfing` and `bearish-engulfing` exactly once each.

## Run Bearish Engulfing explicitly

```powershell
py main.py --strategy bearish-engulfing
```

## Result locations

- Daily candidates and signals: `results/bullish_engulfing/daily/`
- Historical per-ticker trades: `results/bullish_engulfing/historical/`
- Per-ticker current-signal exports: `results/bullish_engulfing/signals/`

Bearish Engulfing results are isolated under:

- Daily candidates and signals: `results/bearish_engulfing/daily/`
- Historical per-ticker trades: `results/bearish_engulfing/historical/`
- Per-ticker current-signal exports: `results/bearish_engulfing/signals/`

Raw OHLCV datasets remain shared in `datasets/`.

## Intraday Research Watchlist

```powershell
py -m research.intraday_watchlist
py -m research.intraday_watchlist --trading-date YYYY-MM-DD
```

This produces completed-daily-data candidate stocks only. It does **not**
generate an entry, target, stop, or trade recommendation. Watchlists are
written under `results/intraday_research/prototype/watchlists/`.

## Test commands

```powershell
.venv\Scripts\python.exe -B -m unittest tests.test_strategy_runner
.venv\Scripts\python.exe -B -m unittest discover -s tests
.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8'), filename=path) for path in ('main.py', 'strategies/registry.py')]"
git diff --check
```

## Planned Strategies

Other strategies are not implemented yet. They must be explicitly registered before they can be selected or included in `--strategy all`.
