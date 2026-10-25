import unittest
import numpy as np
import pandas as pd
from research.feature_engineering import build_features,future_risk,fit_edges,assign_bins,mature_within,rank_association


def prices(n=280):
    c=100*np.exp(np.cumsum(.001+.01*np.sin(np.arange(n)*.41)))
    return pd.DataFrame(dict(open=c,high=c*1.02,low=c*.98,close=c),index=pd.bdate_range('2010-01-01',periods=n))


class FeatureEngineeringTests(unittest.TestCase):
    def test_future_perturbation_and_prefix_are_causal(self):
        raw=prices();f=build_features(raw)
        for k in [100,220,260]:
            pd.testing.assert_frame_equal(f.iloc[:k],build_features(raw.iloc[:k]))
        changed=raw.copy();changed.iloc[220:]*=3
        # Bar220 itself is not yet known at its open.
        pd.testing.assert_frame_equal(f.iloc[:221],build_features(changed).iloc[:221])

    def test_independent_formula_and_exact_one_lag(self):
        raw=prices();f=build_features(raw);i=240
        c=raw.close.to_numpy();returns=c[1:]/c[:-1]-1
        expected=np.std(returns[i-20-1:i-1],ddof=1)/np.std(returns[i-60-1:i-1],ddof=1)
        self.assertAlmostEqual(f.vol_ratio20_60.iloc[i],expected)
        self.assertAlmostEqual(f.range20_pct.iloc[i],.04)
        self.assertEqual(f.observed_close.iloc[i],raw.index[i-1])
        self.assertTrue(pd.isna(f.ema_gap_pct.iloc[199]));self.assertTrue(pd.notna(f.ema_gap_pct.iloc[200]))

    def test_zero_volatility_and_warmup_not_confident_zeros(self):
        raw=prices();raw[:]=100;f=build_features(raw)
        self.assertTrue(f.vol_ratio20_60.isna().all())
        self.assertTrue(f.ema_positive.iloc[:200].isna().all())
        self.assertEqual(f.sigma20.iloc[-1],0.)
        self.assertIsNone(fit_edges(f.range20_pct.iloc[200:]))

    def test_bad_prices_rejected_without_repair(self):
        for kind in ['nan','negative','envelope','duplicate']:
            raw=prices()
            if kind=='nan':raw.iloc[5,0]=np.nan
            elif kind=='negative':raw.iloc[5,0]=-1
            elif kind=='envelope':raw.iloc[5,1]=1
            else:raw.index=pd.DatetimeIndex([raw.index[0],*raw.index[:-1]])
            with self.assertRaises(ValueError):build_features(raw)

    def test_future_risk_includes_first_gap_and_censors_tail(self):
        raw=prices();risk=future_risk(raw);i=230
        r=raw.close.iloc[i:i+21].to_numpy()/raw.close.iloc[i-1:i+20].to_numpy()-1
        self.assertAlmostEqual(risk.iloc[i],np.std(r,ddof=1)*np.sqrt(252))
        self.assertTrue(risk.iloc[-20:].isna().all())

    def test_calibration_edges_not_refitted_to_later_values(self):
        x=pd.Series(np.arange(12.));edges=fit_edges(x.iloc[:6]);a=assign_bins(x,edges)
        y=x.copy();y.iloc[6:]*=1000
        self.assertEqual(edges,fit_edges(y.iloc[:6]));pd.testing.assert_series_equal(a.iloc[:6],assign_bins(y,edges).iloc[:6])

    def test_maturity_crossing_boundary_is_excluded(self):
        f=pd.DataFrame(dict(label_available_after_close=pd.to_datetime(['2011-12-30','2012-01-04',None]),right_censored=[False,False,True]),index=pd.to_datetime(['2011-12-01','2011-12-20','2011-12-21']))
        self.assertEqual(len(mature_within(f,'2011-01-01','2011-12-31')),1)

    def test_constant_and_missing_association_has_reason(self):
        a=rank_association(pd.Series([1.,1.,1.]),pd.Series([1.,2.,3.]))
        self.assertIsNone(a['spearman']);self.assertEqual(a['undefined_reason'],'constant_input')
        a=rank_association(pd.Series([1.,np.nan]),pd.Series([1.,2.]))
        self.assertEqual(a['n'],1);self.assertIsNone(a['spearman'])
