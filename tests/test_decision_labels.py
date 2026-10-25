import unittest
import numpy as np
import pandas as pd
from reporting.decision_labels import decision_log, outcome_labels, summarize, label_outcome


def fixture():
    dates = pd.bdate_range('2020-01-01', periods=34)
    raw = pd.Series(np.arange(100., 134.), index=dates)
    idx = dates[26:]
    state = ['green', 'yellow', 'red', 'red', 'yellow', 'green', 'yellow', 'green']
    bt = np.array([1., 0., 0., 1., 1., 1., 1., 1.])
    cap = np.array([1., .5, 0., 0., .5, 1., .5, 1.])
    gt = np.minimum(bt, cap)
    signal = pd.DataFrame(dict(close=raw.loc[idx], base_target=bt, intended_target=gt), index=idx)
    timeline = signal[['base_target', 'intended_target']].copy()
    timeline['state'] = state; timeline['cap'] = cap
    timeline['observed_close'] = dates[25:-1].strftime('%Y-%m-%d')
    timeline['execution_open'] = idx.strftime('%Y-%m-%d')
    for col, value in [('fast', 2.), ('slow', 1.), ('vol', .3), ('dd', -.1), ('red_count', 0), ('green_count', 0)]:
        timeline[col] = value
    def account(shares):
        return pd.DataFrame(dict(close=raw.loc[idx], shares=shares, cash=1000.,
                                 equity_usd=1000.+shares*raw.loc[idx]), index=idx)
    return timeline, signal, account((gt>0).astype(int)), account(bt.astype(int)), raw


class DecisionLabelTests(unittest.TestCase):
    def log(self, values=None):
        return decision_log(*(values or fixture()), 1000., 'toy', peak_enabled=False)

    def test_cash_warning_distinguishes_exit_and_no_immediate_credit(self):
        d = self.log()
        self.assertTrue(d.warning_base_exiting.iloc[1])
        self.assertFalse(d.warning_already_cash.iloc[1])
        self.assertTrue(d.warning_already_cash.iloc[2])
        self.assertFalse(d.intended_reduction.iloc[2])
        self.assertEqual(label_outcome(-.2, -.1, actionable=False, already_cash=True, prior_return=-.1),
                         'warning_already_cash_no_immediate_credit')

    def test_decision_inputs_are_unchanged_by_valid_future_account_changes(self):
        original = fixture(); d = self.log(original)
        changed = tuple(x.copy() for x in original)
        for account in changed[2:4]:
            account.iloc[5:, account.columns.get_loc('cash')] += 500
            account['equity_usd'] = account.cash + account.shares*account.close
        other = self.log(changed)
        pd.testing.assert_frame_equal(d.iloc[:6], other.iloc[:6])
        self.assertNotIn('gate_return', d)
        self.assertNotIn('label', d)
        self.assertNotIn('close', d)

    def test_noncausal_or_missing_or_unsorted_dates_rejected(self):
        values = list(fixture()); values[0].iloc[2, values[0].columns.get_loc('observed_close')] = str(values[0].index[2].date())
        with self.assertRaises(ValueError): self.log(tuple(values))
        values = list(fixture()); values[2] = values[2].iloc[::-1]
        with self.assertRaises(ValueError): self.log(tuple(values))
        values = list(fixture()); values[3].iloc[0, values[3].columns.get_loc('equity_usd')] = np.nan
        with self.assertRaises(ValueError): self.log(tuple(values))

    def test_same_day_gap_included_and_each_path_has_own_anchor(self):
        d = self.log().iloc[:3].copy()
        x = outcome_labels(d, [90., 99., 108.9], [80., 88., 96.8], 100., horizons=(1, 2))
        first = x[(x.execution_session==d.execution_session.iloc[0]) & (x.horizon_sessions==1)].iloc[0]
        self.assertAlmostEqual(first.gate_return, -.1)
        self.assertAlmostEqual(first.base_return, -.2)
        second = x[(x.execution_session==d.execution_session.iloc[1]) & (x.horizon_sessions==2)].iloc[0]
        self.assertAlmostEqual(second.gate_return, .21)
        self.assertAlmostEqual(second.base_return, .21)

    def test_rebound_requires_prior_decline_and_positive_base_move(self):
        kw=dict(actionable=True, already_cash=False)
        self.assertEqual(label_outcome(.1, .02, prior_return=-.1, **kw), 'missed_rebound')
        self.assertEqual(label_outcome(.1, .02, prior_return=.1, **kw), 'missed_positive_base_move')
        self.assertEqual(label_outcome(-.1, -.02, prior_return=-.1, **kw), 'helped_during_base_loss')
        self.assertEqual(label_outcome(-.02, -.1, prior_return=-.1, **kw), 'worsened_base_loss')
        self.assertEqual(label_outcome(.1, .15, prior_return=-.1, **kw), 'outperformed_positive_base')

    def test_censored_horizons_stay_null_and_maturity_is_end_close(self):
        d=self.log(); x=outcome_labels(d, np.arange(100.,108.), np.arange(100.,108.), 100., horizons=(5,))
        self.assertEqual(int(x.right_censored.sum()), 4)
        self.assertTrue(x.loc[x.right_censored, ['gate_return','base_return','label_available_after_close']].isna().all().all())
        self.assertEqual(x.label_available_after_close.iloc[0], d.execution_session.iloc[4])
        self.assertTrue(x.loc[x.right_censored,'label'].eq('right_censored').all())

    def test_episode_counts_and_overlap_not_daily_independence(self):
        d=self.log(); x=outcome_labels(d, np.arange(100.,108.), np.arange(100.,108.), 100., horizons=(5,))
        daily, rows, _=summarize(d,x)
        r=next(r for r in rows if r['event']=='reduction_episode_start')
        self.assertEqual(r['anchors'], 2)
        self.assertEqual(r['evaluable'], 1)
        self.assertEqual(r['right_censored'], 1)
        self.assertEqual(r['adjacent_overlapping_windows'], 1)
        self.assertEqual(daily['warning_already_cash_sessions'], 1)

    def test_invalid_outcomes_and_horizons_rejected(self):
        d=self.log()
        for h in [(0,), (True,), (1,1)]:
            with self.assertRaises(ValueError):outcome_labels(d, [100.]*8, [100.]*8, 100.,h)
        with self.assertRaises(ValueError):outcome_labels(d,[100.]*7,[100.]*8,100.)
