import unittest
import subprocess
import sys
import textwrap
import numpy as np
import pandas as pd
from reporting.risk_gate_review import verify_temporal_details,paired_verdict
from reporting.temporal import analyze_temporal
class ReviewTests(unittest.TestCase):
 def test_optimized_python_rejects_tampered_audit_fields(self):
  program = textwrap.dedent('''
   import pandas as pd
   from reporting.temporal import analyze_temporal
   from reporting.risk_gate_review import verify_temporal_details, verify_events
   eq = pd.Series([100., 90., 100.], index=pd.bdate_range('2000-01-01', periods=3))
   summary, _ = analyze_temporal(eq, initial_capital=100.)
   verify_temporal_details(eq, summary)
   summary['max_drawdown'] = 0.
   dates = pd.bdate_range('2000-01-01', periods=2)
   timeline = pd.DataFrame({'state': ['yellow', 'green']}, index=dates)
   frame = pd.DataFrame({'base_target': [1., 1.], 'intended_target': [.5, 1.]}, index=dates)
   warning = dict(start=dates[0], left_censored=True, end=dates[1], actionable_index=0,
                  warning_price_drop_5pct=None, actionable_price_drop_5pct=None)
   result = dict(warnings=[warning], red_windows=[])
   verify_events(result, timeline, frame, None, None, None, 100.)
   warning['left_censored'] = False
   checks = [lambda: verify_temporal_details(eq, summary),
             lambda: verify_events(result, timeline, frame, None, None, None, 100.)]
   for check in checks:
       try:
           check()
       except AssertionError:
           continue
       raise RuntimeError('Tampered evidence was accepted under optimized Python')
  ''')
  result = subprocess.run([sys.executable, '-O', '-c', program], capture_output=True, text=True)
  self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
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
