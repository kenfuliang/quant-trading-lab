import unittest
import pandas as pd
from research.evaluation.control_parity import compare

class ControlParityTests(unittest.TestCase):
    def setUp(self):
        self.old=pd.DataFrame(dict(cash=[10.,11.],shares=[1,1],equity_usd=[100.,101.]),index=['a','b'])
        self.new=self.old.assign(effective_target_leverage=1.)
        self.trades=pd.DataFrame(dict(delta=[1],fill_price=[90.]))
    def test_documented_diagnostic(self):
        self.assertTrue(compare(self.old,self.new,self.trades,self.trades)['passed'])
    def test_values_not_hidden(self):
        for new in (self.new.assign(cash=[10.,12.]),self.new.assign(effective_target_leverage=.5),
                    self.new.assign(unexpected=1),self.new.iloc[:-1]):
            with self.assertRaises(AssertionError): compare(self.old,new,self.trades,self.trades)
        with self.assertRaises(AssertionError): compare(self.old,self.new,self.trades,self.trades.assign(delta=2))
