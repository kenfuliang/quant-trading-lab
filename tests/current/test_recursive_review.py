"""Independent review arithmetic fixtures, not additional investment trials."""
import unittest

import numpy as np

from research.evaluation import saved_review as review


class ReviewMetricsTests(unittest.TestCase):
    def test_initial_capital_anchor_counts_first_loss(self):
        row = review.metrics([100, 80, 90])
        self.assertAlmostEqual(row['return_pct'], -10)
        self.assertAlmostEqual(row['drawdown_pct'], -20)
        self.assertAlmostEqual(row['calmar'], -.5)

    def test_calendar_time_cagr_and_no_drawdown_ratio(self):
        row = review.metrics([100, 200], 730.5)
        self.assertAlmostEqual(row['return_pct'], (np.sqrt(2)-1)*100)
        self.assertIsNone(row['calmar'])
        self.assertIsNone(row['sharpe'])

    def test_bad_equity_is_rejected_instead_of_scored(self):
        for values in ([100, float('nan')], [100, float('inf')], [100, 0], [100, -1]):
            with self.assertRaises(ValueError):
                review.metrics(values)


if __name__ == '__main__':
    unittest.main()
