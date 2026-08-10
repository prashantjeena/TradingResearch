"""Conservative model-agnostic intraday execution semantics."""
from __future__ import annotations
import pandas as pd
from intraday.schema import IntradayTradePlan

class IntradaySimulator:
    """Evaluate explicit plans without selecting strategy levels."""
    def simulate(self,bars:pd.DataFrame,plan:IntradayTradePlan,provider:str="yfinance",interval:str="5m")->dict[str,object]:
        """Simulate one date using STOP priority whenever OHLC ordering is ambiguous."""
        data=bars.loc[pd.to_datetime(bars["Timestamp"]).dt.date==pd.Timestamp(plan.trading_date).date()].sort_values("Timestamp",kind="stable")
        if data.empty:return self._none(plan,"NO_ENTRY",provider,interval)
        entry:tuple[object,float]|None=None
        for row in data.itertuples(index=False):
            if plan.forced_exit_time is not None and row.Timestamp.time()>plan.forced_exit_time:
                break
            if entry is None:
                invalid=(plan.side=="LONG" and row.Open<=plan.stop_price) or (plan.side=="SHORT" and row.Open>=plan.stop_price)
                beyond_target=(plan.side=="LONG" and row.Open>=plan.target_price) or (plan.side=="SHORT" and row.Open<=plan.target_price)
                if invalid or beyond_target:return self._none(plan,"INVALIDATED",provider,interval)
                triggered=(plan.side=="LONG" and row.High>=plan.entry_trigger) or (plan.side=="SHORT" and row.Low<=plan.entry_trigger)
                if plan.latest_entry_time is not None and row.Timestamp.time()>plan.latest_entry_time: continue
                if not triggered: continue
                raw=row.Open if ((plan.side=="LONG" and row.Open>=plan.entry_trigger) or (plan.side=="SHORT" and row.Open<=plan.entry_trigger)) else plan.entry_trigger
                entry=(row.Timestamp,raw*(1+plan.entry_slippage if plan.side=="LONG" else 1-plan.entry_slippage))
                stop=(plan.side=="LONG" and row.Low<=plan.stop_price) or (plan.side=="SHORT" and row.High>=plan.stop_price)
                target=(plan.side=="LONG" and row.High>=plan.target_price) or (plan.side=="SHORT" and row.Low<=plan.target_price)
                if stop or target:return self._exit(plan,entry,row.Timestamp,plan.stop_price if stop else plan.target_price,"STOP" if stop else "TARGET","LOSS" if stop else "WIN",provider,interval)
                continue
            stop=(plan.side=="LONG" and row.Low<=plan.stop_price) or (plan.side=="SHORT" and row.High>=plan.stop_price)
            target=(plan.side=="LONG" and row.High>=plan.target_price) or (plan.side=="SHORT" and row.Low<=plan.target_price)
            if stop or target:return self._exit(plan,entry,row.Timestamp,plan.stop_price if stop else plan.target_price,"STOP" if stop else "TARGET","LOSS" if stop else "WIN",provider,interval)
        if entry is None:return self._none(plan,"NO_ENTRY",provider,interval)
        eligible=data.loc[data["Timestamp"].dt.time<=plan.forced_exit_time] if plan.forced_exit_time is not None else data
        last=eligible.iloc[-1]
        raw=float(last["Close"]); provisional=self._exit(plan,entry,last["Timestamp"],raw,"FORCED_EXIT","FLAT",provider,interval)
        provisional["Outcome"]="WIN" if provisional["NetReturn"]>0 else "LOSS" if provisional["NetReturn"]<0 else "FLAT"
        return provisional
    def _none(self,p,r,provider,interval): return {"Ticker":p.ticker,"TradingDate":p.trading_date,"Side":p.side,"EntryFill":None,"ExitFill":None,"ExitReason":r,"Outcome":"NO_TRADE","GrossReturn":None,"NetReturn":None,"HoldingMinutes":None,"Provider":provider,"Interval":interval,"PrototypeOnly":True}
    def _exit(self,p,e,t,raw,reason,out,provider,interval):
        fill=raw*(1-p.exit_slippage if p.side=="LONG" else 1+p.exit_slippage);gross=((raw-e[1])/e[1] if p.side=="LONG" else(e[1]-raw)/e[1])*100;net=((fill-e[1])/e[1] if p.side=="LONG" else(e[1]-fill)/e[1])*100-(p.fees*100)
        return {"Ticker":p.ticker,"TradingDate":p.trading_date,"Side":p.side,"EntryTime":e[0],"EntryFill":e[1],"ExitTime":t,"RawExit":raw,"ExitFill":fill,"ExitReason":reason,"Outcome":out,"GrossReturn":gross,"NetReturn":net,"HoldingMinutes":(t-e[0]).total_seconds()/60,"Provider":provider,"Interval":interval,"PrototypeOnly":True}
