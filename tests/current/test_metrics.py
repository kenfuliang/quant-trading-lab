"""Offline tests of the run-output metrics library."""
import math
import unittest

import pandas as pd

from research.evaluation import metrics
from research.evaluation.market_model import MarketConfig, sma_trend_targets
from research.evaluation.parity_fixture import synthetic_fixture
from research.evaluation.screening_engine import run_screen

DATES = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-08", "2024-01-09"]


def _returns(equity, initial=100.0, dates=DATES):
    prev = [initial] + list(equity[:-1])
    net = [e / p - 1 for e, p in zip(equity, prev)]
    return pd.DataFrame({"date": dates[: len(equity)], "gross_return": net, "cost": 0.0,
                         "net_return": net, "equity": list(equity)})


def _fills(rows=()):
    return pd.DataFrame(list(rows), columns=["date", "instrument", "side", "quantity", "price", "cost"])


class MetricsTests(unittest.TestCase):
    def test_hand_computed_series(self):
        equity = [110.0, 105.0, 100.0, 112.0, 108.0]
        out = metrics.summarize(_returns(equity), _fills(), 100.0)
        self.assertEqual(tuple(out), metrics.METRIC_KEYS)
        cagr = (108 / 100) ** (252 / 5) - 1
        dd = 1 - 100 / 110
        r = pd.Series([e / p - 1 for e, p in zip(equity, [100.0] + equity[:-1])])
        sharpe = r.mean() / r.std(ddof=1) * math.sqrt(252)
        self.assertAlmostEqual(out["net_cagr"], cagr)
        self.assertAlmostEqual(out["max_drawdown"], dd)
        self.assertAlmostEqual(out["sharpe"], sharpe)
        self.assertAlmostEqual(out["calmar"], cagr / dd)
        self.assertEqual(out["turnover"], 0.0)
        self.assertEqual(out["longest_underwater_sessions"], 2)
        self.assertEqual(out["longest_underwater_days"], 6)  # 01-02 peak -> 01-08 regain

    def test_drawdown_includes_initial_baseline(self):
        out = metrics.summarize(_returns([90.0, 95.0, 99.0, 98.0, 99.5]), _fills(), 100.0)
        self.assertAlmostEqual(out["max_drawdown"], 0.10)
        self.assertEqual(out["longest_underwater_sessions"], 5)

    def test_flat_series_gives_none_sharpe_and_calmar(self):
        out = metrics.summarize(_returns([100.0] * 5), _fills(), 100.0)
        self.assertIsNone(out["sharpe"])
        self.assertIsNone(out["calmar"])
        self.assertEqual(out["max_drawdown"], 0.0)
        self.assertEqual(out["net_cagr"], 0.0)
        self.assertEqual(out["longest_underwater_sessions"], 0)
        self.assertEqual(out["longest_underwater_days"], 0)

    def test_turnover_from_fills(self):
        fills = _fills([("2024-01-02", "AAA", "BUY", 10, 50.0, 0.1),
                        ("2024-01-04", "AAA", "SELL", 4, 25.0, 0.1)])
        out = metrics.summarize(_returns([100.0] * 5), fills, 100.0)
        self.assertAlmostEqual(out["turnover"], 600.0 / 100.0 / (5 / 252))

    def test_underwater_sessions_and_days(self):
        # peak 110 on 01-03; below it 01-04..01-09, never regained -> 3 sessions, to the last date
        out = metrics.summarize(_returns([105.0, 110.0, 100.0, 101.0, 102.0]), _fills(), 100.0)
        self.assertEqual(out["longest_underwater_sessions"], 3)
        self.assertEqual(out["longest_underwater_days"], 6)

    def test_window_rebases(self):
        ret = _returns([110.0, 121.0, 108.9, 120.0, 132.0])
        w = metrics.window(ret, "2024-01-04", "2024-01-08")
        self.assertEqual(list(w["date"]), ["2024-01-04", "2024-01-08"])
        self.assertAlmostEqual(w["equity"].iloc[0], 108.9 / 121.0)
        self.assertAlmostEqual(w["equity"].iloc[1], 120.0 / 121.0)
        self.assertAlmostEqual(w["net_return"].iloc[0], 108.9 / 121.0 - 1)
        self.assertEqual(ret["equity"].iloc[2], 108.9)  # input untouched

    def test_matches_registry_definitions_on_synthetic_fixture_run(self):
        cfg = MarketConfig()
        res = run_screen(synthetic_fixture(), sma_trend_targets(), cfg)
        out = metrics.summarize(res.returns, res.fills, cfg.initial_cash)
        self.assertEqual(tuple(out), metrics.METRIC_KEYS)
        for key, value in out.items():
            self.assertIsNotNone(value, key)
            self.assertTrue(math.isfinite(value), key)
        self.assertGreaterEqual(out["max_drawdown"], 0.0)


if __name__ == "__main__":
    unittest.main()
