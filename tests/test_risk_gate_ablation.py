import unittest
import numpy as np
import pandas as pd
from research.risk_gate_ablation import frames,CASES
from research.risk_gate import states
class AblationTests(unittest.TestCase):
 def test_four_cases_and_only_price_component_removed(self):
  self.assertEqual(len(CASES),4)
  p=np.r_[np.linspace(100,150,250),np.linspace(150,90,40),np.linspace(90,110,80)]
  raw=pd.DataFrame(dict(open=p,low=p-1,high=p+1,close=p),index=pd.bdate_range('2000-01-01',periods=len(p)))
  data,t=frames(raw)
  expected=states(t[['fast','slow','vol','dd']].assign(dd=0))
  self.assertTrue(t.state.equals(expected.state))
  self.assertTrue((data['gate_ema'].intended_target<=data['ema'].intended_target).all())
  changed=raw.copy();changed.iloc[300:]*=.5;_,u=frames(changed)
  pd.testing.assert_frame_equal(t.iloc[:301],u.iloc[:301])
  self.assertTrue(t.dd.dropna().lt(-.2).any())
  self.assertTrue(t.price_peak_component_enabled.eq(False).all())
