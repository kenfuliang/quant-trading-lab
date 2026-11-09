import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from paper_trading.alpaca_fixture import native_fixture


def run(**kwargs):
    with tempfile.TemporaryDirectory() as t:
        result = asyncio.run(native_fixture(t, **kwargs))
        return result, json.loads((Path(t) / "journal.json").read_text())


class NativeFailureModeTests(unittest.TestCase):
    def test_reject_is_recorded_and_halts_without_resubmitting(self):
        result, journal = run(mode="reject")
        self.assertEqual(journal[0]["status"], "rejected")
        self.assertIn({"type": "terminal_halt", "state": "rejected"}, result["events"])
        self.assertEqual(result["broker_post_count"], 1)
        self.assertEqual(result["native_fills"], 0)
        self.assertFalse(result["unknown"])

    def test_expire_clears_the_working_order_without_a_fill(self):
        result, journal = run(mode="expire")
        self.assertEqual(journal[0]["status"], "expired")
        self.assertEqual(result["broker_post_count"], 1)
        self.assertIn({"type": "terminal_halt", "state": "expired"}, result["events"])
        self.assertEqual(result["native_fills"], 0)
        self.assertEqual(Decimal_pos(result), 0)

    def test_disconnect_after_submit_marks_unknown_and_never_retries(self):
        result, journal = run(mode="poll_fail")
        self.assertTrue(result["unknown"])
        self.assertEqual(journal[0]["status"], "reconciliation_required")
        self.assertEqual(result["broker_post_count"], 1)
        self.assertEqual(result["broker_delete_count"], 0)

    def test_unfilled_order_is_cancelled_by_id_then_halts_unconfirmed(self):
        result, journal = run(mode="stuck")
        self.assertTrue(result["unknown"])
        self.assertEqual(journal[0]["status"], "cancel_requested_unconfirmed")
        self.assertEqual(result["broker_delete_count"], 1)
        self.assertEqual(result["broker_post_count"], 1)

    def test_cancel_failure_halts_for_reconciliation(self):
        result, journal = run(mode="stuck_cancel_fails")
        self.assertTrue(result["unknown"])
        self.assertEqual(journal[0]["status"], "reconciliation_required")
        self.assertEqual(result["broker_post_count"], 1)

    def test_slow_ack_then_fill_completes_without_duplicate(self):
        result, journal = run(mode="slow")
        self.assertEqual(result["native_fills"], 1)
        self.assertEqual(result["broker_post_count"], 1)
        self.assertFalse(result["unknown"])
        self.assertEqual(journal[0]["status"], "filled")


def Decimal_pos(result):
    from decimal import Decimal
    return Decimal(result["ending_native_position"])


if __name__ == "__main__":
    unittest.main()
