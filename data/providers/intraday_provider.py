"""Intraday provider contract independent of daily providers."""
from abc import ABC,abstractmethod
class IntradayMarketDataProvider(ABC):
    """Fetch normalized recent intraday candles."""
    @abstractmethod
    def fetch_intraday(self,ticker,start,end,interval):
        """Return canonical intraday OHLCV."""
