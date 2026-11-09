"""Pin paper_trading.spy_signal to the engine's actual positions. Offline only."""
import unittest

import numpy as np
import pandas as pd

from paper_trading.spy_signal import target_position, target_series
from research.studies.spy.spy_backtest import run_engine
from scripts.current.shadow_replay import replay_series


def frame(closes):
    dates = pd.bdate_range("2020-01-01", periods=len(closes)).strftime("%Y-%m-%d")
    closes = np.round(np.asarray(closes, float), 2)
    return pd.DataFrame({"open": closes, "high": closes + 1, "low": closes - 1,
                         "close": closes, "volume": 1_000_000}, index=dates)


def wavy(n=120):
    t = np.arange(n)
    return 100 + 15 * np.sin(t / 9) + t * 0.05


class SignalParityTests(unittest.TestCase):
    def assert_parity(self, data, fast, slow):
        curve, _, _, _ = run_engine(data, {}, "trend", start=data.index[0], end=data.index[-1],
                                    fast=fast, slow=slow)
        series = [0] + target_series(data.close, fast, slow)[:-1]
        held = [int(s > 0) for s in curve.shares]
        self.assertEqual(held, series)
        self.assertIn(1, held)
        self.assertIn(0, held[slow:])  # fixture actually flips

    def test_matches_engine_positions_short_spans(self):
        self.assert_parity(frame(wavy()), 3, 8)

    def test_matches_engine_positions_production_spans(self):
        t = np.arange(520)
        data = frame(100 + 25 * np.sin(t / 45) + t * 0.03)
        self.assert_parity(data, 50, 200)

    def test_scalar_matches_series_and_warmup_is_flat(self):
        closes = list(wavy())
        series = target_series(closes, 3, 8)
        for i in range(len(closes)):
            self.assertEqual(target_position(closes[:i + 1], 3, 8), series[i])
        self.assertEqual(series[:7], [0] * 7)

    def test_no_lookahead(self):
        closes = list(wavy())
        changed = closes[:80] + [c * 3 for c in closes[80:]]
        self.assertEqual(target_series(closes, 3, 8)[:80], target_series(changed, 3, 8)[:80])

    def test_replay_series_has_no_mismatch(self):
        data = frame(wavy())
        rows, mismatches = replay_series(data, {}, start=data.index[0], end=data.index[-1], fast=3, slow=8)
        self.assertEqual(mismatches, [])
        self.assertEqual(len(rows), len(data))

    def test_invalid_spans(self):
        with self.assertRaises(ValueError):
            target_position([1.0] * 10, 8, 3)


if __name__ == "__main__":
    unittest.main()
