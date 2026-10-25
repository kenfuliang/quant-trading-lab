import unittest
import numpy as np
import pandas as pd
from reporting.risk_gate_review import verify_temporal_details,paired_verdict
from reporting.temporal import analyze_temporal
class ReviewTests(unittest.TestCase):
 def test_episode_reference_and_tampering(self):
  e=pd.Series([100,100,90,95,100,101,99,80],index=pd.bdate_range('2000-01-01',periods=8),dtype=float)
  s,_=analyze_temporal(e,initial_capital=100)
  self.assertTrue(verify_temporal_details(e,s)['passed'])
  s['drawdown_episodes'][-1]['right_censored']=False
  with self.assertRaises(AssertionError):verify_temporal_details(e,s)
 def test_depth_only_improvement_fails_and_growth_is_separate(self):
  b=dict(drawdown_pct=-30,longest_underwater_sessions=500,cagr_pct=8,ending_equity_usd=200,longest_censored=False)
  g=dict(b,drawdown_pct=-20,longest_underwater_sessions=501,cagr_pct=9)
  self.assertFalse(paired_verdict(g,b)['path_criterion_pass'])
  g.update(longest_underwater_sessions=500,cagr_pct=6)
  self.assertTrue(paired_verdict(g,b)['path_criterion_pass'])
  self.assertEqual(paired_verdict(g,b)['cagr_change_pp'],-2)
