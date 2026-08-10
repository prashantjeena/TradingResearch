"""Canonical intraday contracts."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import time
INTRADAY_COLUMNS=("Timestamp","Open","High","Low","Close","Volume","Ticker")
@dataclass(frozen=True,slots=True)
class IntradayTradePlan:
    """Explicit model plan consumed by the generic simulator.

    Slippage and fees are decimal return fractions: ``0.001`` represents
    0.1%. Simulator return fields are reported as percentage points.
    """
    ticker:str; trading_date:object; side:str; entry_trigger:float; stop_price:float; target_price:float; latest_entry_time:time|None; forced_exit_time:time; entry_slippage:float=0.; exit_slippage:float=0.; fees:float=0.
