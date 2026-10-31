import unittest
import pandas as pd
from research.legacy_control_contract import compare_ema_diagnostic


class LegacyControlContractTests(unittest.TestCase):
    def fixture(self):
        index=pd.Index(['2020-01-02','2020-01-03'],name='date')
        a=pd.DataFrame(dict(equity_usd=[100.,101.],shares=[0,1],effective_target_leverage=[0.,1.]),index=index)
        b=a.copy();b['effective_target_leverage']=1.
        f=pd.DataFrame(dict(want_long=[False,True],intended_target=[0.,1.]),index=index)
        trades=pd.DataFrame(dict(date=['2020-01-03'],delta=[1],fill_price=[100.]))
        return a,b,trades,f

    def test_known_semantics_only(self):
        a,b,t,f=self.fixture();r=compare_ema_diagnostic(a,b,t,t,f)
        self.assertTrue(r['passed']);self.assertFalse(r['frozen_gate_overridden']);self.assertEqual(r['mismatch_sessions'],1)
        a.iloc[0,a.columns.get_loc('effective_target_leverage')]=.5
        with self.assertRaises(ValueError):compare_ema_diagnostic(a,b,t,t,f)

    def test_no_financial_or_trade_drift_hidden(self):
        a,b,t,f=self.fixture();b.iloc[0,b.columns.get_loc('equity_usd')]+=.01
        with self.assertRaises(AssertionError):compare_ema_diagnostic(a,b,t,t,f)
        a,b,t,f=self.fixture();other=t.copy();other['delta']=2
        with self.assertRaises(AssertionError):compare_ema_diagnostic(a,b,t,other,f)
