"""Focused conservative simulator checks."""
import unittest
from datetime import time
import pandas as pd
from intraday.schema import INTRADAY_COLUMNS,IntradayTradePlan
from intraday.simulation import IntradaySimulator
class TestSimulation(unittest.TestCase):
 def bars(self,rows):return pd.DataFrame(rows,columns=INTRADAY_COLUMNS)
 def plan(self,side="LONG"):return IntradayTradePlan("A.NS",pd.Timestamp("2026-01-05"),side,101,100,103,None,time(15,15))
 def test_long_entry_bar_ambiguity_stops(self):
  b=self.bars([[pd.Timestamp("2026-01-05 09:15",tz="Asia/Kolkata"),100.5,104,99,102,1,"A.NS"]]);self.assertEqual(IntradaySimulator().simulate(b,self.plan())["ExitReason"],"STOP")
 def test_long_gap_entry_uses_open(self):
  b=self.bars([[pd.Timestamp("2026-01-05 09:15",tz="Asia/Kolkata"),102,102.5,101.5,102,1,"A.NS"]]);self.assertEqual(IntradaySimulator().simulate(b,self.plan())["EntryFill"],102)
 def test_forced_exit_uses_cutoff_bar(self):
  b=self.bars([[pd.Timestamp("2026-01-05 09:15",tz="Asia/Kolkata"),101,102,100.5,101,1,"A.NS"],[pd.Timestamp("2026-01-05 15:15",tz="Asia/Kolkata"),101,102,100.5,102,1,"A.NS"],[pd.Timestamp("2026-01-06 09:15",tz="Asia/Kolkata"),101,200,1,200,1,"A.NS"]]);self.assertEqual(IntradaySimulator().simulate(b,self.plan())["ExitReason"],"FORCED_EXIT")
 def test_latest_entry_cutoff_and_next_day_isolation(self):
  p=self.plan();p=IntradayTradePlan(p.ticker,p.trading_date,p.side,p.entry_trigger,p.stop_price,p.target_price,time(10,0),p.forced_exit_time)
  b=self.bars([[pd.Timestamp("2026-01-05 10:00",tz="Asia/Kolkata"),100.5,100.8,100.2,100.5,1,"A.NS"],[pd.Timestamp("2026-01-05 10:05",tz="Asia/Kolkata"),100.6,101.5,100.4,101.2,1,"A.NS"],[pd.Timestamp("2026-01-06 09:15",tz="Asia/Kolkata"),100,200,1,200,1,"A.NS"]]);r=IntradaySimulator().simulate(b,p);self.assertEqual(r['ExitReason'],'NO_ENTRY');self.assertEqual(r['Outcome'],'NO_TRADE')
 def test_short_forced_exit_and_holding_time(self):
  p=IntradayTradePlan('A.NS',pd.Timestamp('2026-01-05'),'SHORT',99,102,96,None,time(9,20));b=self.bars([[pd.Timestamp('2026-01-05 09:15',tz='Asia/Kolkata'),100,101,98,99,1,'A.NS'],[pd.Timestamp('2026-01-05 09:20',tz='Asia/Kolkata'),99,100,98,98.5,1,'A.NS'],[pd.Timestamp('2026-01-06 09:15',tz='Asia/Kolkata'),99,200,1,1,1,'A.NS']]);r=IntradaySimulator().simulate(b,p);self.assertEqual(r['ExitReason'],'FORCED_EXIT');self.assertEqual(r['HoldingMinutes'],5)
 def test_latest_entry_before_and_exact_cutoff_long_short(self):
  for side,trigger,stop,target,open_ in [('LONG',101,99,104,101),('SHORT',99,102,96,99)]:
   for stamp in ['09:55','10:00']:
    p=IntradayTradePlan('A.NS',pd.Timestamp('2026-01-05'),side,trigger,stop,target,time(10,0),time(10,5));b=self.bars([[pd.Timestamp(f'2026-01-05 {stamp}',tz='Asia/Kolkata'),open_,101 if side=='LONG' else 100,98 if side=='LONG' else 99,open_,1,'A.NS']]);self.assertNotEqual(IntradaySimulator().simulate(b,p)['ExitReason'],'NO_ENTRY')
 def test_short_after_cutoff_and_next_day_extremes_ignored(self):
  p=IntradayTradePlan('A.NS',pd.Timestamp('2026-01-05'),'SHORT',99,102,96,time(10,0),time(15,15));b=self.bars([[pd.Timestamp('2026-01-05 10:00',tz='Asia/Kolkata'),100,101,99.5,100,1,'A.NS'],[pd.Timestamp('2026-01-05 10:05',tz='Asia/Kolkata'),100,101,98.5,99,1,'A.NS'],[pd.Timestamp('2026-01-06 09:15',tz='Asia/Kolkata'),99,200,1,1,1,'A.NS']]);r=IntradaySimulator().simulate(b,p);self.assertEqual(r['ExitReason'],'NO_ENTRY');self.assertEqual(r['Outcome'],'NO_TRADE')
 def test_next_day_target_and_stop_are_ignored_after_entry(self):
  p=IntradayTradePlan('A.NS',pd.Timestamp('2026-01-05'),'LONG',101,99,103,None,time(9,20));d=self.bars([[pd.Timestamp('2026-01-05 09:15',tz='Asia/Kolkata'),101,102,100,101.5,1,'A.NS'],[pd.Timestamp('2026-01-05 09:20',tz='Asia/Kolkata'),101.5,102,100,101.75,1,'A.NS']])
  for next_day in [[pd.Timestamp('2026-01-06 09:15',tz='Asia/Kolkata'),101,104,100,103,1,'A.NS'],[pd.Timestamp('2026-01-06 09:15',tz='Asia/Kolkata'),101,102,98,99,1,'A.NS']]:
   self.assertEqual(IntradaySimulator().simulate(pd.concat([d,self.bars([next_day])],ignore_index=True),p)['ExitReason'],'FORCED_EXIT')
 def test_next_day_invalidation_and_extremes_do_not_change_result_or_input(self):
  p=IntradayTradePlan('A.NS',pd.Timestamp('2026-01-05'),'LONG',101,99,103,None,time(9,20));d=self.bars([[pd.Timestamp('2026-01-05 09:15',tz='Asia/Kolkata'),101,102,100,101.5,1,'A.NS'],[pd.Timestamp('2026-01-05 09:20',tz='Asia/Kolkata'),101.5,102,100,101.75,1,'A.NS']]);extended=pd.concat([d,self.bars([[pd.Timestamp('2026-01-06 09:15',tz='Asia/Kolkata'),98,200,1,150,1,'A.NS']])],ignore_index=True);before=d.copy(deep=True);before_extended=extended.copy(deep=True)
  base=IntradaySimulator().simulate(d,p);with_next_day=IntradaySimulator().simulate(extended,p)
  for field in ['ExitReason','Outcome','EntryTime','ExitTime','RawExit','HoldingMinutes']:self.assertEqual(base[field],with_next_day[field])
  pd.testing.assert_frame_equal(d,before);pd.testing.assert_frame_equal(extended,before_extended)
 def test_target_and_stop_precede_forced_exit_for_both_sides(self):
  cases=[
   ('LONG','TARGET',101,99,103,[[100,101,100,100.5],[101,103,100,102],[101,102,99,100]],5),
   ('LONG','STOP',101,99,103,[[100,101,100,100.5],[101,102,99,100],[101,104,100,103]],5),
   ('SHORT','TARGET',99,102,96,[[100,101,99,99.5],[99,100,96,97],[99,102,95,96]],5),
   ('SHORT','STOP',99,102,96,[[100,101,99,99.5],[99,102,97,101],[99,100,96,97]],5),
  ]
  for side,reason,trigger,stop,target,values,holding in cases:
   with self.subTest(side=side,reason=reason):
    p=IntradayTradePlan('A.NS',pd.Timestamp('2026-01-05'),side,trigger,stop,target,None,time(9,30));rows=[[pd.Timestamp(f'2026-01-05 09:{15+5*i:02d}',tz='Asia/Kolkata'),*bar,1,'A.NS'] for i,bar in enumerate(values)];r=IntradaySimulator().simulate(self.bars(rows),p);self.assertEqual(r['ExitReason'],reason);self.assertEqual(r['HoldingMinutes'],holding)
 def test_forced_exit_uses_final_eligible_bar_and_ignores_later_same_day_bar(self):
  p=IntradayTradePlan('A.NS',pd.Timestamp('2026-01-05'),'LONG',101,99,103,None,time(9,20));b=self.bars([[pd.Timestamp('2026-01-05 09:15',tz='Asia/Kolkata'),100,101,100,100.5,1,'A.NS'],[pd.Timestamp('2026-01-05 09:20',tz='Asia/Kolkata'),101,102,100,101.75,1,'A.NS'],[pd.Timestamp('2026-01-05 09:25',tz='Asia/Kolkata'),101,104,98,103,1,'A.NS']]);r=IntradaySimulator().simulate(b,p);self.assertEqual(r['ExitReason'],'FORCED_EXIT');self.assertEqual(r['RawExit'],101.75);self.assertEqual(r['HoldingMinutes'],5)
 def test_no_entry_and_invalidation_have_no_holding_time(self):
  no_entry=self.bars([[pd.Timestamp('2026-01-05 09:15',tz='Asia/Kolkata'),100,100.5,99.5,100,1,'A.NS']]);invalidated=self.bars([[pd.Timestamp('2026-01-05 09:15',tz='Asia/Kolkata'),99,101,98,99,1,'A.NS']]);p=self.plan()
  self.assertIsNone(IntradaySimulator().simulate(no_entry,p)['HoldingMinutes']);self.assertIsNone(IntradaySimulator().simulate(invalidated,p)['HoldingMinutes'])
 def test_all_exit_outcomes_leave_inputs_unchanged(self):
  p=self.plan();frames=[
   self.bars([[pd.Timestamp('2026-01-05 09:15',tz='Asia/Kolkata'),100,103,100,102,1,'A.NS']]),
   self.bars([[pd.Timestamp('2026-01-05 09:15',tz='Asia/Kolkata'),100,101,99,100,1,'A.NS']]),
   self.bars([[pd.Timestamp('2026-01-05 09:15',tz='Asia/Kolkata'),100,101,100,100.5,1,'A.NS']]),
   self.bars([[pd.Timestamp('2026-01-05 09:15',tz='Asia/Kolkata'),100,100.5,99.5,100,1,'A.NS']]),
   self.bars([[pd.Timestamp('2026-01-05 09:15',tz='Asia/Kolkata'),100,101,98,99,1,'A.NS']]),
  ]
  for frame in frames:
   before=frame.copy(deep=True);IntradaySimulator().simulate(frame,p);pd.testing.assert_frame_equal(frame,before)
 def test_exact_target_return_math_with_decimal_slippage_and_fees(self):
  long=IntradayTradePlan('A.NS',pd.Timestamp('2026-01-05'),'LONG',100,90,105,None,time(9,15),.001,.001,.001);short=IntradayTradePlan('A.NS',pd.Timestamp('2026-01-05'),'SHORT',100,110,95,None,time(9,15),.001,.001,.001)
  long_result=IntradaySimulator().simulate(self.bars([[pd.Timestamp('2026-01-05 09:15',tz='Asia/Kolkata'),100,105,99,104,1,'A.NS']]),long);short_result=IntradaySimulator().simulate(self.bars([[pd.Timestamp('2026-01-05 09:15',tz='Asia/Kolkata'),100,101,95,96,1,'A.NS']]),short)
  for result,entry_fill,exit_fill,raw_exit in [(long_result,100.1,104.895,105),(short_result,99.9,95.095,95)]:
   gross=(raw_exit-entry_fill)/entry_fill*100 if result['Side']=='LONG' else (entry_fill-raw_exit)/entry_fill*100;net=(exit_fill-entry_fill)/entry_fill*100-.1 if result['Side']=='LONG' else (entry_fill-exit_fill)/entry_fill*100-.1
   self.assertEqual(result['ExitReason'],'TARGET');self.assertAlmostEqual(result['EntryFill'],entry_fill,places=12);self.assertAlmostEqual(result['ExitFill'],exit_fill,places=12);self.assertAlmostEqual(result['GrossReturn'],gross,places=12);self.assertAlmostEqual(result['NetReturn'],net,places=12)
 def test_stop_and_forced_exit_return_math_for_both_sides(self):
  cases=[
   ('LONG','STOP',100,90,105,[[100,100,90,91]],(90-100)/100*100),
   ('SHORT','STOP',100,110,95,[[100,110,99,109]],(100-110)/100*100),
   ('LONG','FORCED_EXIT',100,90,110,[[100,100,99,100],[100,109,99,105]],(105-100)/100*100),
   ('SHORT','FORCED_EXIT',100,110,90,[[100,101,100,100],[100,109,91,95]],(100-95)/100*100),
  ]
  for side,reason,trigger,stop,target,values,expected in cases:
   with self.subTest(side=side,reason=reason):
    p=IntradayTradePlan('A.NS',pd.Timestamp('2026-01-05'),side,trigger,stop,target,None,time(9,20));rows=[[pd.Timestamp(f'2026-01-05 09:{15+5*i:02d}',tz='Asia/Kolkata'),*bar,1,'A.NS'] for i,bar in enumerate(values)];r=IntradaySimulator().simulate(self.bars(rows),p);self.assertEqual(r['ExitReason'],reason);self.assertAlmostEqual(r['GrossReturn'],expected,places=12);self.assertAlmostEqual(r['NetReturn'],expected,places=12)
 def test_adverse_slippage_and_decimal_fees_never_improve_net_return(self):
  for side,trigger,stop,target,bar in [('LONG',100,90,110,[100,109,99,105]),('SHORT',100,110,90,[100,109,91,95])]:
   with self.subTest(side=side):
    def run(entry_slippage=0.,exit_slippage=0.,fees=0.):
     p=IntradayTradePlan('A.NS',pd.Timestamp('2026-01-05'),side,trigger,stop,target,None,time(9,20),entry_slippage,exit_slippage,fees);return IntradaySimulator().simulate(self.bars([[pd.Timestamp('2026-01-05 09:15',tz='Asia/Kolkata'),*bar[:-1],100,1,'A.NS'],[pd.Timestamp('2026-01-05 09:20',tz='Asia/Kolkata'),*bar,1,'A.NS']]),p)
    baseline=run();self.assertLess(run(fees=.001)['NetReturn'],baseline['NetReturn']);self.assertLessEqual(run(entry_slippage=.001)['NetReturn'],baseline['NetReturn']);self.assertLessEqual(run(exit_slippage=.001)['NetReturn'],baseline['NetReturn'])
 def test_forced_exit_outcome_follows_net_return_and_costs(self):
  def run(close,fees=0.):
   p=IntradayTradePlan('A.NS',pd.Timestamp('2026-01-05'),'LONG',100,90,110,None,time(9,20),0.,0.,fees);return IntradaySimulator().simulate(self.bars([[pd.Timestamp('2026-01-05 09:15',tz='Asia/Kolkata'),100,100,99,100,1,'A.NS'],[pd.Timestamp('2026-01-05 09:20',tz='Asia/Kolkata'),100,109,99,close,1,'A.NS']]),p)
  self.assertEqual(run(101)['Outcome'],'WIN');self.assertEqual(run(99)['Outcome'],'LOSS');self.assertEqual(run(100)['Outcome'],'FLAT');self.assertEqual(run(100.05,fees=.001)['Outcome'],'LOSS')
 def test_no_trade_results_have_null_execution_and_return_fields(self):
  p=self.plan();frames=[self.bars([[pd.Timestamp('2026-01-05 09:15',tz='Asia/Kolkata'),100,100.5,99.5,100,1,'A.NS']]),self.bars([[pd.Timestamp('2026-01-05 09:15',tz='Asia/Kolkata'),99,101,98,99,1,'A.NS']])]
  for frame in frames:
   result=IntradaySimulator().simulate(frame,p)
   for field in ['EntryFill','ExitFill','GrossReturn','NetReturn']:self.assertIsNone(result[field])
 def test_returns_use_project_percentage_points_and_decimal_costs(self):
  cases=[('LONG',100,90,110,[100,101,99,101]),('SHORT',100,110,90,[100,101,99,99])]
  for side,trigger,stop,target,bar in cases:
   with self.subTest(side=side):
    p=IntradayTradePlan('A.NS',pd.Timestamp('2026-01-05'),side,trigger,stop,target,None,time(9,20));rows=[[pd.Timestamp('2026-01-05 09:15',tz='Asia/Kolkata'),100,100,99,100,1,'A.NS'],[pd.Timestamp('2026-01-05 09:20',tz='Asia/Kolkata'),*bar,1,'A.NS']];r=IntradaySimulator().simulate(self.bars(rows),p);self.assertAlmostEqual(r['GrossReturn'],1.0,places=12);self.assertAlmostEqual(r['NetReturn'],1.0,places=12)
    with_fee=IntradayTradePlan('A.NS',pd.Timestamp('2026-01-05'),side,trigger,stop,target,None,time(9,20),0.,0.,.001);r=IntradaySimulator().simulate(self.bars(rows),with_fee);self.assertAlmostEqual(r['NetReturn'],.9,places=12)
