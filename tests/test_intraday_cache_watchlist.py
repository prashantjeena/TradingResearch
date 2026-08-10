"""Focused cache and watchlist contracts without network access."""
import tempfile,unittest
from pathlib import Path
import pandas as pd
from intraday.cache import IntradayCache
from intraday.schema import INTRADAY_COLUMNS
from intraday.watchlist import IntradayWatchlistGenerator
class TestCacheWatchlist(unittest.TestCase):
 def data(self):return pd.DataFrame([[pd.Timestamp('2026-01-05 09:15',tz='Asia/Kolkata'),1,2,0,1,1,'A.NS']],columns=INTRADAY_COLUMNS)
 def test_cache_isolated_and_metadata(self):
  with tempfile.TemporaryDirectory() as d:
   c=IntradayCache(Path(d)/'datasets/intraday/raw/5m');c.save(self.data(),'A.NS',{'provider':'yfinance','interval':'5m'});loaded=c.load('A.NS');self.assertEqual(len(loaded),1);self.assertEqual(str(loaded['Timestamp'].dt.tz),'Asia/Kolkata');self.assertTrue(c.path('A.NS').with_suffix('.json').exists())
 def test_malformed_cache_is_not_reused(self):
  with tempfile.TemporaryDirectory() as d:
   c=IntradayCache(Path(d)/'datasets/intraday/raw/5m');c.root.mkdir(parents=True);c.path('A.NS').write_text('Timestamp,Open\nbad,1');self.assertIsNone(c.load('A.NS'))
 def test_bearish_and_bullish_watchlists(self):
  sessions=pd.Series(['2026-01-02','2026-01-05']);g=IntradayWatchlistGenerator()
  b=pd.DataFrame([{'Date':'2026-01-02','Ticker':'A.NS','PatternName':'Bullish Engulfing','Open':1,'High':2,'Low':0,'Close':1,'DowntrendPassed':True,'ConfirmationPassed':False}]);self.assertEqual(g.generate(b,sessions,'NIFTY50','LONG').iloc[0].Side,'LONG')
  s=pd.DataFrame([{'Date':'2026-01-02','Ticker':'A.NS','PatternName':'Bearish Engulfing','Open':1,'High':2,'Low':0,'Close':1,'UptrendPassed':True}]);self.assertEqual(g.generate(s,sessions,'NIFTY50','SHORT').iloc[0].Side,'SHORT')
  s['ConfirmationPassed']=False;self.assertEqual(len(g.generate(s,sessions,'NIFTY50','SHORT')),1)
 def test_trend_failures_excluded(self):
  g=IntradayWatchlistGenerator();dates=pd.Series(['2026-01-02','2026-01-05']);b=pd.DataFrame([{'Date':'2026-01-02','Ticker':'A','PatternName':'Bullish Engulfing','Open':1,'High':2,'Low':0,'Close':1,'DowntrendPassed':False}]);self.assertTrue(g.generate(b,dates,'U','LONG').empty)
  s=b.rename(columns={'DowntrendPassed':'UptrendPassed'});self.assertTrue(g.generate(s,dates,'U','SHORT').empty)
 def test_actual_sessions_no_lookahead_and_immutability(self):
  g=IntradayWatchlistGenerator();source=pd.DataFrame([{'Date':'2026-01-02','Ticker':'A','PatternName':'Bullish Engulfing','Open':1,'High':2,'Low':0,'Close':1,'DowntrendPassed':True,'ConfirmationPassed':False,'Outcome':'LOSS','NetReturn':-99}]);original=source.copy(deep=True);a=g.generate(source,pd.Series(['2026-01-02','2026-01-05','2026-01-06']),'U','LONG');source[['ConfirmationPassed','NetReturn']]=[True,999];b=g.generate(source,pd.Series(['2026-01-02','2026-01-05','2026-01-06']),'U','LONG');self.assertEqual(a[['Side','TradingDate']].to_dict(),b[['Side','TradingDate']].to_dict());pd.testing.assert_frame_equal(original,original)
