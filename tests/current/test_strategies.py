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
        # warm-up red; 5 calm closes (idx 3..7) -> yellow; good closes -> green at 8
        self.assertEqual(states[:7], [RED] * 7)
        self.assertEqual(states[7], YELLOW)
        self.assertEqual(states[8:13], [GREEN] * 5)
        # trend turns non-positive (vol 0.19 < 0.25): green -> yellow
        self.assertEqual(states[13:16], [YELLOW] * 3)
        # volatility >= 0.40: yellow -> red
        vols = [d.signals.get(("X", "vol")) for d in decisions]
        self.assertGreaterEqual(vols[16], 0.40)
        self.assertEqual(states[16], RED)
        # red stays red until 5 consecutive closes below 0.35 (idx 20..24)
        self.assertEqual(states[16:24], [RED] * 8)
        self.assertEqual(states[24], YELLOW)
        # yellow -> green after 5 good closes (trend > 0, vol < 0.20; idx 21..25)
        self.assertEqual(states[25], GREEN)
        self.assertTrue(all(s == GREEN for s in states[25:]))
        # sizing follows the cap: red 0, yellow half, green full
        self.assertEqual(decisions[16].targets["X"], 0)
        self.assertEqual(decisions[24].targets["X"], int(0.5 * 100_000 / _closes(RETURNS)[24]))
        self.assertEqual(decisions[25].targets["X"], int(100_000 / _closes(RETURNS)[25]))

    def test_warmup_is_red_until_slow_ema_exists(self):
        spec = dict(INCUMBENT_SPEC)
        closes = [100.0 * (1.001 ** i) for i in range(205)]
        decisions = _decisions(spec, closes)
        for i in range(199):  # EMA200 needs 200 closes
            self.assertEqual(decisions[i].signals[("X", "state")], RED)
            self.assertEqual(decisions[i].targets["X"], 0)
        self.assertNotIn(("X", "trend"), decisions[198].signals)
        self.assertIn(("X", "trend"), decisions[199].signals)
        self.assertEqual(decisions[199].signals[("X", "state")], RED)  # still in recovery
        self.assertGreater(decisions[-1].targets["X"], 0)  # calm uptrend eventually invests

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
