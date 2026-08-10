"""Development-only recent-data intraday diagnostics; not a strategy runner."""
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from data.providers.yfinance_intraday_provider import YFinanceIntradayProvider
from intraday.cache import IntradayCache
from intraday.validation import validate

def run(tickers:tuple[str,...]=( "RELIANCE.NS", "INFY.NS", "HDFCBANK.NS"), days:int=5)->pd.DataFrame:
    """Fetch/reuse a small prototype sample and write diagnostics only."""
    cache=IntradayCache(); provider=YFinanceIntradayProvider(); records=[]; end=datetime.now(); start=end-timedelta(days=days)
    for ticker in tickers:
        data=cache.load(ticker); reused=data is not None
        if data is None:
            data=provider.fetch_intraday(ticker,start,end,"5m");cache.save(data,ticker,{"provider":"yfinance","interval":"5m","requested_start":start,"requested_end":end,"retrieved_start":data.Timestamp.min(),"retrieved_end":data.Timestamp.max(),"timezone":"Asia/Kolkata"})
        records.append({"Ticker":ticker,"CacheReused":reused,**validate(data),"PrototypeOnly":True})
    report=pd.DataFrame(records);out=Path("results/intraday_research/prototype/diagnostics");out.mkdir(parents=True,exist_ok=True);report.to_csv(out/"diagnostics.csv",index=False);return report
