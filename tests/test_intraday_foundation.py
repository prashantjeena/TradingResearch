"""Focused contract tests for the Phase 35 intraday foundation."""
from __future__ import annotations
import unittest
import pandas as pd
from intraday.schema import INTRADAY_COLUMNS
from intraday.session import expected_session_starts,normalize_and_filter_session
from intraday.validation import validate,IntradayValidationError
from intraday.watchlist import IntradayWatchlistGenerator
class IntradayFoundationTests(unittest.TestCase):
 def frame(self):
  return pd.DataFrame([["2026-08-07 03:45:00+00:00",100,101,99,100,1,"A.NS"],["2026-08-07 03:50:00+00:00",100,101,99,100,1,"A.NS"]],columns=INTRADAY_COLUMNS)
 def test_session_schema_and_validation(self):
  data=normalize_and_filter_session(self.frame());self.assertEqual(str(data.Timestamp.dt.tz),"Asia/Kolkata");self.assertEqual(validate(data)["rows"],2)
 def test_duplicate_rejected(self):
  data=normalize_and_filter_session(self.frame());data=pd.concat([data,data.iloc[[0]]]);
  with self.assertRaises(IntradayValidationError):validate(data)
 def test_session_excludes_outside_rows(self):
  x=self.frame();x.loc[0,'Timestamp']='2026-08-07 02:00:00+00:00';self.assertEqual(len(normalize_and_filter_session(x)),1)
 def test_session_retains_last_full_bar_and_excludes_session_end_marker(self):
  data=pd.DataFrame([['2026-08-07 09:55:00+00:00',100,101,99,100,1,'A.NS'],['2026-08-07 10:00:00+00:00',100,101,99,100,1,'A.NS']],columns=INTRADAY_COLUMNS);filtered=normalize_and_filter_session(data);self.assertEqual([timestamp.time().isoformat() for timestamp in filtered['Timestamp']],['15:25:00'])
 def test_complete_session_grid_and_missing_bar_diagnostics(self):
  timestamps=expected_session_starts('2026-08-07');self.assertEqual(len(timestamps),75);self.assertEqual(timestamps[0].time().isoformat(),'09:15:00');self.assertEqual(timestamps[-1].time().isoformat(),'15:25:00')
  complete=pd.DataFrame([[timestamp,100,101,99,100,1,'A.NS'] for timestamp in timestamps],columns=INTRADAY_COLUMNS);self.assertEqual(validate(complete)['missing_gap_count'],0)
  self.assertEqual(validate(complete.drop(index=20))['missing_gap_count'],1);self.assertEqual(validate(complete.iloc[:-1])['missing_gap_count'],1)
 def test_ohlc_and_volume_invariants_rejected_independently(self):
  """Each documented row-level OHLCV invariant must fail independently."""
  base=pd.DataFrame([[pd.Timestamp('2026-08-07 09:15',tz='Asia/Kolkata'),100,105,95,102,1000,'A.NS']],columns=INTRADAY_COLUMNS)
  cases={'high_below_open':{'High':99},'high_below_close':{'High':101},'low_above_open':{'Low':101},'low_above_close':{'Low':103},'high_below_low':{'High':94},'negative_volume':{'Volume':-1}}
  for label,changes in cases.items():
   with self.subTest(label=label):
    frame=base.copy();
    for column,value in changes.items():frame.loc[0,column]=value
    with self.assertRaises(IntradayValidationError):validate(frame)
 def test_watchlist_uses_next_actual_session_without_confirmation(self):
  s=pd.DataFrame([{"Date":"2026-08-07","Ticker":"A.NS","PatternName":"Bullish Engulfing","Open":1,"High":2,"Low":0,"Close":1,"DowntrendPassed":True,"ConfirmationPassed":False}]);out=IntradayWatchlistGenerator().generate(s,pd.Series(["2026-08-07","2026-08-10"]),"NIFTY50","LONG");self.assertEqual(str(out.iloc[0].TradingDate.date()),"2026-08-10")
