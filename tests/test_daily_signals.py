import unittest

import numpy as np
import pandas as pd

from research.daily_signals import DEFINITIONS, build_signal
from research.leveraged_spy import FinancingModel, simulate


def bars(close):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({'open': close, 'high': close + .25, 'low': close - .25,
                         'close': close, 'volume': 1000.},
                        index=pd.bdate_range('2004-01-02', periods=len(close)))


class DailySignalTests(unittest.TestCase):
    def test_prefix_stability_and_future_mutation(self):
        rng = np.random.default_rng(73)
        data = bars(100 * np.exp(np.cumsum(rng.normal(0, .015, 550))))
        for strategy in DEFINITIONS:
            with self.subTest(strategy=strategy):
                full = build_signal(data, strategy)
                pd.testing.assert_frame_equal(full.iloc[:420], build_signal(data.iloc[:420], strategy))
                changed = data.copy()
                changed.iloc[420:, :4] *= 2
                pd.testing.assert_frame_equal(full.iloc[:420], build_signal(changed, strategy).iloc[:420])
                self.assertEqual(full.want_long.dtype, bool)
                self.assertFalse(full.want_long.isna().any())
                self.assertFalse(full.want_long.iloc[0])

    def test_warmup_blocks_long_positions(self):
        increasing = bars(np.arange(100., 500.))
        for strategy, first_possible in {1: 200, 2: 200, 3: 200, 4: 34,
                                         5: 200, 6: 21, 7: 56, 8: 15,
                                         10: 2, 11: 3, 12: 20, 13: 20,
                                         14: 102, 15: 6, 21: 253}.items():
            with self.subTest(strategy=strategy):
                signal = build_signal(increasing, strategy).want_long
                self.assertFalse(signal.iloc[:first_possible].any())
        for strategy in (1, 2, 3, 5, 6, 7, 8, 10, 21):
            self.assertTrue(build_signal(increasing, strategy).want_long.iloc[-1])

    def test_rsi_state_entry_exit_and_next_open(self):
        frame = build_signal(bars([100, 99, 98, 97, 105, 106]), 11)
        self.assertEqual(frame.want_long.tolist(), [False, False, False, True, True, False])

    def test_channel_hysteresis_and_actual_next_open_roundtrip(self):
        frame = build_signal(bars([100, 102, 103, 100, 99, 102]), 10)
        self.assertEqual(frame.want_long.tolist(), [False, False, True, True, False, False])
        curve, trades = simulate(frame, {}, 'trend', 1,
                                 FinancingModel(capital=10000, cost_bps=0, commission=0))
        self.assertEqual(trades.date.tolist(), [str(frame.index[2].date()), str(frame.index[4].date())])
        self.assertEqual(trades.fill_price.tolist(), [103, 99])
        self.assertGreater(trades.delta.iloc[0], 0)
        self.assertLess(trades.delta.iloc[-1], 0)
        self.assertEqual(curve.shares.iloc[-1], 0)

    def test_constant_prices_never_invent_a_signal(self):
        for strategy in DEFINITIONS:
            with self.subTest(strategy=strategy):
                self.assertFalse(build_signal(bars([100.] * 400), strategy).want_long.any())

    def test_reject_invalid_data(self):
        valid = bars([100., 101., 102.])
        invalid = [valid.iloc[::-1], pd.concat([valid, valid.iloc[-1:]]), valid.assign(close=np.nan),
                   valid.assign(volume=np.inf), valid.assign(high=1), valid.assign(low=0)]
        for frame in invalid:
            with self.subTest(frame=repr(frame)):
                with self.assertRaises(ValueError):
                    build_signal(frame, 1)
        with self.assertRaises(ValueError):
            build_signal(valid, 1000)


if __name__ == '__main__':
    unittest.main()
