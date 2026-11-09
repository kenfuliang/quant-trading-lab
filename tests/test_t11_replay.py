import unittest

import numpy as np
import pandas as pd

from paper_trading import t11_replay as tr
from paper_trading.t11_pilot import SYMBOLS


def synthetic_bars(n=620, seed=0):
    rng = np.random.default_rng(seed)
    days = list(pd.bdate_range("2023-01-02", periods=n).strftime("%Y-%m-%d"))
    bars = {}
    for k, symbol in enumerate(sorted(SYMBOLS)):
        close = 50 * np.cumprod(1 + rng.normal(0.0003, 0.01, n))
        bars[symbol] = {d: (c * 0.998, c * 1.01, c * 0.99, c) for d, c in zip(days, close)}
    return bars, days


def payload(symbol, rows):
    return {"bars": {symbol: [{"t": f"{d}T05:00:00Z", "o": o, "h": h, "l": l, "c": c, "v": 1} for d, (o, h, l, c) in rows.items()]}}


class ParseTests(unittest.TestCase):
    def test_valid_bars_parse_and_unknown_symbols_are_rejected(self):
        got = tr.parse_bars([payload("SPY", {"2024-01-02": (10, 11, 9, 10.5)})], {"SPY"})
        self.assertEqual(got["SPY"]["2024-01-02"], (10.0, 11.0, 9.0, 10.5))
        with self.assertRaises(ValueError):
            tr.parse_bars([payload("XXX", {"2024-01-02": (10, 11, 9, 10.5)})], {"SPY"})

    def test_bad_ohlc_or_duplicate_or_wrong_time_is_rejected(self):
        for bad in [{"2024-01-02": (10, 9, 11, 10)}, {"2024-01-02": (-1, 1, 1, 1)}]:
            with self.assertRaises(ValueError):
                tr.parse_bars([payload("SPY", bad)], {"SPY"})
        good = payload("SPY", {"2024-01-02": (10, 11, 9, 10.5)})
        with self.assertRaises(ValueError):
            tr.parse_bars([good, good], {"SPY"})
        late = {"bars": {"SPY": [{"t": "2024-01-02T15:00:00Z", "o": 1, "h": 1, "l": 1, "c": 1}]}}
        with self.assertRaises(ValueError):
            tr.parse_bars([late], {"SPY"})


class DecisionTests(unittest.TestCase):
    def test_decisions_use_only_data_up_to_each_day(self):
        bars, days = synthetic_bars()
        raw = {d: bars["SPY"][d][3] for d in days}
        calls = []

        def policy(features, cap):
            calls.append((features["prices"]["SPY"], cap))
            return {"reason": "stub", "gated_weights": {"TQQQ": cap}}

        start = days[400]
        decided = tr.decisions(bars, raw, policy, start)
        self.assertTrue(decided and min(decided) >= start)
        first = min(decided)
        self.assertEqual(calls[0][0], bars["SPY"][first][3])
        changed = {s: dict(v) for s, v in bars.items()}
        last = days[-1]
        changed["SPY"][last] = tuple(x * 2 for x in changed["SPY"][last])
        again = tr.decisions(changed, {**raw, last: raw[last] * 2}, policy, start)
        self.assertEqual(again[days[-2]], decided[days[-2]])

    def test_gate_series_needs_enough_history(self):
        with self.assertRaises(ValueError):
            tr.gate_series({f"2024-01-{d:02d}": 100.0 for d in range(1, 20)})


class SimulateTests(unittest.TestCase):
    def setUp(self):
        self.bars, self.days = synthetic_bars(n=30)

    def test_fills_happen_at_the_next_open_with_cost_and_whole_shares(self):
        d0, d1 = self.days[5], self.days[6]
        sim = tr.simulate({d0: {"weights": {"TQQQ": 1.0}}}, self.bars, capital=10000, deployment=0.9, cost_bp=25)
        self.assertEqual(sim["dates"][0], d0)
        self.assertNotIn(d0, sim["orders"])
        order = sim["orders"][d1][0]
        open_price = self.bars["TQQQ"][d1][0]
        self.assertEqual(order[0], "TQQQ")
        self.assertEqual(order[2], round(open_price, 4))
        self.assertEqual(order[1], float(int(9000 // open_price)))
        self.assertEqual(sim["nav"][0], 10000.0)
        self.assertIn(d0, sim["decided"])
        self.assertLess(sim["nav"][1], 10000 * 1.2)

    def test_changing_the_decision_sells_then_buys(self):
        decided = {self.days[5]: {"weights": {"TQQQ": 1.0}}, self.days[7]: {"weights": {"SQQQ": 1.0}}}
        sim = tr.simulate(decided, self.bars)
        day = self.days[8]
        self.assertEqual([o[0] for o in sim["orders"][day]], ["TQQQ", "SQQQ"])
        self.assertLess(sim["orders"][day][0][1], 0)
        self.assertGreater(sim["orders"][day][1][1], 0)

    def test_flat_decision_holds_cash_and_snapshots_clear(self):
        decided = {self.days[5]: {"weights": {"TQQQ": 1.0}}, self.days[7]: {"weights": {}}}
        sim = tr.simulate(decided, self.bars)
        self.assertEqual(sim["pos"][self.days[8]], {})
        self.assertEqual(sim["expo"][-1], 0.0)


class ParityTests(unittest.TestCase):
    def test_identical_datasets_agree_fully(self):
        bars, days = synthetic_bars(n=30)
        sim = tr.simulate({days[5]: {"weights": {"TQQQ": 1.0}}}, bars)
        result = tr.parity(sim, sim)
        self.assertEqual(result["same_held_set_share"], 1.0)
        self.assertAlmostEqual(result["daily_return_correlation"], 1.0)

    def test_different_holdings_lower_the_agreement(self):
        bars, days = synthetic_bars(n=30)
        a = tr.simulate({days[5]: {"weights": {"TQQQ": 1.0}}}, bars)
        b = tr.simulate({days[5]: {"weights": {"SQQQ": 1.0}}}, bars)
        self.assertLess(tr.parity(a, b)["same_held_set_share"], 1.0)


if __name__ == "__main__":
    unittest.main()
