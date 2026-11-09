import asyncio
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from paper_trading.alpaca_fixture import native_fixture
from paper_trading.kill_switch import KillSwitch
from paper_trading.risk_gate import RiskLimits


class NativeHaltTests(unittest.TestCase):
    def test_engaged_switch_blocks_submit_and_halts_native_risk_engine(self):
        with tempfile.TemporaryDirectory() as t:
            r = asyncio.run(native_fixture(t, halted=True))
            self.assertEqual(r["broker_post_count"], 0)
            self.assertEqual(r["risk_engine_state"], "HALTED")
            self.assertIn("halt", [e["type"] for e in r["events"]])
            self.assertTrue(KillSwitch(Path(t) / "HALT").engaged())

    def test_normal_session_keeps_risk_engine_active(self):
        with tempfile.TemporaryDirectory() as t:
            r = asyncio.run(native_fixture(t))
            self.assertEqual(r["risk_engine_state"], "ACTIVE")
            self.assertEqual(r["broker_post_count"], 2)

    def test_daily_loss_limit_trips_a_persistent_halt_before_posting(self):
        with tempfile.TemporaryDirectory() as t:
            r = asyncio.run(native_fixture(t, denied=True, limits=RiskLimits(max_daily_loss=Decimal(0))))
            self.assertEqual(r["broker_post_count"], 0)
            denied = [e for e in r["events"] if e["type"] == "gate_denied"]
            self.assertIn("daily_loss_limit", denied[0]["reasons"])
            status = KillSwitch(Path(t) / "HALT").status()
            self.assertTrue(status["engaged"])
            self.assertEqual(status["reason"], "daily_loss_limit")

    def test_pre_engaged_switch_stays_engaged_without_operator_release(self):
        with tempfile.TemporaryDirectory() as t:
            switch = KillSwitch(Path(t) / "HALT")
            switch.engage("prior session", actor="ken")
            r = asyncio.run(native_fixture(t, kill_switch=switch))
            self.assertEqual(r["broker_post_count"], 0)
            self.assertTrue(switch.engaged())


if __name__ == "__main__":
    unittest.main()
