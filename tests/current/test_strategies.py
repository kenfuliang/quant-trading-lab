"""Offline tests of the strategy specs and the traffic-light state machine."""
import unittest

import pandas as pd

from research.evaluation.market_model import MarketConfig
from research.evaluation.parity_fixture import synthetic_fixture
from research.evaluation.screening_engine import run_screen
from research.evaluation.strategies import INCUMBENT_SPEC, build_target_fn

SMALL = dict(name="traffic_light", fast=2, slow=4, vol_window=3, red_vol=0.40, yellow_vol=0.25,
             recover_red_vol=0.35, recover_green_vol=0.20, recover_sessions=5,
             caps={"green": 1.0, "yellow": 0.5, "red": 0.0}, gross=1.0)
RETURNS = [0.001] * 12 + [-0.02] * 3 + [0.03, -0.03, 0.03] + [0.001] * 14
RED, YELLOW, GREEN = 0.0, 1.0, 2.0


def _closes(returns):
    close = [100.0]
    for r in returns:
        close.append(close[-1] * (1 + r))
    return close


def _decisions(spec, closes):
    fn = build_target_fn(spec)
    out = []
    for i in range(len(closes)):
        frame = pd.DataFrame({"close": closes[: i + 1]})
        frame["split_factor"] = 1.0
        out.append(fn(f"d{i}", {"X": frame}, {}, 100_000.0))
    return out


class TrafficLightTests(unittest.TestCase):
    def test_traffic_light_states_on_constructed_series(self):
        decisions = _decisions(SMALL, _closes(RETURNS))
        states = [d.signals[("X", "state")] for d in decisions]
        # warm-up: no position until the first assessed close (idx 3), which classifies yellow
        self.assertEqual(states[:3], [RED] * 3)
        self.assertEqual(states[3:7], [YELLOW] * 4)
        # 5 good closes (idx 3..7) -> green
        self.assertEqual(states[7:13], [GREEN] * 6)
        # trend turns non-positive (vol 0.19 < 0.25): green -> yellow
        self.assertEqual(states[13:16], [YELLOW] * 3)
        # volatility >= 0.40: yellow -> red
        vols = [d.signals.get(("X", "vol")) for d in decisions]
        self.assertGreaterEqual(vols[16], 0.40)
        # red stays red until 5 consecutive closes below 0.35 (idx 20..24)
        self.assertEqual(states[16:24], [RED] * 8)
        self.assertEqual(states[24], YELLOW)
        # the red -> yellow close does not count toward green: 5 further good closes (idx 25..29)
        self.assertEqual(states[24:29], [YELLOW] * 5)
        self.assertTrue(all(s == GREEN for s in states[29:]))
        # sizing follows the cap: red 0, yellow half, green full
        self.assertEqual(decisions[16].targets["X"], 0)
        self.assertEqual(decisions[24].targets["X"], int(0.5 * 100_000 / _closes(RETURNS)[24]))
        self.assertEqual(decisions[29].targets["X"], int(100_000 / _closes(RETURNS)[29]))

    def test_warmup_is_red_until_slow_ema_exists(self):
        spec = dict(INCUMBENT_SPEC)
        closes = [100.0 * (1.001 ** i) for i in range(205)]
        decisions = _decisions(spec, closes)
        for i in range(199):  # EMA200 needs 200 closes
            self.assertEqual(decisions[i].signals[("X", "state")], RED)
            self.assertEqual(decisions[i].targets["X"], 0)
        self.assertNotIn(("X", "trend"), decisions[198].signals)
        self.assertIn(("X", "trend"), decisions[199].signals)
        # first assessed session classifies directly (legacy unassessed -> yellow), not red
        self.assertEqual(decisions[199].signals[("X", "state")], YELLOW)
        self.assertGreater(decisions[199].targets["X"], 0)
        self.assertGreater(decisions[-1].targets["X"], 0)

    def test_first_assessed_session_in_high_vol_is_red(self):
        closes = [100.0 * (1.05 if i % 2 else 0.95) for i in range(8)]
        decisions = _decisions(SMALL, closes)
        self.assertEqual(decisions[4].signals[("X", "state")], RED)
        self.assertEqual(decisions[4].targets["X"], 0)

    def test_recovery_stages_do_not_share_a_confirmation_close(self):
        # after a spike, calm uptrend meets both criteria: yellow at t, green no earlier than t+5
        decisions = _decisions(SMALL, _closes(RETURNS))
        states = [d.signals[("X", "state")] for d in decisions]
        t = states.index(YELLOW, 17)
        self.assertEqual(states[t:t + 5], [YELLOW] * 5)
        self.assertEqual(states[t + 5], GREEN)

    def test_multi_instrument_equal_split(self):
        fn = build_target_fn({"name": "buy_hold", "gross": 0.9})
        frames = {}
        for name, px in (("A", 10.0), ("B", 30.0)):
            frame = pd.DataFrame({"close": [px, px]})
            frame["split_factor"] = 1.0
            frames[name] = frame
        d = fn("d", frames, {}, 1000.0)
        self.assertEqual(d.targets, {"A": 45, "B": 15})

    def test_zero_close_gives_zero_shares(self):
        fn = build_target_fn({"name": "buy_hold", "gross": 0.9})
        frame = pd.DataFrame({"close": [0.0, float("nan")]})
        frame["split_factor"] = 1.0
        self.assertEqual(fn("d", {"A": frame}, {}, 1000.0).targets, {"A": 0})

    def test_causal_prefix_independence(self):
        closes = _closes(RETURNS)
        full = _decisions(SMALL, closes)
        short = _decisions(SMALL, closes[:20])
        for a, b in zip(short, full):
            self.assertEqual(a, b)

    def test_unknown_strategy_raises(self):
        with self.assertRaises(ValueError):
            build_target_fn({"name": "nope"})

    def test_every_strategy_runs_on_the_fixture(self):
        data = synthetic_fixture()
        market = MarketConfig(cost_bps=0, commission_usd=0)
        specs = [{"name": "sma_trend", "window": 20, "gross": 0.95},
                 {"name": "buy_hold", "gross": 0.99},
                 {"name": "ema_trend", "fast": 10, "slow": 30, "gross": 0.99},
                 dict(SMALL)]
        for spec in specs:
            result = run_screen(data, build_target_fn(spec), market)
            self.assertEqual(len(result.returns), len(data.sessions), spec["name"])


if __name__ == "__main__":
    unittest.main()
