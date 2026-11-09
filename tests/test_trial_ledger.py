"""Synthetic trial-ledger checks only: local temp files, no network or broker."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from research.control.trial_ledger import (
    EXPOSURE_PROTECTED, EXPOSURE_VIEWED, LedgerError, TrialLedger, read_ledger)

PLAN = "a" * 64


class TrialLedgerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name) / "ledger"

    def sealed(self, ledger, holdout="h1"):
        return ledger.seal(holdout, "2026-01-01", "2026-06-30", "synthetic holdout")

    def test_read_refused_until_frozen_then_logged(self):
        with TrialLedger(self.dir) as ledger:
            self.sealed(ledger)
            with self.assertRaises(LedgerError):
                ledger.open("h1", "c1", "tester", "before freeze")
            self.assertEqual(ledger.view.access_count("h1"), 0)
            ledger.freeze("h1", PLAN, "frozen")
            ledger.open("h1", "c1", "tester", "after freeze")
            self.assertEqual(ledger.view.access_count("h1"), 1)
        self.assertEqual([e["kind"] for e in read_ledger(self.dir).opens("h1")], ["open"])

    def test_unknown_holdout_and_double_freeze_refused(self):
        with TrialLedger(self.dir) as ledger:
            with self.assertRaises(LedgerError):
                ledger.freeze("nope", PLAN, "x")
            self.sealed(ledger)
            with self.assertRaises(LedgerError):
                self.sealed(ledger)
            ledger.freeze("h1", PLAN, "x")
            with self.assertRaises(LedgerError):
                ledger.freeze("h1", PLAN, "x")

    def test_chain_tamper_detected(self):
        with TrialLedger(self.dir) as ledger:
            self.sealed(ledger)
            ledger.trial("c1", "first")
        log = self.dir / "ledger.jsonl"
        log.write_bytes(log.read_bytes().replace(b"synthetic holdout", b"changed holdout!"))
        with self.assertRaises(LedgerError):
            read_ledger(self.dir)
        with self.assertRaises(LedgerError):
            TrialLedger(self.dir)

    def test_tail_truncation_detected(self):
        with TrialLedger(self.dir) as ledger:
            self.sealed(ledger)
            ledger.trial("c1", "first")
            ledger.trial("c1", "second")
        log = self.dir / "ledger.jsonl"
        log.write_bytes(b"".join(log.read_bytes().splitlines(keepends=True)[:-2]))
        with self.assertRaises(LedgerError):
            read_ledger(self.dir)

    def test_second_writer_blocked(self):
        with TrialLedger(self.dir):
            with self.assertRaises(LedgerError):
                TrialLedger(self.dir)
        TrialLedger(self.dir).close()  # released on close

    def test_crash_between_log_and_head_resumes(self):
        ledger = TrialLedger(self.dir)
        with mock.patch.object(TrialLedger, "_write_head", side_effect=RuntimeError("crash")):
            with self.assertRaises(RuntimeError):
                self.sealed(ledger)
        ledger.close()
        self.assertTrue(read_ledger(self.dir).head_lag)
        with TrialLedger(self.dir) as resumed:
            self.assertFalse(read_ledger(self.dir).head_lag)
            self.assertEqual(resumed.view.exposure("h1"), EXPOSURE_PROTECTED)
            resumed.freeze("h1", PLAN, "after crash")
        self.assertEqual(len(read_ledger(self.dir).events), 2)

    def test_torn_tail_is_dropped_on_resume(self):
        with TrialLedger(self.dir) as ledger:
            self.sealed(ledger)
        with open(self.dir / "ledger.jsonl", "ab") as stream:
            stream.write(b'{"sequence":2,"previous_')
        self.assertTrue(read_ledger(self.dir).torn_tail)
        with TrialLedger(self.dir) as resumed:
            self.assertEqual(resumed.trial("c1", "after torn tail"), 1)
        view = read_ledger(self.dir)
        self.assertFalse(view.torn_tail)
        self.assertEqual(len(view.events), 2)

    def test_seal_then_view_marks_previously_viewed(self):
        with TrialLedger(self.dir) as ledger:
            self.sealed(ledger)
            self.assertEqual(ledger.view.exposure("h1"), EXPOSURE_PROTECTED)
            ledger.freeze("h1", PLAN, "frozen")
            self.assertEqual(ledger.view.exposure("h1"), EXPOSURE_PROTECTED)
            ledger.open("h1", "c1", "tester", "single read")
            self.assertEqual(ledger.view.exposure("h1"), EXPOSURE_VIEWED)
        self.assertEqual(read_ledger(self.dir).exposure("h1"), EXPOSURE_VIEWED)

    def test_trial_count_monotonic_across_reopen(self):
        with TrialLedger(self.dir) as ledger:
            self.assertEqual([ledger.trial("c1", "a"), ledger.trial("c1", "b"),
                              ledger.trial("c2", "x")], [1, 2, 1])
        with TrialLedger(self.dir) as ledger:
            self.assertEqual(ledger.trial("c1", "c"), 3)
        view = read_ledger(self.dir)
        self.assertEqual((view.trial_count("c1"), view.trial_count("c2"), view.trial_count("c3")),
                         (3, 1, 0))

    def test_replayed_or_skipped_trial_number_rejected(self):
        with TrialLedger(self.dir) as ledger:
            ledger.trial("c1", "a")
            with self.assertRaises(LedgerError):
                ledger._append("trial", {"cycle_id": "c1", "trial_number": 1, "description": "dup"})
            with self.assertRaises(LedgerError):
                ledger._append("trial", {"cycle_id": "c1", "trial_number": 3, "description": "gap"})

    def test_missing_ledger_reads_empty(self):
        view = read_ledger(self.dir / "absent")
        self.assertEqual((len(view.events), view.trial_count("c1")), (0, 0))

    def test_records_are_plain_json(self):
        with TrialLedger(self.dir) as ledger:
            self.sealed(ledger)
        line = (self.dir / "ledger.jsonl").read_text().splitlines()[0]
        self.assertEqual(json.loads(line)["event"]["kind"], "seal")


if __name__ == "__main__":
    unittest.main()
