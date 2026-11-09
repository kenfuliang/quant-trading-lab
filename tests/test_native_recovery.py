import asyncio
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from paper_trading.alpaca_fixture import FakePaper, native_fixture
from paper_trading.alpaca_native import Context
from paper_trading.kill_switch import KillSwitch
from paper_trading.recovery import OrderNotFound, RecoveryError, recover


def entry(client, status, side="buy"):
    return {"client_order_id": client, "side": side, "status": status}


def order(client, status, filled="0", side="buy", symbol="SPY"):
    return {"client_order_id": client, "symbol": symbol, "side": side, "status": status,
            "filled_qty": filled, "filled_avg_price": "100.00"}


class Broker:
    def __init__(self, answers):
        self.answers, self.calls = answers, []

    def by_client_id(self, client):
        self.calls.append(client)
        answer = self.answers[client]
        if isinstance(answer, Exception):
            raise answer
        return answer


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "journal.json"

    def write(self, entries):
        self.path.write_text(json.dumps(entries))

    def status(self):
        return json.loads(self.path.read_text())[0]["status"]

    def test_crash_between_journal_and_post_resolves_never_sent_and_keeps_slot(self):
        self.write([entry("a", "reserved")])
        report = recover(self.path, Broker({"a": OrderNotFound()}))
        self.assertFalse(report.halt)
        self.assertEqual(self.status(), "never_sent")
        self.assertEqual((report.submissions, report.position), (1, 0))

    def test_unacknowledged_entry_with_unknown_broker_error_stays_unresolved(self):
        self.write([entry("a", "reserved")])
        report = recover(self.path, Broker({"a": ConnectionError("down")}))
        self.assertTrue(report.halt)
        self.assertEqual(self.status(), "reserved")

    def test_not_found_for_an_acknowledged_order_is_not_trusted(self):
        self.write([entry("a", "accepted")])
        self.assertTrue(recover(self.path, Broker({"a": OrderNotFound()})).halt)
        self.assertEqual(self.status(), "accepted")

    def test_crash_after_post_before_ack_finds_fill_and_updates_position(self):
        self.write([entry("a", "reserved")])
        report = recover(self.path, Broker({"a": order("a", "filled", "1")}))
        self.assertFalse(report.halt)
        self.assertEqual(self.status(), "filled")
        self.assertEqual(report.position, Decimal(1))

    def test_working_or_partial_order_halts(self):
        for status, filled in [("new", "0"), ("partially_filled", "0.5")]:
            with self.subTest(status=status):
                self.write([entry("a", "unknown_submission")])
                report = recover(self.path, Broker({"a": order("a", status, filled)}))
                self.assertTrue(report.halt)
                self.assertEqual(self.status(), "unknown_submission")

    def test_identity_mismatch_halts(self):
        for bad in [order("other", "filled", "1"), order("a", "filled", "1", side="sell"),
                    order("a", "filled", "1", symbol="QQQ"), order("a", "filled", "2")]:
            with self.subTest(bad=bad):
                self.write([entry("a", "reconciliation_required")])
                self.assertTrue(recover(self.path, Broker({"a": bad})).halt)

    def test_terminal_entries_are_not_requeried_and_recovery_is_idempotent(self):
        self.write([entry("a", "reserved")])
        broker = Broker({"a": order("a", "rejected")})
        recover(self.path, broker)
        again = recover(self.path, broker)
        self.assertEqual(broker.calls, ["a"])
        self.assertFalse(again.halt)

    def test_corrupt_or_misshapen_journal_fails_closed(self):
        self.path.write_text("garbage")
        with self.assertRaises(RecoveryError):
            recover(self.path, Broker({}))
        self.write([{"status": "reserved"}])
        with self.assertRaises(RecoveryError):
            recover(self.path, Broker({}))

    def test_missing_journal_is_an_empty_clean_start(self):
        report = recover(self.path, Broker({}))
        self.assertEqual((report.halt, report.submissions), (False, 0))


class NativeRecoveryTests(unittest.TestCase):
    def test_recovered_fill_blocks_a_duplicate_buy_after_restart(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "prior.json"
            path.write_text(json.dumps([entry("a", "reserved")]))
            report = recover(path, Broker({"a": order("a", "filled", "1")}))
            result = asyncio.run(native_fixture(Path(t) / "run", denied=True, recovery=report))
            self.assertEqual(result["broker_post_count"], 0)
            self.assertIn("policy_rejected", [e["type"] for e in result["events"]])

    def test_unresolved_intent_halts_and_nothing_is_submitted(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "prior.json"
            path.write_text(json.dumps([entry("a", "accepted")]))
            report = recover(path, Broker({"a": ConnectionError("down")}))
            result = asyncio.run(native_fixture(Path(t) / "run", recovery=report))
            self.assertEqual(result["broker_post_count"], 0)
            self.assertTrue(result["unknown"])
            self.assertIn("recovery_halt", [e["type"] for e in result["events"]])

    def test_recovered_history_is_kept_when_new_entries_are_saved(self):
        with tempfile.TemporaryDirectory() as t:
            ctx = Context(FakePaper(), Path(t) / "run", fake=True, kill_switch=KillSwitch(Path(t) / "HALT"))
            path = Path(t) / "prior.json"
            path.write_text(json.dumps([entry("a", "filled")]))
            ctx.apply_recovery(recover(path, Broker({})))
            self.assertEqual([e["client_order_id"] for e in ctx.journal], ["a"])
            self.assertEqual((ctx.submissions, ctx.position), (1, Decimal(1)))


if __name__ == "__main__":
    unittest.main()
