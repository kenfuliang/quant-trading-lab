"""Offline tests of the trust statistics (PSR, DSR, PBO)."""
import math
import time
import unittest
from statistics import NormalDist

import numpy as np
import pandas as pd

from research.evaluation import trust

ND = NormalDist()


def _series(n=250, seed=1, mu=0.001, sd=0.01):
    return np.random.default_rng(seed).normal(mu, sd, n)


class PsrTests(unittest.TestCase):
    def test_psr_hand_value(self):
        r = np.array([0.01, -0.005, 0.02, 0.003, -0.01, 0.015, 0.007, -0.002, 0.012, 0.001])
        n = len(r)
        mean = r.mean()
        std = r.std(ddof=1)
        sr = mean / std
        z = (r - mean) / r.std(ddof=0)
        skew = float((z ** 3).mean())
        kurt = float((z ** 4).mean())
        expected = ND.cdf((sr - 0.1) * math.sqrt(n - 1) / math.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr ** 2))
        out = trust.psr(r, sr_benchmark=0.1)
        self.assertAlmostEqual(out["value"], expected, places=12)
        self.assertAlmostEqual(out["sharpe"], sr, places=12)
        self.assertEqual(out["n"], n)
        self.assertAlmostEqual(trust.sharpe_per_period(r), sr, places=12)

    def test_psr_rises_with_sample_length(self):
        long = _series(1000, seed=3)
        self.assertGreater(trust.psr(long)["value"], trust.psr(long[:100])["value"])

    def test_expected_max_sharpe_increases_with_trials(self):
        vals = [trust.expected_max_sharpe(n, 0.01) for n in (2, 10, 100, 1000)]
        self.assertEqual(vals, sorted(vals))
        self.assertGreater(vals[0], 0.0)

    def test_dsr_below_psr_when_many_trials(self):
        r = _series(500, seed=5)
        self.assertLess(trust.dsr(r, 100, 0.0004)["value"], trust.psr(r)["value"])

    def test_degenerate_inputs_return_none_with_reason(self):
        flat = np.zeros(50)
        for out in (trust.psr(flat), trust.psr(np.array([0.1, 0.2])),
                    trust.dsr(_series(), 1, 0.01), trust.dsr(_series(), 10, 0.0),
                    trust.dsr(flat, 10, 0.01),
                    trust.pbo(pd.DataFrame(np.ones((5, 3))), n_partitions=16),
                    trust.pbo(pd.DataFrame(np.ones((100, 1))), n_partitions=16),
                    trust.pbo(pd.DataFrame(np.ones((100, 3))), n_partitions=5)):
            self.assertIsNone(out["value"])
            self.assertTrue(out["reason"])
        self.assertIsNone(trust.sharpe_per_period(flat))
        self.assertIsNone(trust.sharpe_per_period(np.array([0.1])))


class PboTests(unittest.TestCase):
    def test_pbo_near_zero_for_dominant_config_and_high_for_noise(self):
        rng = np.random.default_rng(7)
        noise = rng.normal(0, 0.01, (320, 8))
        dom = noise.copy()
        dom[:, 0] = 0.01 + rng.normal(0, 0.001, 320)
        out = trust.pbo(pd.DataFrame(dom), n_partitions=8)
        self.assertEqual(out["value"], 0.0)
        self.assertEqual(out["n_combinations"], 70)
        self.assertEqual(len(out["logits"]), 70)
        # The 0.2-0.8 band for pure noise depends on this fixed seed (seed 7).
        pure = trust.pbo(pd.DataFrame(noise), n_partitions=8)
        self.assertGreater(pure["value"], 0.2)
        self.assertLess(pure["value"], 0.8)

    def test_constant_nonzero_column_is_never_chosen(self):
        noise = np.random.default_rng(13).normal(0, 0.01, (2500, 7))
        base = trust.pbo(pd.DataFrame(noise), n_partitions=16)
        with_const = np.column_stack([noise, np.full(2500, 0.05)])
        out = trust.pbo(pd.DataFrame(with_const), n_partitions=16)
        self.assertEqual(out["value"], base["value"])
        self.assertGreater(out["value"], 0.2)

    def test_guards_for_benchmark_and_expected_max_sharpe(self):
        self.assertIsNone(trust.psr(_series(), sr_benchmark=float("nan"))["value"])
        with self.assertRaises(ValueError):
            trust.expected_max_sharpe(1, 0.01)
        with self.assertRaises(ValueError):
            trust.expected_max_sharpe(5, -0.1)

    def test_pbo_default_partitions_runs_fast(self):
        perf = pd.DataFrame(np.random.default_rng(11).normal(0, 0.01, (2500, 8)))
        t0 = time.time()
        out = trust.pbo(perf)
        self.assertLess(time.time() - t0, 30)
        self.assertEqual(out["n_combinations"], 12870)
        self.assertTrue(all(math.isfinite(x) for x in out["logits"]))


if __name__ == "__main__":
    unittest.main()
