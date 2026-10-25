"""Fresh independent edge cases; synthetic equity only, no strategy simulations."""
import json
import math
import unittest

import numpy as np
import pandas as pd

from reporting.temporal import analyze_temporal


def anchored(values, dates=None):
    return pd.Series(values, index=pd.to_datetime(dates) if dates is not None else pd.bdate_range('2021-01-01', periods=len(values)))


class TemporalAdversarialTests(unittest.TestCase):
    def test_geometric_constant_nonzero_return_has_undefined_sharpe(self):
        for rate in (.001, .01, .125):
            equity = anchored(100 * np.power(1 + rate, np.arange(301)))
            summary, table = analyze_temporal(equity, initial_capital=100)
            for window in (63, 252):
                self.assertTrue(table[f'sharpe_{window}'].isna().all(), (rate, window))
                self.assertEqual(summary['rolling_sharpe'][str(window)]['valid_windows'], 0)
                self.assertIsNone(summary['rolling_sharpe'][str(window)]['last_sharpe'])

    def test_small_real_variance_is_not_erased_as_constant(self):
        returns = .001 + np.tile([1e-8, -1e-8, 2e-8, -2e-8], 80)
        equity = anchored(np.r_[100., 100 * np.cumprod(1 + returns)])
        summary, table = analyze_temporal(equity, initial_capital=100)
        observed = equity.pct_change().iloc[1:64].to_numpy()
        expected = observed.mean() / observed.std(ddof=1) * math.sqrt(252)
        self.assertAlmostEqual(table.sharpe_63.iloc[63] / expected, 1., places=9)
        self.assertGreater(summary['rolling_sharpe']['63']['valid_windows'], 0)

    def test_latest_plateau_peak_and_censored_longest_are_separate_from_deepest(self):
        equity = anchored([100., 50., 100., 100., 99., 98., 97., 99.])
        summary, _ = analyze_temporal(equity, initial_capital=100)
        deepest = summary['worst_drawdown_episode']
        longest = summary['longest_underwater_episode']
        self.assertEqual(len(summary['drawdown_episodes']), 2)
        self.assertAlmostEqual(deepest['drawdown'], -.5)
        self.assertEqual(deepest['duration_sessions'], 2)
        self.assertFalse(deepest['right_censored'])
        self.assertEqual(longest['peak_date'], equity.index[3].isoformat())
        self.assertAlmostEqual(longest['drawdown'], -.03)
        self.assertEqual(longest['duration_sessions'], 4)
        self.assertEqual(longest['underwater_sessions'], 4)
        self.assertIsNone(longest['recovery_date'])
        self.assertEqual(longest['observed_end_date'], equity.index[-1].isoformat())
        self.assertTrue(summary['longest_underwater_right_censored'])

    def test_longest_duration_ties_use_calendar_days(self):
        dates = ['2021-01-01', '2021-01-02', '2021-01-03', '2021-01-10', '2021-01-20', '2021-02-20']
        equity = anchored([100., 90., 100., 100., 99., 100.], dates)
        summary, _ = analyze_temporal(equity, initial_capital=100)
        longest = summary['longest_underwater_episode']
        self.assertEqual(longest['peak_date'], pd.Timestamp('2021-01-10').isoformat())
        self.assertEqual(longest['duration_sessions'], 2)
        self.assertEqual(longest['underwater_sessions'], 1)
        self.assertEqual(longest['duration_calendar_days'], 41)
        self.assertFalse(longest['right_censored'])

    def test_empirical_tail_ties_do_not_expand_count_and_sign_not_clipped(self):
        returns = np.r_[np.repeat(-.1, 4), np.repeat(.01, 37)]
        equity = anchored(np.r_[100., 100 * np.cumprod(1 + returns)])
        summary, _ = analyze_temporal(equity, initial_capital=100)
        tail = summary['historical_daily_es95']
        self.assertEqual(tail['sample_count'], 41)
        self.assertEqual(tail['tail_count'], 3)
        self.assertEqual(tail['actual_tail_fraction'], 3 / 41)
        self.assertAlmostEqual(tail['tail_mean_return'], -.1)
        self.assertAlmostEqual(tail['loss_magnitude'], .1)
        self.assertAlmostEqual(tail['threshold_return'], -.1)
        positive = anchored(np.r_[100., 100 * np.cumprod(1 + np.r_[.01, .02, np.repeat(.03, 19)])])
        result, _ = analyze_temporal(positive, initial_capital=100)
        self.assertEqual(result['historical_daily_es95']['tail_count'], 2)
        self.assertAlmostEqual(result['historical_daily_es95']['loss_magnitude'], -.015)
        self.assertFalse(result['historical_daily_es95']['future_loss_bound'])
        json.dumps(result, allow_nan=False)

    def test_observed_intervals_are_not_calendar_months_or_completed_market_sessions(self):
        dates = pd.date_range('2021-01-01', periods=23, freq='7D')
        equity = anchored(100 + np.arange(23), dates)
        summary, table = analyze_temporal(equity, initial_capital=100)
        self.assertAlmostEqual(table.return_21.iloc[21], .21)
        self.assertEqual(summary['rolling_returns']['21']['valid_windows'], 2)
        self.assertEqual((dates[21] - dates[0]).days, 147)
        self.assertIn('observed intervals', summary['coverage_note'])
        self.assertIn('caller-verified', summary['coverage_note'])
        self.assertIsNone(summary['rolling_returns']['63']['last_return'])

    def test_peak_equality_ends_episode_without_extra_underwater_session(self):
        equity = anchored([100., 99., 100., 100., 100., 98., 100., 100.])
        summary, _ = analyze_temporal(equity, initial_capital=100)
        episodes = summary['drawdown_episodes']
        self.assertEqual([e['duration_sessions'] for e in episodes], [2, 2])
        self.assertEqual([e['underwater_sessions'] for e in episodes], [1, 1])
        self.assertEqual(episodes[1]['peak_date'], equity.index[4].isoformat())
        self.assertEqual(episodes[1]['recovery_date'], equity.index[6].isoformat())
        self.assertTrue(all(not e['right_censored'] for e in episodes))


if __name__ == '__main__':
    unittest.main()
