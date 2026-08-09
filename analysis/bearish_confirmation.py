"""Frozen Day-T+1 confirmation for Bearish Engulfing."""
from __future__ import annotations
from collections import defaultdict
import pandas as pd
from analysis.bearish_uptrend import UPTREND_COLUMNS
from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS

BEARISH_CONFIRMATION_COLUMNS = (*UPTREND_COLUMNS, "ConfirmationPassed", "ConfirmationDate", "ConfirmationIndex", "ConfirmationRejectionReason")
class BearishConfirmationInputError(ValueError):
    """Raised when confirmation source references are invalid."""
class BearishConfirmationEvaluator:
    """Confirm qualified patterns only when Close[T+1] is below Low[T]."""
    def evaluate(self, dataset: pd.DataFrame, patterns: pd.DataFrame) -> pd.DataFrame:
        """Return a new frame with strict same-ticker confirmation fields.
        Args: dataset: Canonical source data. patterns: Uptrend output.
        Returns: New confirmation result frame.
        Raises: BearishConfirmationInputError: On invalid source references.
        """
        self._validate(dataset, patterns); pos, groups, ranks = self._lookup(dataset); rows=[]
        for row in patterns.itertuples(index=False):
            if not bool(row.UptrendPassed): rows.append((False,None,None,"Pattern did not pass uptrend evaluation.")); continue
            p=pos.get(row.PatternIndex)
            if p is None or dataset.iloc[p]["Ticker"] != row.Ticker or dataset.iloc[p]["Date"] != row.Date: raise BearishConfirmationInputError(f"Invalid PatternIndex: {row.PatternIndex!r}.")
            same=groups[row.Ticker]; rank=ranks[p]
            if rank+1 >= len(same): rows.append((False,None,None,"Confirmation candle unavailable.")); continue
            cpos=same[rank+1]; candle=dataset.iloc[cpos]
            if candle["Close"] < dataset.iloc[p]["Low"]: rows.append((True,candle["Date"],dataset.index[cpos],None))
            else: rows.append((False,None,None,"Confirmation failed: Close[T+1] >= Low[T]."))
        out=patterns.copy(); out[["ConfirmationPassed","ConfirmationDate","ConfirmationIndex","ConfirmationRejectionReason"]]=pd.DataFrame(rows,index=out.index); return out.loc[:,BEARISH_CONFIRMATION_COLUMNS]
    @staticmethod
    def _lookup(dataset: pd.DataFrame):
        """Build same-ticker source mappings."""
        pos={}; groups=defaultdict(list); ranks={}
        for p,(i,t) in enumerate(zip(dataset.index,dataset["Ticker"],strict=True)): pos[i]=p; ranks[p]=len(groups[t]); groups[t].append(p)
        return pos,dict(groups),ranks
    @staticmethod
    def _validate(dataset: pd.DataFrame, patterns: pd.DataFrame)->None:
        """Validate required immutable input contracts."""
        for frame,columns in ((dataset,CANONICAL_OHLCV_COLUMNS),(patterns,UPTREND_COLUMNS)):
            if any(c not in frame or (frame.columns==c).sum()!=1 for c in columns): raise BearishConfirmationInputError("Required input columns are missing or duplicated.")
        if not dataset.index.is_unique: raise BearishConfirmationInputError("Dataset index must be unique.")
