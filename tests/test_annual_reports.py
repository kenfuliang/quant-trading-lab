import unittest

import numpy as np
import pandas as pd

from reporting.annual import annual_metrics


class AnnualMetricsTests(unittest.TestCase):
    def test_year_boundary_first_loss_and_drawdown_reset(self):
        curve = pd.DataFrame({'equity_usd': [100, 90, 120, 60, 66, 80, 72]},
                             index=pd.to_datetime(['2019-12-31', '2020-01-02', '2020-06-01', '2020-12-31',
                                                   '2021-01-04', '2021-06-01', '2021-12-31']))
        annual = annual_metrics(curve).set_index('year')
        self.assertEqual(list(annual.index), [2020, 2021])
        self.assertAlmostEqual(annual.loc[2020, 'annual_return_pct'], -40)
        self.assertAlmostEqual(annual.loc[2020, 'annual_max_drawdown_pct'], -50)
        self.assertAlmostEqual(annual.loc[2021, 'annual_return_pct'], 20)
        self.assertAlmostEqual(annual.loc[2021, 'annual_max_drawdown_pct'], -10)
        self.assertEqual(annual.loc[2021, 'opening_equity_usd'], 60)
        self.assertAlmostEqual(np.prod(1 + annual.annual_return_pct / 100), 72 / 100)

    def test_same_year_anchor_excluded_and_first_day_loss_counts(self):
        curve = pd.DataFrame({'equity_usd': [100, 90, 95]},
                             index=pd.to_datetime(['2005-01-02', '2005-01-03', '2005-01-04']))
        row = annual_metrics(curve).iloc[0]
        self.assertEqual(row.sessions, 2)
        self.assertAlmostEqual(row.annual_max_drawdown_pct, -10)
        self.assertAlmostEqual(row.annual_return_pct, -5)

    def test_monotonic_year_has_zero_drawdown(self):
        curve = pd.DataFrame({'equity_usd': [100, 110, 120]},
                             index=pd.to_datetime(['2020-12-31', '2021-01-04', '2021-12-31']))
        self.assertEqual(annual_metrics(curve).iloc[0].annual_max_drawdown_pct, 0)

    def test_invalid_curve_rejected(self):
        curve = pd.DataFrame({'equity_usd': [100, 90]}, index=pd.to_datetime(['2021-01-01', '2021-01-01']))
        with self.assertRaises(ValueError):
            annual_metrics(curve)


class ScoreTests(unittest.TestCase):
    def test_negative_calmar_and_no_drawdown(self):
        from reporting.annual import calmar
        self.assertAlmostEqual(calmar(-12, -20), -.6)
        self.assertAlmostEqual(calmar(10, -20), .5)
        self.assertTrue(np.isnan(calmar(10, 0)))

    def test_sharpe_known_returns_and_undefined_variance(self):
        from reporting.annual import sharpe
        self.assertAlmostEqual(sharpe([.1, -.2]), -np.sqrt(14))
        self.assertTrue(np.isnan(sharpe([.01, .01])))
        self.assertTrue(np.isnan(sharpe([0, 0])))
        self.assertTrue(np.isnan(sharpe([.1])))

    def test_annual_sharpe_includes_boundary_return_excludes_anchor(self):
        curve = pd.DataFrame({'equity_usd': [100, 110, 88]},
                             index=pd.to_datetime(['2020-12-31', '2021-01-04', '2021-12-31']))
        row = annual_metrics(curve).iloc[0]
        self.assertAlmostEqual(row.annual_sharpe_zero_rf, -np.sqrt(14))
        self.assertAlmostEqual(row.annual_calmar, -.6)

    def test_ranks_handle_negative_ties_and_missing(self):
        from reporting.annual import score_ranks
        ranks = score_ranks([-.5, -1, -.5, float('nan')])
        self.assertEqual(list(ranks.iloc[:3]), [1, 3, 1])
        self.assertTrue(np.isnan(ranks.iloc[3]))

    def test_grouped_ranks_preserve_nonconsecutive_indices(self):
        from reporting.annual import score_ranks
        rows = pd.DataFrame({'period': ['2020', '2021', '2020', '2021'], 'score': [.2, -.2, .3, -.3]})
        ranks = rows.groupby('period').score.transform(score_ranks)
        self.assertEqual(list(ranks), [2, 1, 1, 2])
