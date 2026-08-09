"""Focused frozen-rule tests for the independent Bearish Engulfing path."""
from __future__ import annotations
import unittest
import pandas as pd
from patterns.bearish_engulfing import BearishEngulfingDetector
from analysis.bearish_uptrend import UptrendEvaluator
from analysis.bearish_confirmation import BearishConfirmationEvaluator
from analysis.bearish_trade_setup import BearishTradeSetupEvaluator
from analysis.bearish_trade_simulation import BearishTradeSimulator
from analysis.bearish_performance import BearishTradePerformanceEvaluator
from data.providers.base_provider import CANONICAL_OHLCV_COLUMNS

def _data() -> pd.DataFrame:
    """Return one strict-pattern data set with a four-of-four prior uptrend."""
    rows=[]
    for day,(o,h,l,c) in enumerate([(10,11,9,10.5),(11,12,10,11.5),(12,13,11,12.5),(13,14,12,13.5),(14,15,13,14.5),(15,16,14,15.5),(16,17,13,14),(13,14,10,12),(12,13,9,11),(11,12,8,10),(10,11,7,9),(9,10,6,8),(8,9,5,7)]):
        rows.append((pd.Timestamp("2026-01-01")+pd.Timedelta(days=day),o,h,l,c,c,100,"TEST.NS"))
    return pd.DataFrame(rows,columns=CANONICAL_OHLCV_COLUMNS)

class BearishEngulfingTests(unittest.TestCase):
    """Exercise strict pattern through performance without provider calls."""
    def test_strict_pattern_and_pipeline_fields(self)->None:
        """Detect strict bearish body, confirm, size, simulate, and measure it."""
        source=_data(); patterns=BearishEngulfingDetector().detect(source)
        self.assertEqual(len(patterns),1); self.assertEqual(patterns.iloc[0].PatternName,"Bearish Engulfing")
        uptrend=UptrendEvaluator().evaluate(source,patterns);self.assertTrue(uptrend.iloc[0].UptrendPassed);self.assertEqual(uptrend.iloc[0].UptrendScore,4)
        confirmed=BearishConfirmationEvaluator().evaluate(source,uptrend);self.assertTrue(confirmed.iloc[0].ConfirmationPassed)
        setup=BearishTradeSetupEvaluator().evaluate(source,confirmed); self.assertAlmostEqual(setup.iloc[0].EntryFill,11.988); self.assertAlmostEqual(setup.iloc[0].StopPrice,17); self.assertAlmostEqual(setup.iloc[0].TargetPrice,1.964)
        source.loc[9, "High"] = 18
        original=source.copy(deep=True)
        simulated=BearishTradeSimulator().simulate(source,setup);self.assertEqual(simulated.iloc[0].Outcome,"LOSS");self.assertAlmostEqual(simulated.iloc[0].ExitFill,17.016999999999996)
        performance=BearishTradePerformanceEvaluator().evaluate(source,simulated);self.assertAlmostEqual(performance.iloc[0].MFE,2.988);self.assertAlmostEqual(performance.iloc[0].MAE,1.012)
        pd.testing.assert_frame_equal(source,original)
    def test_equality_and_wick_only_do_not_qualify(self)->None:
        """Reject non-strict body boundaries and wick-only setups."""
        source=_data();source.loc[6,"Open"]=15.5;self.assertTrue(BearishEngulfingDetector().detect(source).empty)
    def test_uptrend_two_of_four_rejects(self)->None:
        """Require at least three strict comparisons."""
        source=_data();source.loc[2,["High","Low"]]=[15,14];source.loc[4,["High","Low"]]=[12,11];patterns=BearishEngulfingDetector().detect(source);result=UptrendEvaluator().evaluate(source,patterns);self.assertFalse(result.iloc[0].UptrendPassed);self.assertLess(result.iloc[0].UptrendScore,3)
    def test_same_bar_is_conservative_stop(self)->None:
        """Classify simultaneous target/stop contact as a short loss."""
        source=_data();patterns=BearishEngulfingDetector().detect(source);setup=BearishTradeSetupEvaluator().evaluate(source,BearishConfirmationEvaluator().evaluate(source,UptrendEvaluator().evaluate(source,patterns)));source.loc[8,["High","Low"]]=[18,0];sim=BearishTradeSimulator().simulate(source,setup);self.assertEqual(sim.iloc[0].ExitReason,"STOP");self.assertEqual(sim.iloc[0].Outcome,"LOSS")
