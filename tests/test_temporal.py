"""Path-sensitive diagnostics on known synthetic equity; no strategy simulations."""
import json
import math
import unittest

import numpy as np
import pandas as pd

from reporting.temporal import analyze_temporal


def path(values,dates=None):
    return pd.Series(values,index=pd.to_datetime(dates) if dates else pd.date_range('2024-01-01',periods=len(values),freq='B'))


class TemporalTests(unittest.TestCase):
    def test_same_endpoints_distinct_paths_and_drawdowns(self):
        smooth,_=analyze_temporal(path([100.,110.,120.]),initial_capital=100)
        volatile,_=analyze_temporal(path([100.,60.,120.]),initial_capital=100)
        self.assertEqual(smooth['total_return'],volatile['total_return'])
        self.assertEqual(smooth['last_date'],volatile['last_date'])
        self.assertEqual(smooth['max_drawdown'],0)
        self.assertAlmostEqual(volatile['max_drawdown'],-.4)
        self.assertIsNone(smooth['worst_drawdown_episode'])
        self.assertIsNotNone(volatile['worst_drawdown_episode'])

    def test_initial_loss_includes_anchor_and_exact_recovery(self):
        s,t=analyze_temporal(path([100.,90.,100.]),initial_capital=100)
        self.assertAlmostEqual(t.drawdown.iloc[1],-.1)
        e=s['worst_drawdown_episode']
        self.assertEqual(e['peak_date'],t.index[0].isoformat())
        self.assertEqual(e['trough_date'],t.index[1].isoformat())
        self.assertEqual(e['recovery_date'],t.index[2].isoformat())
        self.assertEqual(e['duration_sessions'],2)
        self.assertEqual(e['underwater_sessions'],1)
        self.assertFalse(e['right_censored'])

    def test_flat_path_has_zero_drawdown_undefined_sharpe_and_no_episode(self):
        s,t=analyze_temporal(path([100.]*300),initial_capital=100)
        self.assertEqual(s['max_drawdown'],0)
        self.assertIsNone(s['longest_underwater_episode'])
        self.assertEqual(s['longest_underwater_duration_sessions'],0)
        self.assertEqual(s['historical_daily_es95']['tail_mean_return'],0)
        self.assertTrue(t.sharpe_63.isna().all())
        self.assertTrue(t.sharpe_252.isna().all())
        self.assertEqual(s['rolling_returns']['252']['valid_windows'],48)
        self.assertEqual(s['rolling_sharpe']['252']['valid_windows'],0)

    def test_unrecovered_is_censored_at_last_observation(self):
        s,t=analyze_temporal(path([100.,95.,80.,90.],['2024-01-05','2024-01-08','2024-01-09','2024-01-10']),initial_capital=100)
        e=s['worst_drawdown_episode']
        self.assertIsNone(e['recovery_date'])
        self.assertTrue(e['right_censored'])
        self.assertEqual(e['duration_sessions'],3)
        self.assertEqual(e['duration_calendar_days'],5)
        self.assertEqual(e['underwater_sessions'],3)

    def test_deepest_episode_differs_from_longest(self):
        s,_=analyze_temporal(path([100.,50.,100.,99.,98.,97.,99.,100.]),initial_capital=100)
        self.assertEqual(s['worst_drawdown_episode']['duration_sessions'],2)
        self.assertEqual(s['longest_underwater_episode']['duration_sessions'],5)
        self.assertAlmostEqual(s['worst_drawdown_episode']['drawdown'],-.5)
        self.assertAlmostEqual(s['longest_underwater_episode']['drawdown'],-.03)

    def test_latest_equal_peak_precedes_episode(self):
        s,t=analyze_temporal(path([100.,100.,90.,100.]),initial_capital=100)
        self.assertEqual(s['worst_drawdown_episode']['peak_date'],t.index[1].isoformat())
        self.assertEqual(s['worst_drawdown_episode']['duration_sessions'],2)

    def test_full_rolling_coverage_and_no_annualization(self):
        e=path(np.arange(100.,400.))
        s,t=analyze_temporal(e,initial_capital=100)
        for w in (21,63,126,252):
            self.assertTrue(t[f'return_{w}'].iloc[:w].isna().all())
            self.assertAlmostEqual(t[f'return_{w}'].iloc[w],e.iloc[w]/e.iloc[0]-1)
            self.assertEqual(s['rolling_returns'][str(w)]['valid_windows'],len(e)-w)
            self.assertAlmostEqual(s['rolling_returns'][str(w)]['minimum_return'],t[f'return_{w}'].min())
        self.assertAlmostEqual(t.return_21.iloc[21],.21)

    def test_rolling_sharpe_matches_explicit_sample_calculation(self):
        daily=np.array([.01,-.02,.005,.003,-.004]*60)
        e=path(np.r_[100.,100*np.cumprod(1+daily)])
        _,t=analyze_temporal(e,initial_capital=100)
        for w in (63,252):
            self.assertTrue(t[f'sharpe_{w}'].iloc[:w].isna().all())
            expected=np.mean(daily[:w])/np.std(daily[:w],ddof=1)*math.sqrt(252)
            self.assertAlmostEqual(t[f'sharpe_{w}'].iloc[w],expected)

    def test_future_changes_cannot_change_past_descriptive_windows(self):
        e=path(np.r_[100.,100*np.cumprod(1+np.sin(np.arange(400))*.01)])
        _,before=analyze_temporal(e,initial_capital=100)
        altered=e.copy();altered.iloc[300:]*=.5
        _,after=analyze_temporal(altered,initial_capital=100)
        pd.testing.assert_frame_equal(before.iloc[:300],after.iloc[:300])

    def test_worst_windows_include_initial_interval_and_exact_endpoints(self):
        e=path([100.,50.,100.,101.,102.,103.,104.])
        s,_=analyze_temporal(e,initial_capital=100)
        self.assertEqual(s['worst_returns']['1']['return'],-.5)
        self.assertEqual(s['worst_returns']['1']['start_date'],e.index[0].isoformat())
        self.assertAlmostEqual(s['worst_returns']['5']['return'],.03)
        self.assertIsNone(s['worst_returns']['21']['return'])
        self.assertEqual(s['worst_returns']['21']['valid_windows'],0)

    def test_ES95_exact_ceil_tail_and_small_sample_qualification(self):
        returns=np.array([-.1,-.05]+[.01]*19)
        e=path(np.r_[100.,100*np.cumprod(1+returns)])
        s,_=analyze_temporal(e,initial_capital=100)
        es=s['historical_daily_es95']
        self.assertEqual(es['tail_count'],2)
        self.assertAlmostEqual(es['actual_tail_fraction'],2/21)
        self.assertAlmostEqual(es['tail_mean_return'],-.075)
        self.assertAlmostEqual(es['loss_magnitude'],.075)
        self.assertTrue(es['small_sample'])
        self.assertFalse(es['future_loss_bound'])
        self.assertFalse(es['independence_assumed'])

    def test_ES_profitable_tail_is_not_clipped_and_summary_JSON_safe(self):
        s,_=analyze_temporal(path([100.,110.]),initial_capital=100)
        self.assertAlmostEqual(s['historical_daily_es95']['loss_magnitude'],-.1)
        self.assertIsNone(s['rolling_returns']['21']['last_return'])
        json.dumps(s,allow_nan=False)

    def test_invalid_anchor_dates_values_and_boolean_inputs_reject(self):
        valid=path([100.,101.,102.])
        bads=[valid.iloc[::-1],pd.Series([100.,101.],index=pd.to_datetime(['2024-01-01','2024-01-01'])),
              pd.Series([100.,101.],index=pd.to_datetime(['2024-01-01',None])),
              pd.Series([100.,101.]),path([100.]),path([100.,0.]),path([100.,-1.]),
              path([100.,float('nan')]),path([100.,float('inf')]),path([True,False]),
              path(['100','101']),path([100+1j,101+1j])]
        for e in bads:
            with self.assertRaises(ValueError):analyze_temporal(e,initial_capital=100)
        for anchor in (0,-1,float('nan'),float('inf'),True,101):
            with self.assertRaises(ValueError):analyze_temporal(valid,initial_capital=anchor)

    def test_extreme_finite_values_do_not_emit_infinite_JSON(self):
        with self.assertRaisesRegex(ValueError,'finite numerical'):
            analyze_temporal(path([1e-300,1e300]),initial_capital=1e-300)

    def test_input_not_mutated(self):
        e=path([100.,90.,110.]);original=e.copy(deep=True)
        analyze_temporal(e,initial_capital=100)
        pd.testing.assert_series_equal(e,original)


if __name__=='__main__':unittest.main()
