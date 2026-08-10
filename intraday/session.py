"""NSE session handling."""
from __future__ import annotations
from datetime import time,timedelta
import pandas as pd
REGULAR_SESSION_START=time(9,15)
REGULAR_SESSION_END=time(15,30)
LAST_FULL_BAR_START=time(15,25)
def expected_session_starts(trading_date:object,interval_minutes:int=5,timezone:object="Asia/Kolkata")->pd.DatetimeIndex:
    """Return full regular-session bar starts for one NSE cash session."""
    start=pd.Timestamp(trading_date)
    start=start.tz_localize(timezone) if start.tzinfo is None else start.tz_convert(timezone)
    start=start.normalize()+timedelta(hours=9,minutes=15)
    periods=(6*60+15)//interval_minutes
    return pd.date_range(start,periods=periods,freq=f"{interval_minutes}min")
def normalize_and_filter_session(data:pd.DataFrame)->pd.DataFrame:
    """Normalize timestamps and retain full bars starting 09:15--15:25 IST."""
    out=data.copy();out["Timestamp"]=pd.to_datetime(out["Timestamp"],errors="coerce",utc=True).dt.tz_convert("Asia/Kolkata")
    return out.loc[out["Timestamp"].dt.time.between(REGULAR_SESSION_START,LAST_FULL_BAR_START)].sort_values(["Ticker","Timestamp"],kind="stable").reset_index(drop=True)
