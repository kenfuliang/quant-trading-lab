import tempfile
import unittest
from pathlib import Path

from reporting.saved_runs import read_curve


class SavedCurveTests(unittest.TestCase):
    def test_first_session_loss_and_drawdown_include_initial_capital(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'curve.csv'
            path.write_text('date,equity\n2020-01-02,90\n2020-01-03,95\n')
            curve, returns = read_curve(path, 100, {'sessions': 2, 'ending_equity': 95, 'max_drawdown_pct': -10, 'total_return_pct': -5})
            self.assertEqual(curve.iloc[0].equity_usd, 100)
            self.assertAlmostEqual(returns.iloc[1], -.1)
            self.assertAlmostEqual(curve.drawdown_pct.min(), -10)
            self.assertAlmostEqual((1 + returns).prod(), .95)

    def test_duplicate_dates_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'curve.csv'
            path.write_text('date,equity\n2020-01-02,90\n2020-01-02,95\n')
            with self.assertRaises(ValueError):
                read_curve(path, 100, {})
