import unittest
from decimal import Decimal as D

from paper_trading.risk_gate import PilotLimits, PilotState, check_pilot


def state(**kw):
    base = dict(equity=D(15000), peak_equity=D(15000), day_start_equity=D(15000), week_start_equity=D(15000),
                cash=D(15000), position=D(0), halted=False)
    base.update(kw)
    return PilotState(**base)


class PilotLimitTests(unittest.TestCase):
    limits = PilotLimits()

    def test_a_normal_buy_is_allowed_and_there_is_no_position_cap(self):
        d = check_pilot(self.limits, "SPY", "buy", 30, 500, state())  # 100% of capital in one name
        self.assertTrue(d.allowed)
        self.assertFalse(d.trip)

    def test_daily_loss_trips_at_two_percent_of_pilot_capital(self):
        self.assertFalse(check_pilot(self.limits, "SPY", "buy", 1, 100, state(equity=D("14701"), cash=D(14701))).trip)
        d = check_pilot(self.limits, "SPY", "buy", 1, 100, state(equity=D(14700), day_start_equity=D(15000)))
        self.assertTrue(d.trip)
        self.assertIn("daily_loss_limit", d.reasons)

    def test_weekly_loss_trips_at_five_percent(self):
        d = check_pilot(self.limits, "SPY", "buy", 1, 100, state(equity=D(14250), week_start_equity=D(15000), day_start_equity=D(14250)))
        self.assertIn("weekly_loss_limit", d.reasons)
        self.assertTrue(d.trip)

    def test_drawdown_warns_at_twenty_and_halts_at_thirty_percent_from_peak(self):
        warn = check_pilot(self.limits, "SPY", "buy", 1, 100, state(equity=D(16000), peak_equity=D(20000),
                                                                      day_start_equity=D(16000), week_start_equity=D(16000), cash=D(16000)))
        self.assertTrue(warn.allowed)
        self.assertEqual(warn.warnings, ("drawdown_warning",))
        halt = check_pilot(self.limits, "SPY", "buy", 1, 100, state(equity=D(14000), peak_equity=D(20000),
                                                                      day_start_equity=D(14000), week_start_equity=D(14000), cash=D(14000)))
        self.assertIn("drawdown_halt", halt.reasons)
        self.assertTrue(halt.trip)

    def test_no_margin_and_no_shorting(self):
        self.assertIn("exceeds_cash", check_pilot(self.limits, "SPY", "buy", 40, 500, state()).reasons)
        self.assertIn("would_short", check_pilot(self.limits, "SPY", "sell", 1, 500, state()).reasons)
        self.assertTrue(check_pilot(self.limits, "SPY", "sell", 1, 500, state(position=D(2))).allowed)

    def test_allow_list_blocks_unlisted_symbols_when_configured(self):
        limits = PilotLimits(allowed_symbols=frozenset({"SPY"}))
        self.assertIn("symbol_not_allowed", check_pilot(limits, "TQQQ", "buy", 1, 50, state()).reasons)
        self.assertTrue(check_pilot(limits, "SPY", "buy", 1, 50, state()).allowed)

    def test_halted_and_garbage_state_fail_closed(self):
        self.assertIn("halt_engaged", check_pilot(self.limits, "SPY", "buy", 1, 50, state(halted=True)).reasons)
        d = check_pilot(self.limits, "SPY", "buy", 1, 50, state(equity=D("NaN")))
        self.assertFalse(d.allowed)
        self.assertTrue(d.trip)

    def test_invalid_order_is_rejected(self):
        for args in (("SPY", "hold", 1, 50), ("SPY", "buy", 0, 50), ("SPY", "buy", 1, 0)):
            self.assertIn("invalid_order", check_pilot(self.limits, *args, state()).reasons)


if __name__ == "__main__":
    unittest.main()
