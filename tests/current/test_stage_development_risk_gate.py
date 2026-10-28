"""Stage worksheet exercise: synthetic target interfaces only, no financial runner."""
import unittest
import numpy as np
import pandas as pd
from research.policies.risk_gate import frames


class StageDevelopmentRiskGateTests(unittest.TestCase):
    shock_row = 250

    def market(self, *, shock=True):
        close = np.linspace(100., 160., 360)
        opened = close.copy()
        if shock:
            close[self.shock_row:] *= .5
            opened[self.shock_row + 1:] = close[self.shock_row:-1]
        return pd.DataFrame({"open": opened, "close": close,
                             "high": np.maximum(opened, close) + 1,
                             "low": np.minimum(opened, close) - 1},
                            index=pd.bdate_range("2020-01-01", periods=len(close)))

    def assert_boundary(self, decisions):
        # The shock close is not known at that day's open. Its next open must
        # already carry the risk reduction, rather than waiting a second day.
        self.assertEqual(decisions.iloc[self.shock_row], 1.)
        self.assertEqual(decisions.iloc[self.shock_row + 1], 0.)

    def test_target_is_next_open_ready_and_keeps_input_unchanged(self):
        raw = self.market()
        before = raw.copy(deep=True)
        output, observed = frames(raw)
        self.assert_boundary(output["gate_hold"].intended_target)
        self.assertEqual(pd.Timestamp(observed.observed_close.iloc[self.shock_row + 1]), raw.index[self.shock_row])
        pd.testing.assert_frame_equal(raw, before)

    def test_future_close_changes_no_decision_at_or_before_its_open(self):
        healthy, _ = frames(self.market(shock=False))
        shocked, _ = frames(self.market())
        for case in ("gate_hold", "gate_ema"):
            for field in ("intended_target", "want_long", "base_target"):
                pd.testing.assert_series_equal(healthy[case][field].iloc[:self.shock_row + 1],
                                               shocked[case][field].iloc[:self.shock_row + 1])
        self.assertNotEqual(healthy["gate_hold"].intended_target.iloc[self.shock_row + 1],
                            shocked["gate_hold"].intended_target.iloc[self.shock_row + 1])

    def test_contract_rejects_double_shift_and_lookahead_consumers(self):
        output, _ = frames(self.market())
        target = output["gate_hold"].intended_target
        self.assert_boundary(target)
        for wrong in (target.shift(1).fillna(0.), target.shift(-1).fillna(0.)):
            with self.subTest(wrong_at_shock=wrong.iloc[self.shock_row]):
                with self.assertRaises(AssertionError):
                    self.assert_boundary(wrong)

    def test_warmup_and_invalid_order_have_explicit_behavior(self):
        raw = self.market()
        output, _ = frames(raw)
        self.assertTrue(output["gate_hold"].intended_target.iloc[:200].eq(0.).all())
        self.assertTrue(np.isfinite(output["gate_hold"].intended_target).all())
        duplicate = raw.copy()
        duplicate.index = list(raw.index[:-1]) + [raw.index[-2]]
        with self.assertRaises(ValueError):
            frames(duplicate)
        invalid = raw.copy()
        invalid.loc[invalid.index[10], "close"] = np.nan
        with self.assertRaises(ValueError):
            frames(invalid)

    def test_actual_target_not_nominal_diagnostic_is_composed_with_gate(self):
        output, _ = frames(self.market())
        ema, gated = output["ema"], output["gate_ema"]
        cash = ~ema.want_long
        self.assertTrue(cash.any())
        self.assertTrue(ema.loc[cash, "allocation_factor"].eq(1.).all())
        self.assertTrue(ema.loc[cash, "intended_target"].eq(0.).all())
        self.assertTrue(gated.loc[cash, "intended_target"].eq(0.).all())
        self.assertTrue((gated.intended_target <= ema.intended_target).all())
        self.assertTrue(set(gated.intended_target.unique()) <= {0., .5, 1.})


if __name__ == "__main__":
    unittest.main()
