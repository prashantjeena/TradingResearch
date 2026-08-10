"""Separate disk cache for prototype intraday data."""
from pathlib import Path
import json
import pandas as pd
from intraday.schema import INTRADAY_COLUMNS
class IntradayCache:
    """Persist canonical 5-minute data below the isolated intraday directory."""
    def __init__(self,root:Path=Path("datasets/intraday/raw/5m")): self.root=root
    def path(self,ticker:str)->Path: return self.root/f"{ticker.replace('.','_')}_5m.csv"
    def load(self,ticker:str)->pd.DataFrame|None:
        """Return cached canonical data or None when absent."""
        p=self.path(ticker)
        if not p.exists(): return None
        try:
            data=pd.read_csv(p,parse_dates=["Timestamp"])
        except (OSError,ValueError): return None
        timestamps=pd.to_datetime(data["Timestamp"],errors="coerce")
        if tuple(data.columns)!=INTRADAY_COLUMNS or timestamps.isna().any() or timestamps.dt.tz is None: return None
        data=data.copy();data["Timestamp"]=timestamps.dt.tz_convert("Asia/Kolkata")
        return data
    def save(self,data:pd.DataFrame,ticker:str,metadata:dict[str,object])->Path:
        """Persist data and simple prototype provenance metadata."""
        if tuple(data.columns)!=INTRADAY_COLUMNS:raise ValueError("Canonical schema required.")
        p=self.path(ticker);p.parent.mkdir(parents=True,exist_ok=True);data.to_csv(p,index=False);p.with_suffix(".json").write_text(json.dumps({**metadata,"PrototypeOnly":True},default=str),encoding="utf-8");return p
