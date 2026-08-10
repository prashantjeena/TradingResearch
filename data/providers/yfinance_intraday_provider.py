"""Recent-only yfinance intraday prototype provider."""
from __future__ import annotations
import pandas as pd,yfinance as yf
from data.providers.base_provider import ProviderError
from data.providers.intraday_provider import IntradayMarketDataProvider
from intraday.schema import INTRADAY_COLUMNS
from intraday.session import normalize_and_filter_session
class YFinanceIntradayProvider(IntradayMarketDataProvider):
    """Retrieve recent 5m/15m data; never multi-year evidence."""
    def fetch_intraday(self,ticker,start,end=None,interval="5m"):
        """Fetch prototype bars, filter NSE session, and normalize timezone."""
        raw=yf.download(tickers=ticker,start=start,end=end,interval=interval,auto_adjust=False,progress=False,threads=False,prepost=False)
        if raw is None or raw.empty:raise ProviderError(f"yfinance returned no intraday data for {ticker}.")
        if isinstance(raw.columns,pd.MultiIndex):raw.columns=raw.columns.get_level_values(0)
        required=("Open","High","Low","Close","Volume")
        missing=[column for column in required if column not in raw.columns]
        if missing:raise ProviderError("yfinance intraday response missing: "+", ".join(missing))
        timestamps=pd.to_datetime(raw.index,errors="coerce")
        if timestamps.isna().any() or timestamps.tz is None:raise ProviderError("yfinance intraday response has invalid or naive timestamps.")
        out=pd.DataFrame({"Timestamp":timestamps,"Open":raw.Open,"High":raw.High,"Low":raw.Low,"Close":raw.Close,"Volume":raw.Volume,"Ticker":ticker})
        result=normalize_and_filter_session(out).loc[:,INTRADAY_COLUMNS]
        result.attrs.update({"Provider":"yfinance","Interval":interval,"PrototypeOnly":True})
        return result
