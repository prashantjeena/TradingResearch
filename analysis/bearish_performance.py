"""Price-unit short performance metrics for Bearish Engulfing."""
from __future__ import annotations
from collections import defaultdict
import pandas as pd
from analysis.bearish_trade_simulation import BEARISH_SIMULATION_COLUMNS
from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS

BEARISH_PERFORMANCE_FIELDS=("GrossReturn","NetReturn","MFE","MAE")
BEARISH_PERFORMANCE_COLUMNS=(*BEARISH_SIMULATION_COLUMNS,*BEARISH_PERFORMANCE_FIELDS)
class BearishPerformanceInputError(ValueError): """Raised when bearish trade performance cannot be measured safely."""
class BearishTradePerformanceEvaluator:
    """Measure frozen short returns and price-unit excursions read-only."""
    def evaluate(self,dataset:pd.DataFrame,trades:pd.DataFrame)->pd.DataFrame:
        """Append short returns and excursions without changing outcomes.
        Args: dataset: Canonical source data. trades: Bearish simulation output.
        Returns: New performance frame.
        Raises: BearishPerformanceInputError: On invalid resolved references.
        """
        self._validate(dataset,trades);pos,g,r=self._lookup(dataset);records=[]
        for t in trades.itertuples(index=False):
            if t.Outcome is None:records.append((None,None,None,None));continue
            ep=pos.get(t.EntryIndex);xp=pos.get(t.ExitIndex)
            if ep is None or xp is None:raise BearishPerformanceInputError("Resolved trade references are invalid.")
            if dataset.iloc[ep]["Ticker"]!=t.Ticker or dataset.iloc[xp]["Ticker"]!=t.Ticker:raise BearishPerformanceInputError("Cross-ticker performance reference.")
            active=g[t.Ticker][r[ep]:r[ep]+5] if t.Outcome=="EXPIRED" else g[t.Ticker][r[ep]:r[xp]]
            if active:
                candles=dataset.iloc[active];mfe=max(float(t.EntryFill)-float(candles["Low"].min()),0.0);mae=max(float(candles["High"].max())-float(t.EntryFill),0.0)
            else:mfe=mae=0.0
            records.append(((float(t.EntryFill)-float(t.ExitPrice))/float(t.EntryFill)*100,(float(t.EntryFill)-float(t.ExitFill))/float(t.EntryFill)*100,mfe,mae))
        out=trades.copy();out[list(BEARISH_PERFORMANCE_FIELDS)]=pd.DataFrame(records,index=out.index);return out.loc[:,BEARISH_PERFORMANCE_COLUMNS]
    @staticmethod
    def _lookup(dataset:pd.DataFrame):
        """Build source and ticker mappings.""";pos={};g=defaultdict(list);r={}
        for p,(i,t) in enumerate(zip(dataset.index,dataset["Ticker"],strict=True)):pos[i]=p;r[p]=len(g[t]);g[t].append(p)
        return pos,dict(g),r
    @staticmethod
    def _validate(dataset:pd.DataFrame,trades:pd.DataFrame)->None:
        """Validate source and simulation schemas."""
        for f,cols in ((dataset,CANONICAL_OHLCV_COLUMNS),(trades,BEARISH_SIMULATION_COLUMNS)):
            if any(c not in f or(f.columns==c).sum()!=1 for c in cols):raise BearishPerformanceInputError("Required input columns are missing or duplicated.")
        if not dataset.index.is_unique:raise BearishPerformanceInputError("Dataset index must be unique.")
