"""Mocked yfinance intraday normalization tests."""
import unittest
from unittest.mock import patch
import pandas as pd
from data.providers.base_provider import ProviderError
from data.providers.yfinance_intraday_provider import YFinanceIntradayProvider
from intraday.schema import INTRADAY_COLUMNS
class TestProvider(unittest.TestCase):
 @patch('data.providers.yfinance_intraday_provider.yf.download')
 def test_canonical_ist_output(self,mock):
  index=pd.DatetimeIndex(['2026-01-05 03:45:00+00:00','2026-01-05 03:50:00+00:00']);mock.return_value=pd.DataFrame({'Open':[1,1],'High':[2,2],'Low':[0,0],'Close':[1,1],'Volume':[1,1]},index=index)
  out=YFinanceIntradayProvider().fetch_intraday('A.NS','2026-01-05','2026-01-06','5m');self.assertEqual(tuple(out.columns),INTRADAY_COLUMNS);self.assertEqual(str(out.Timestamp.dt.tz),'Asia/Kolkata')
  self.assertEqual(out.attrs,{"Provider":"yfinance","Interval":"5m","PrototypeOnly":True})
 @patch('data.providers.yfinance_intraday_provider.yf.download')
 def test_empty_and_missing_columns_raise_provider_error(self,mock):
  mock.return_value=pd.DataFrame()
  with self.assertRaises(ProviderError):YFinanceIntradayProvider().fetch_intraday('A.NS','2026-01-05')
  mock.return_value=pd.DataFrame({'Open':[1]},index=pd.DatetimeIndex(['2026-01-05 03:45+00:00']))
  with self.assertRaises(ProviderError):YFinanceIntradayProvider().fetch_intraday('A.NS','2026-01-05')
