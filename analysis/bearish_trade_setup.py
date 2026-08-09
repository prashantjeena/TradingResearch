"""Frozen short trade-setup calculations for Bearish Engulfing."""
from __future__ import annotations
from collections import defaultdict
import pandas as pd
from analysis.bearish_confirmation import BEARISH_CONFIRMATION_COLUMNS
from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS

BEARISH_TRADE_SETUP_FIELDS=("EntryDate","EntryIndex","RawEntryPrice","EntryFill","StopPrice","Risk","RiskPercent","TargetPrice","TradeEligible","TradeRejectionReason")
BEARISH_TRADE_SETUP_COLUMNS=(*BEARISH_CONFIRMATION_COLUMNS,*BEARISH_TRADE_SETUP_FIELDS)
class BearishTradeSetupInputError(ValueError): """Raised when bearish setup inputs are invalid."""
class BearishTradeSetupEvaluator:
    """Create frozen T+2 short setups without simulating them."""
    def evaluate(self,dataset:pd.DataFrame,patterns:pd.DataFrame)->pd.DataFrame:
        """Append short entry, risk, and target fields.
        Args: dataset: Canonical source data. patterns: Bearish confirmation output.
        Returns: New setup frame.
        Raises: BearishTradeSetupInputError: On invalid references.
        """
        self._validate(dataset,patterns); pos,groups,ranks=self._lookup(dataset); records=[]
        for row in patterns.itertuples(index=False):
            if not bool(row.ConfirmationPassed): records.append((None,None,None,None,None,None,None,None,False,"Pattern did not pass confirmation evaluation.")); continue
            p=pos.get(row.PatternIndex)
            if p is None or dataset.iloc[p]["Ticker"]!=row.Ticker or dataset.iloc[p]["Date"]!=row.Date: raise BearishTradeSetupInputError(f"Invalid PatternIndex: {row.PatternIndex!r}.")
            same=groups[row.Ticker]; rank=ranks[p]
            if rank+2>=len(same): records.append((None,None,None,None,None,None,None,None,False,"Entry candle unavailable.")); continue
            epos=same[rank+2]; candle=dataset.iloc[epos]; raw=float(candle["Open"]); fill=raw*.999; stop=float(dataset.iloc[p]["High"]); risk=stop-fill
            if risk<=0: records.append((candle["Date"],dataset.index[epos],raw,fill,stop,risk,None,None,False,"Trade rejected: Risk must be greater than zero.")); continue
            risk_pct=risk/fill*100; target=fill-2*risk
            records.append((candle["Date"],dataset.index[epos],raw,fill,stop,risk,risk_pct,target,True,None))
        out=patterns.copy(); out[list(BEARISH_TRADE_SETUP_FIELDS)]=pd.DataFrame(records,index=out.index); return out.loc[:,BEARISH_TRADE_SETUP_COLUMNS]
    @staticmethod
    def _lookup(dataset:pd.DataFrame):
        """Build source index mappings."""; pos={}; groups=defaultdict(list); ranks={}
        for p,(i,t) in enumerate(zip(dataset.index,dataset["Ticker"],strict=True)):pos[i]=p;ranks[p]=len(groups[t]);groups[t].append(p)
        return pos,dict(groups),ranks
    @staticmethod
    def _validate(dataset:pd.DataFrame,patterns:pd.DataFrame)->None:
        """Validate input schemas."""
        for frame,cols in ((dataset,CANONICAL_OHLCV_COLUMNS),(patterns,BEARISH_CONFIRMATION_COLUMNS)):
            if any(c not in frame or (frame.columns==c).sum()!=1 for c in cols):raise BearishTradeSetupInputError("Required input columns are missing or duplicated.")
        if not dataset.index.is_unique:raise BearishTradeSetupInputError("Dataset index must be unique.")
