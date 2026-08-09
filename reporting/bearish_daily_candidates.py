"""Presentation-only latest-day Bearish Engulfing candidate report."""
from __future__ import annotations
import pandas as pd
from analysis.bearish_trade_setup import BEARISH_TRADE_SETUP_COLUMNS

BEARISH_DAILY_CANDIDATE_COLUMNS=("Universe","Ticker","PatternDate","UptrendScore","CandidateStatus","Open","High","Low","Close","PreviousDate","PreviousOpen","PreviousHigh","PreviousLow","PreviousClose","UptrendPassed","ConfirmationPassed","ConfirmationDate","TradeEligible","EntryDate","EntryPrice","StopLoss","TargetPrice","RejectionReason")
BEARISH_DAILY_CANDIDATE_PRICE_COLUMNS=("Open","High","Low","Close","PreviousOpen","PreviousHigh","PreviousLow","PreviousClose","EntryPrice","StopLoss","TargetPrice")
class BearishDailyCandidatesReportError(ValueError): """Raised when candidate projection inputs are invalid."""
class BearishDailyCandidatesReportGenerator:
    """Project all latest-date bearish patterns, including rejected candidates."""
    def generate(self,dataset:pd.DataFrame,trade_setups:pd.DataFrame,latest_trading_date:pd.Timestamp,universe:str)->pd.DataFrame:
        """Return a new latest-day diagnostic candidate frame.
        Args: dataset: Canonical source data. trade_setups: Bearish setup output. latest_trading_date: Date cutoff. universe: Scanner bucket.
        Returns: Candidate-only presentation data.
        Raises: BearishDailyCandidatesReportError: If required columns are absent.
        """
        if any(c not in trade_setups for c in BEARISH_TRADE_SETUP_COLUMNS):raise BearishDailyCandidatesReportError("Invalid bearish trade setup columns.")
        latest=trade_setups.loc[pd.to_datetime(trade_setups["Date"]).dt.normalize()==pd.Timestamp(latest_trading_date).normalize()].copy()
        if latest.empty:return pd.DataFrame(columns=BEARISH_DAILY_CANDIDATE_COLUMNS)
        lookup={i:p for p,i in enumerate(dataset.index)};records=[]
        for row in latest.itertuples(index=False):
            p=lookup.get(row.PatternIndex)
            if p is None:raise BearishDailyCandidatesReportError("PatternIndex is unavailable.")
            candle=dataset.iloc[p];previous=dataset.iloc[p-1] if p and dataset.iloc[p-1]["Ticker"]==row.Ticker else None;score=row.UptrendScore
            status="PASSED UPTREND" if score in (3,4) else "NEAR FILTER" if score==2 else "REJECTED"
            reason=row.UptrendRejectionReason if not row.UptrendPassed else row.ConfirmationRejectionReason if not row.ConfirmationPassed else row.TradeRejectionReason
            records.append(dict(Universe=universe,Ticker=row.Ticker,PatternDate=row.Date,UptrendScore=score,CandidateStatus=status,Open=candle.Open,High=candle.High,Low=candle.Low,Close=candle.Close,PreviousDate=row.PreviousDate,PreviousOpen=None if previous is None else previous.Open,PreviousHigh=None if previous is None else previous.High,PreviousLow=None if previous is None else previous.Low,PreviousClose=None if previous is None else previous.Close,UptrendPassed=row.UptrendPassed,ConfirmationPassed=row.ConfirmationPassed,ConfirmationDate=row.ConfirmationDate,TradeEligible=row.TradeEligible,EntryDate=row.EntryDate,EntryPrice=row.EntryFill,StopLoss=row.StopPrice,TargetPrice=row.TargetPrice,RejectionReason=reason))
        return pd.DataFrame(records,columns=BEARISH_DAILY_CANDIDATE_COLUMNS)
