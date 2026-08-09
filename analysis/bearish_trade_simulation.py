"""Frozen five-session short trade simulation for Bearish Engulfing."""
from __future__ import annotations
from collections import defaultdict
import pandas as pd
from analysis.bearish_trade_setup import BEARISH_TRADE_SETUP_COLUMNS
from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS

BEARISH_SIMULATION_FIELDS=("ExitDate","ExitIndex","ExitReason","ExitPrice","ExitFill","Outcome","HoldingDays")
BEARISH_SIMULATION_COLUMNS=(*BEARISH_TRADE_SETUP_COLUMNS,*BEARISH_SIMULATION_FIELDS)
class BearishTradeSimulationInputError(ValueError): """Raised when bearish simulation references are invalid."""
class BearishTradeSimulator:
    """Apply the frozen short-side exit priority without look-ahead."""
    def simulate(self,dataset:pd.DataFrame,setups:pd.DataFrame)->pd.DataFrame:
        """Return deterministic simulation fields for eligible short setups.
        Args: dataset: Canonical source data. setups: Bearish setup output.
        Returns: New simulated-trade frame.
        Raises: BearishTradeSimulationInputError: On unsafe entry references.
        """
        self._validate(dataset,setups); pos,groups,ranks=self._lookup(dataset); records=[]
        for trade in setups.itertuples(index=False):
            if not bool(trade.TradeEligible): records.append((None,None,"Trade was not eligible.",None,None,None,None));continue
            ep=pos.get(trade.EntryIndex)
            if ep is None: raise BearishTradeSimulationInputError(f"Invalid EntryIndex: {trade.EntryIndex!r}.")
            entry=dataset.iloc[ep]
            if entry["Ticker"]!=trade.Ticker or entry["Date"]!=trade.EntryDate or float(entry["Open"])!=float(trade.RawEntryPrice):raise BearishTradeSimulationInputError("Entry metadata does not match source data.")
            window=groups[trade.Ticker][ranks[ep]:ranks[ep]+5]
            if len(window)<5:records.append((None,None,"Observation window unavailable.",None,None,None,None));continue
            records.append(self._window(dataset,window,trade))
        out=setups.copy();out[list(BEARISH_SIMULATION_FIELDS)]=pd.DataFrame(records,index=out.index);return out.loc[:,BEARISH_SIMULATION_COLUMNS]
    @staticmethod
    def _window(dataset:pd.DataFrame,window:list[int],trade:object)->tuple[object,...]:
        """Evaluate exactly five same-ticker observations in frozen priority."""
        for days,p in enumerate(window,1):
            c=dataset.iloc[p]
            if c["Open"]>=trade.StopPrice:return BearishTradeSimulator._exit(dataset,p,"GAP_STOP",c["Open"],"LOSS",days)
            if c["Open"]<=trade.TargetPrice:return BearishTradeSimulator._exit(dataset,p,"GAP_TARGET",c["Open"],"WIN",days)
            if c["High"]>=trade.StopPrice and c["Low"]<=trade.TargetPrice:return BearishTradeSimulator._exit(dataset,p,"STOP",trade.StopPrice,"LOSS",days)
            if c["High"]>=trade.StopPrice:return BearishTradeSimulator._exit(dataset,p,"STOP",trade.StopPrice,"LOSS",days)
            if c["Low"]<=trade.TargetPrice:return BearishTradeSimulator._exit(dataset,p,"TARGET",trade.TargetPrice,"WIN",days)
        p=window[-1];return BearishTradeSimulator._exit(dataset,p,"EXPIRED",dataset.iloc[p]["Close"],"EXPIRED",5)
    @staticmethod
    def _exit(dataset:pd.DataFrame,p:int,reason:str,raw:float,outcome:str,days:int)->tuple[object,...]:
        """Build an adverse short exit record."""; c=dataset.iloc[p];raw=float(raw);return(c["Date"],dataset.index[p],reason,raw,raw*1.001,outcome,days)
    @staticmethod
    def _lookup(dataset:pd.DataFrame):
        """Build source and ticker mappings.""";pos={};g=defaultdict(list);r={}
        for p,(i,t) in enumerate(zip(dataset.index,dataset["Ticker"],strict=True)):pos[i]=p;r[p]=len(g[t]);g[t].append(p)
        return pos,dict(g),r
    @staticmethod
    def _validate(dataset:pd.DataFrame,setups:pd.DataFrame)->None:
        """Validate immutable simulation inputs."""
        for f,cols in ((dataset,CANONICAL_OHLCV_COLUMNS),(setups,BEARISH_TRADE_SETUP_COLUMNS)):
            if any(c not in f or (f.columns==c).sum()!=1 for c in cols):raise BearishTradeSimulationInputError("Required input columns are missing or duplicated.")
        if not dataset.index.is_unique:raise BearishTradeSimulationInputError("Dataset index must be unique.")
