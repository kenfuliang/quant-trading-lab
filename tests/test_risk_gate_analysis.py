import unittest
import numpy as np
import pandas as pd
from research.risk_gate_analysis import events, independent_temporal
from reporting.temporal import analyze_temporal

class AnalysisTests(unittest.TestCase):
    def test_independent_temporal(self):
        p=100*np.cumprod(np.r_[1,1+np.sin(np.arange(400))*.01])
        eq=pd.Series(p,index=pd.bdate_range('2000-01-01',periods=len(p)))
        s,t=analyze_temporal(eq,initial_capital=100)
        self.assertTrue(independent_temporal(eq,s,t)['passed'])
        bad=t.copy(); bad.iloc[100,bad.columns.get_loc('return_21')]+=.01
        with self.assertRaises(AssertionError): independent_temporal(eq,s,bad)
    def test_event_boundary_censor_action_and_overnight(self):
        n=30; index=pd.Index(pd.bdate_range('2020-01-01',periods=n).strftime('%Y-%m-%d'))
        time=pd.DataFrame(dict(state=['yellow']*2+['green']+['red']*3+['yellow']*2+['green']*20+['red']*2),index=index)
        frame=pd.DataFrame(dict(open=100.,close=100.,base_target=1.,intended_target=1.),index=index)
        frame.loc[index[3:6],'intended_target']=0
        frame.loc[index[23],'close']=95  # start3 plus20: included exactly
        account=pd.DataFrame(dict(equity_usd=np.arange(n)+100.,shares=1,close=100.,commission_usd=0,slippage_usd=0),index=index)
        r=events(time,frame,account,account,account,100)
        self.assertEqual(r['summary']['left_censored'],1)
        self.assertEqual(r['summary']['evaluable_warning_episodes'],1)
        self.assertEqual(r['summary']['warnings_with_drop'],1)
        self.assertTrue(r['warnings'][-1]['warning_right_censored'])
        first=r['red_windows'][0]
        self.assertAlmostEqual(first['gate_return'],107/102-1)
        self.assertEqual(first['event'],'red_entry')
        frame.loc[index[23],'close']=100; frame.loc[index[24],'close']=90
        r=events(time,frame,account,account,account,100)
        self.assertEqual(r['summary']['warnings_with_drop'],0)

if __name__=='__main__': unittest.main()
