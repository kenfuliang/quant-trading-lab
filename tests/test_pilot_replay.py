import unittest
from datetime import date, timedelta

from paper_trading.pilot_replay import replay
from paper_trading.risk_gate import PilotLimits


def days(n, start=date(2020, 1, 1)):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


class PilotReplayTests(unittest.TestCase):
    def test_flat_and_rising_market_fires_nothing(self):
        ds = days(260)
        closes = {d: 100 + i * 0.1 for i, d in enumerate(ds)}
        out = replay(closes)
        self.assertEqual(sum(out["counts"].values()), 0)
        self.assertGreater(out["final_equity"], 15000)

    def test_a_crash_while_long_fires_loss_and_drawdown_limits(self):
        ds = days(262)
        closes = {d: 100 + i * 0.1 for i, d in enumerate(ds)}
        last = ds[-1]
        closes[last] = closes[ds[-2]] * 0.6  # -40% on a day the signal is long
        out = replay(closes)
        self.assertIn(last, out["events"]["daily_loss_limit"])
        self.assertIn(last, out["events"]["weekly_loss_limit"])
        self.assertIn(last, out["events"]["drawdown_halt"])
        self.assertLess(out["max_drawdown"], -0.3)

    def test_warmup_is_required(self):
        with self.assertRaises(ValueError):
            replay({d: 100.0 for d in days(50)})

    def test_limits_scale_with_capital(self):
        ds = days(262)
        closes = {d: 100 + i * 0.1 for i, d in enumerate(ds)}
        closes[ds[-1]] = closes[ds[-2]] * 0.97  # -3%
        self.assertIn(ds[-1], replay(closes)["events"]["daily_loss_limit"])
        wide = PilotLimits(daily_loss=PilotLimits().daily_loss * 2)
        self.assertNotIn(ds[-1], replay(closes, wide)["events"]["daily_loss_limit"])


if __name__ == "__main__":
    unittest.main()
