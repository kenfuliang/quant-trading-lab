import unittest
from decimal import Decimal

from paper_trading.risk_gate import GateState, RiskLimits, check

LIMITS = RiskLimits()


def state(**kw):
    base = dict(submissions=0, position=Decimal(0), realized_pnl=Decimal(0), halted=False)
    return GateState(**{**base, **kw})


class RiskGateTests(unittest.TestCase):
    def test_flat_buy_within_limits_is_allowed(self):
        decision = check(LIMITS, "buy", 1, "100.00", state())
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reasons, ())

    def test_halt_blocks_even_a_reducing_order(self):
        decision = check(LIMITS, "sell", 1, "100.00", state(position=Decimal(1), halted=True))
        self.assertFalse(decision.allowed)
        self.assertIn("halt_engaged", decision.reasons)

    def test_notional_limit(self):
        self.assertIn("notional_limit", check(LIMITS, "buy", 1, "1000.01", state()).reasons)

    def test_order_count_limit(self):
        self.assertIn("order_count_limit", check(LIMITS, "buy", 1, "100", state(submissions=2)).reasons)

    def test_position_limits_forbid_pyramiding_and_shorting(self):
        self.assertIn("position_limit", check(LIMITS, "buy", 1, "100", state(position=Decimal(1))).reasons)
        self.assertIn("position_limit", check(LIMITS, "sell", 1, "100", state()).reasons)

    def test_daily_loss_denies_and_requests_trip(self):
        decision = check(LIMITS, "buy", 1, "100", state(realized_pnl=Decimal("-25")))
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.trip)
        self.assertIn("daily_loss_limit", decision.reasons)

    def test_small_loss_does_not_trip(self):
        decision = check(LIMITS, "buy", 1, "100", state(realized_pnl=Decimal("-24.99")))
        self.assertTrue(decision.allowed)
        self.assertFalse(decision.trip)

    def test_malformed_order_is_denied(self):
        for side, qty, price in [("hold", 1, "100"), ("buy", 0, "100"), ("buy", 1, "0"), ("buy", 1, "NaN")]:
            with self.subTest(side=side, qty=qty, price=price):
                self.assertFalse(check(LIMITS, side, qty, price, state()).allowed)


if __name__ == "__main__":
    unittest.main()
