"""Protocol boundary for future execution models."""
from typing import Protocol
from intraday.schema import IntradayTradePlan
class ExecutionModel(Protocol):
    """Future model creates a plan; it does not simulate fills."""
    def create_plan(self,watchlist_row:object)->IntradayTradePlan: ...
