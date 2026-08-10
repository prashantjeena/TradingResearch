"""No-look-ahead daily-setup to next-session intraday watchlists."""
import pandas as pd
WATCHLIST_COLUMNS=("SetupDate","TradingDate","Ticker","Universe","Side","PatternName","TrendPassed","TrendScore","PatternOpen","PatternHigh","PatternLow","PatternClose","PrototypeOnly")
class IntradayWatchlistGenerator:
    """Build watchlists without swing confirmation or T+1 price data."""
    def generate(self,setups:pd.DataFrame,available_sessions:pd.Series,universe:str,side:str)->pd.DataFrame:
        """Return qualified rows using the next actual supplied session date."""
        trend="DowntrendPassed" if side=="LONG" else "UptrendPassed";score="DowntrendScore" if side=="LONG" else "UptrendScore";dates=sorted(pd.to_datetime(available_sessions).dt.normalize().unique());rows=[]
        for r in setups.itertuples(index=False):
            if not bool(getattr(r,trend)):continue
            nxt=next((d for d in dates if d>pd.Timestamp(r.Date).normalize()),None)
            if nxt is not None:rows.append((r.Date,nxt,r.Ticker,universe,side,r.PatternName,True,getattr(r,score,None),r.Open,r.High,r.Low,r.Close,True))
        return pd.DataFrame(rows,columns=WATCHLIST_COLUMNS)
