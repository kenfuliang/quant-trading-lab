import unittest
import numpy as np
import pandas as pd
from reporting.temporal import analyze_temporal

class FlatWindowTests(unittest.TestCase):
    def test_flat_cash_after_volatile_history_is_undefined(self):
        changes=np.r_[np.sin(np.arange(100))*.03,np.zeros(300)]
        eq=pd.Series(100*np.cumprod(np.r_[1,1+changes]),index=pd.bdate_range('2000-01-01',periods=401))
        summary,table=analyze_temporal(eq,initial_capital=100)
        self.assertEqual(summary['method_version'],'temporal-v1.2')
        self.assertTrue(table.sharpe_63.iloc[163:].isna().all())
        self.assertTrue(table.sharpe_252.iloc[352:].isna().all())
        self.assertTrue(np.isfinite(table.sharpe_63.iloc[100]))
