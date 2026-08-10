"""Read-only intraday data validation."""
from __future__ import annotations
import pandas as pd
from intraday.schema import INTRADAY_COLUMNS
from intraday.session import expected_session_starts
class IntradayValidationError(ValueError): """Invalid canonical intraday data."""
def validate(data:pd.DataFrame,interval_minutes:int=5)->dict[str,object]:
    """Return diagnostics or raise without mutating source data."""
    if tuple(data.columns)!=INTRADAY_COLUMNS:raise IntradayValidationError("Canonical intraday schema required.")
    ts=pd.to_datetime(data.Timestamp,errors="coerce")
    if ts.isna().any() or ts.dt.tz is None or data.duplicated(["Ticker","Timestamp"]).any():raise IntradayValidationError("Invalid timestamps or duplicates.")
    x=data[["Open","High","Low","Close","Volume"]].apply(pd.to_numeric,errors="coerce")
    if x.isna().any().any() or (x.Volume<0).any() or (x.High<x[["Open","Close","Low"]].max(axis=1)).any() or (x.Low>x[["Open","Close","High"]].min(axis=1)).any():raise IntradayValidationError("Invalid OHLCV.")
    missing=0
    for (_,trading_date),frame in data.assign(_date=ts.dt.date).groupby(["Ticker","_date"],sort=False):
        expected=expected_session_starts(trading_date,interval_minutes,ts.dt.tz)
        actual=pd.DatetimeIndex(pd.to_datetime(frame["Timestamp"]))
        missing+=len(expected.difference(actual))
    return {"rows":len(data),"timezone":str(ts.dt.tz),"missing_gap_count":missing,"PrototypeOnly":True}
