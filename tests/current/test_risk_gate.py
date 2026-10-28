import unittest
import numpy as np
import pandas as pd
from research.policies.risk_gate import states, frames, timeline
from research.evaluation.leveraged_spy import simulate, FinancingModel
from research.evaluation.leverage_audit import reconcile

class GateTests(unittest.TestCase):
    def feature(self,n=30):
        return pd.DataFrame(dict(fast=np.ones(n)*101,slow=np.ones(n)*100,vol=np.ones(n)*.1,dd=np.zeros(n)))
    def test_boundaries_precedence_staging(self):
        f=self.feature(); f.loc[5,'dd']=-.2; f.loc[6,'dd']=-.20001
        s=states(f)
        self.assertEqual(s.state.iloc[3],'yellow'); self.assertEqual(s.state.iloc[4],'green')
        self.assertEqual(s.state.iloc[5],'yellow'); self.assertEqual(s.state.iloc[6],'red')
        self.assertEqual(s.state.iloc[10],'red'); self.assertEqual(s.state.iloc[11],'yellow')
        self.assertEqual(s.green_count.iloc[11],0); self.assertEqual(s.state.iloc[16],'green')
        for column,value,color in [('vol',.4,'red'),('vol',.25,'yellow'),('dd',-.1,'yellow'),('fast',100,'yellow')]:
            f=self.feature(6); f.loc[5,column]=value
            self.assertEqual(states(f).state.iloc[5],color)
    def test_recovery_reset(self):
        f=self.feature(20); f.loc[0,'vol']=.4; f.loc[4,'dd']=-.18
        s=states(f); self.assertEqual(s.red_count.iloc[4],0)
        self.assertEqual(s.state.iloc[8],'red'); self.assertEqual(s.state.iloc[9],'yellow')
        f.loc[12,'vol']=.20; s=states(f)
        self.assertEqual(s.green_count.iloc[12],0); self.assertEqual(s.state.iloc[17],'green')
    def raw(self):
        p=np.linspace(100,160,300); return pd.DataFrame(dict(open=p,high=p+1,low=p-1,close=p),index=pd.bdate_range('2004-01-01',periods=300))
    def test_causality_lag_and_cap(self):
        r=self.raw(); a,t=frames(r); changed=r.copy(); changed.iloc[250:,:]*=.5
        b,u=frames(changed)
        pd.testing.assert_frame_equal(t.iloc[:251],u.iloc[:251])
        for k in a:
            pd.testing.assert_series_equal(a[k].intended_target.iloc[:251],b[k].intended_target.iloc[:251])
        self.assertEqual(t.state.iloc[199],'unassessed'); self.assertEqual(t.state.iloc[200],'yellow')
        self.assertTrue((a['gate_ema'].intended_target<=a['ema'].intended_target).all())
        self.assertTrue(set(a['gate_ema'].allocation_factor.unique())<={0,.5,1})
        self.assertTrue(a['ema'].allocation_factor.eq(1.).all())
        pd.testing.assert_series_equal(a['ema'].want_long.astype(float),a['ema'].intended_target,check_names=False)
    def test_entry_only_and_audit_guards(self):
        r=self.raw().iloc[-10:][['open','low','close']].copy(); r.index=r.index.strftime('%Y-%m-%d')
        r['want_long']=True; r['rebalance_policy']='entry_only'
        dividends={r.index[2]:100.}
        c,t=simulate(r,dividends,'buy_hold',1)
        self.assertEqual(len(t),1); self.assertEqual(c.shares.nunique(),1)
        self.assertGreater(c.cash.iloc[-1],c.cash.iloc[0])
        self.assertTrue(reconcile(r,dividends,c,t,'buy_hold',1,FinancingModel())['passed'])
        for broken in (c.iloc[:-1],c.assign(cash=float('nan'))):
            with self.assertRaises(AssertionError): reconcile(r,dividends,broken,t,'buy_hold',1,FinancingModel())
        with self.assertRaises(ValueError): simulate(r.assign(allocation_factor=.5),dividends,'buy_hold',1)
    def test_forced_exit_preserved(self):
        r=pd.DataFrame(dict(open=[100.,100.],low=[100.,1.],close=[100.,1.],want_long=True,rebalance_policy='entry_only'),index=['2020-01-01','2020-01-02'])
        # A 1x cash-only account cannot violate 25% margin without borrowing;
        # changing margin policy verifies entry-only still executes shared checks.
        m=FinancingModel(initial_margin=1,maintenance=1)
        c,t=simulate(r,{},'buy_hold',1,m)
        self.assertTrue(reconcile(r,{},c,t,'buy_hold',1,m)['passed'])

if __name__=='__main__': unittest.main()
