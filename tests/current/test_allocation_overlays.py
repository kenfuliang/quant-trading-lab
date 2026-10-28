import unittest
import numpy as np
import pandas as pd
from research.policies.allocation_overlays import DEFINITIONS, build_allocation_signal


def frame(values):
    close = np.asarray(values, dtype=float)
    return pd.DataFrame({'open': close, 'high': close * 1.01,
                         'low': close * .99, 'close': close},
                        index=pd.date_range('2000-01-01', periods=len(close)))


class AllocationOverlayTests(unittest.TestCase):
    def test_all_methods_are_causal_and_shift_once(self):
        raw = frame(100 * np.exp(np.cumsum(.001 + .02 * np.sin(np.arange(400)))))
        for strategy_id in DEFINITIONS:
            full = build_allocation_signal(raw, strategy_id)
            prefix = build_allocation_signal(raw.iloc[:250], strategy_id)
            pd.testing.assert_frame_equal(full.iloc[:250], prefix)
            changed = raw.copy()
            changed.loc[raw.index[250]:, ['open', 'high', 'low', 'close']] *= 2
            pd.testing.assert_frame_equal(full.iloc[:250], build_allocation_signal(changed, strategy_id).iloc[:250])
            # Today's changed close cannot affect today's open allocation.
            one = raw.copy()
            one.loc[raw.index[249], 'close'] *= 1.005
            pd.testing.assert_series_equal(full.iloc[249][['want_long', 'allocation_factor']], build_allocation_signal(one, strategy_id).iloc[249][['want_long', 'allocation_factor']])
            self.assertEqual(full.want_long.dtype, bool)
            self.assertTrue(full.allocation_factor.between(0, 1).all())
            self.assertFalse(full.iloc[0].want_long)

    def test_volatility_hand_calculation_and_warmup(self):
        raw = frame(100 * np.cumprod(1 + np.tile([.01, -.02], 20)))
        result = build_allocation_signal(raw, 31)
        vol = raw.close.pct_change().iloc[1:21].std(ddof=1) * np.sqrt(252)
        self.assertAlmostEqual(result.iloc[21].allocation_factor, min(1, .1 / vol))
        self.assertFalse(result.iloc[:21].want_long.any())
        self.assertTrue(result.iloc[21].want_long)
        flat = build_allocation_signal(frame(np.full(30, 100)), 31)
        self.assertEqual(flat.iloc[21].allocation_factor, 1)

    def test_trend_gate_waits_for_ema_history(self):
        result = build_allocation_signal(frame(np.arange(100, 350)), 32)
        self.assertFalse(result.iloc[:200].want_long.any())
        self.assertTrue(result.iloc[200].want_long)
        falling = build_allocation_signal(frame(np.arange(350, 100, -1)), 32)
        self.assertFalse(falling.want_long.any())

    def test_underlying_drawdown_thresholds_and_recovery(self):
        raw = frame([100] * 20 + [90, 80, 79, 95, 100])
        result = build_allocation_signal(raw, 33)
        self.assertEqual(result.allocation_factor.tolist()[-5:], [1, .5, .5, 0, 1])
        self.assertFalse(result.iloc[:20].want_long.any())
        self.assertFalse(result.iloc[23].want_long)
        self.assertTrue(result.iloc[24].want_long)

    def test_cppi_emits_metadata_not_fake_portfolio_equity(self):
        result = build_allocation_signal(frame([100, 50, 25]), 34)
        self.assertEqual(result.allocation_factor.tolist(), [0, 1, 1])
        self.assertTrue((result.cppi_floor_fraction == .8).all())
        self.assertTrue((result.cppi_multiplier == 3).all())
        self.assertNotIn('equity_usd', result)

    def test_bad_inputs_rejected(self):
        valid = frame([100] * 25)
        invalid = [valid.iloc[::-1], pd.concat([valid, valid.iloc[-1:]]), valid.iloc[:0]]
        for value in [np.nan, np.inf, -1]:
            bad = valid.copy(); bad.iloc[2, bad.columns.get_loc('close')] = value
            invalid.append(bad)
        for raw in invalid:
            with self.assertRaises(ValueError):
                build_allocation_signal(raw, 31)
        with self.assertRaises(ValueError):
            build_allocation_signal(valid, 999)
