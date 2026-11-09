"""Shadow collection and tracking error on invented bars. No network, broker or orders."""
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from paper_trading.shadow import DecisionStore, assert_shadow_record, build_decisions, parse_spy_closes
from paper_trading.spy_signal import target_series
from paper_trading.tracking_error import tracking_error
from scripts import spy_shadow_run

ROOT = Path(__file__).resolve().parents[1]
FAST, SLOW = 3, 8
N = 60


def dates(n=N):
    return list(pd.bdate_range("2024-01-02", periods=n).strftime("%Y-%m-%d"))


def closes(n=N):
    t = np.arange(n)
    return dict(zip(dates(n), np.round(100 + 10 * np.sin(t / 5) + t * .05, 2)))


def pages(values):
    bars = [{"t": pd.Timestamp(d, tz="America/New_York").tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"), "o": c, "h": c + 1, "l": c - 1, "c": c, "v": 1000}
            for d, c in values.items()]
    return [{"bars": {"SPY": bars}}]


def replay(values, fast=FAST, slow=SLOW):
    ds = list(values)
    signal = target_series(list(values.values()), fast, slow)
    return [{"date": d, "target_position": p} for d, p in zip(ds[1:], signal[:-1])]


class ShadowTests(unittest.TestCase):
    def test_records_have_no_order_fields(self):
        records = build_decisions(closes(), days=10, fast=FAST, slow=SLOW)
        self.assertEqual(len(records), 10)
        self.assertIsNone(records[-1]["session"])
        for r in records:
            assert_shadow_record(r)
            self.assertEqual(r["record_origin"], "shadow")
        with self.assertRaises(ValueError):
            assert_shadow_record(records[0] | {"side": "BUY"})
        with self.assertRaises(ValueError):
            assert_shadow_record(records[0] | {"client_order_id": "x"})

    def test_parse_rejects_bad_bars(self):
        good = pages(closes(3))
        parse_spy_closes(good)
        with self.assertRaises(ValueError):
            parse_spy_closes(good + good)
        with self.assertRaises(ValueError):
            parse_spy_closes([{"bars": {"QQQ": []}}])
        bad = pages(closes(3))
        bad[0]["bars"]["SPY"][0]["l"] = 10_000
        with self.assertRaises(ValueError):
            parse_spy_closes(bad)

    def test_tracking_error_zero_for_identical_inputs(self):
        values = closes()
        records = build_decisions(values, days=30, fast=FAST, slow=SLOW)
        report = tracking_error(records, replay(values))
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["tracking_error"], 0)
        self.assertGreater(report["compared_days"], 20)

    def test_mismatch_and_missing_days_are_flagged(self):
        values = closes()
        records = build_decisions(values, days=30, fast=FAST, slow=SLOW)
        rows = replay(values)
        flipped = [dict(r) for r in rows]
        flipped[-5]["target_position"] ^= 1
        report = tracking_error(records, flipped)
        self.assertEqual(report["status"], "flagged")
        self.assertEqual(report["mismatch_days"], [flipped[-5]["date"]])
        dropped = [r for r in records if r["session"] != rows[-10]["date"]]
        report = tracking_error(dropped, rows)
        self.assertEqual(report["status"], "flagged")
        self.assertEqual(report["missing_in_shadow"], [rows[-10]["date"]])
        report = tracking_error(records, rows[:-3])
        self.assertEqual(len(report["missing_in_replay"]), 3)

    def test_store_is_idempotent_and_refuses_history_rewrites(self):
        values = closes()
        with tempfile.TemporaryDirectory() as tmp:
            store = DecisionStore(Path(tmp) / "decisions.jsonl")
            records = build_decisions(values, days=10, fast=FAST, slow=SLOW)
            self.assertEqual(store.add(records)["added"], 10)
            before = store.path.read_bytes()
            self.assertEqual(store.add(records), {"added": 0, "unchanged": 10, "resolved": 0})
            self.assertEqual(store.path.read_bytes(), before)
            extended = dict(values)
            extended["2024-03-26"] = 101.0
            later = build_decisions(extended, days=10, fast=FAST, slow=SLOW)
            counts = store.add(later)
            self.assertEqual(counts["resolved"], 1)
            self.assertEqual(len(store.load()), 11)
            with self.assertRaises(ValueError):
                store.add([records[0] | {"hypothetical_position": 1 - records[0]["hypothetical_position"]}])

    def test_same_day_rerun_adds_nothing(self):
        values = closes()
        rows = replay(values)
        with tempfile.TemporaryDirectory() as tmp:
            first = spy_shadow_run.run(pages(values), rows, tmp, datetime(2024, 4, 1, 3, tzinfo=timezone.utc), days=30, fast=FAST, slow=SLOW)
            second = spy_shadow_run.run(pages(values), rows, tmp, datetime(2024, 4, 1, 4, tzinfo=timezone.utc), days=30, fast=FAST, slow=SLOW)
            self.assertEqual(first["status"], "completed", first)
            self.assertEqual(second["store"]["added"], 0)
            self.assertEqual(second["store"]["unchanged"], first["store"]["added"])
            lines = (Path(tmp) / "decisions.jsonl").read_text().splitlines()
            self.assertEqual(len(lines), len(set(lines)))
            manifest = json.loads((Path(second["run_dir"]) / "manifest.json").read_text())
            self.assertIn("plan.json", manifest["files"])
            self.assertIn("summary.json", manifest["files"])
            redacted = json.dumps(spy_shadow_run.redacted_summary(second))
            self.assertNotIn("fast_ema", redacted)
            self.assertNotIn(tmp, redacted)

    def test_run_flags_missing_day_and_preserves_failure(self):
        values = closes()
        rows = [r for r in replay(values) if r["date"] != dates()[-6]]
        with tempfile.TemporaryDirectory() as tmp:
            flagged = spy_shadow_run.run(pages(values), rows, tmp, datetime(2024, 4, 1, 3, tzinfo=timezone.utc), days=30, fast=FAST, slow=SLOW)
            self.assertEqual(flagged["status"], "completed_flagged")
            self.assertEqual(flagged["tracking"]["missing_in_replay"], 1)
            failed = spy_shadow_run.run([{"bars": {}}], rows, tmp, datetime(2024, 4, 1, 5, tzinfo=timezone.utc), fast=FAST, slow=SLOW)
            self.assertEqual(failed["status"], "failed_preserved")
            self.assertTrue((Path(failed["run_dir"]) / "summary.json").exists())


class NoOrderPathTests(unittest.TestCase):
    FILES = ("scripts/spy_shadow_run.py", "paper_trading/shadow.py",
             "paper_trading/tracking_error.py", "paper_trading/spy_signal.py")
    FORBIDDEN_MODULES = ("paper_trading.alpaca", "paper_trading.alpaca_native", "paper_trading.alpaca_fixture",
                         "paper_trading.gateway", "paper_trading.node", "paper_trading.t11_pilot",
                         "nautilus_trader", "requests", "httpx", "ib_insync", "alpaca")
    FORBIDDEN_STRINGS = {"POST", "PUT", "DELETE", "PATCH"}
    FORBIDDEN_NAMES = {"submit_order", "submit", "order_factory", "place_order"}

    def test_runner_and_shadow_modules_have_no_order_path(self):
        for name in self.FILES:
            tree = ast.parse((ROOT / name).read_text())
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    modules = [node.module or ""]
                    modules += [f"{node.module}.{a.name}" for a in node.names]
                for module in modules:
                    self.assertFalse(any(module == f or module.startswith(f + ".") for f in self.FORBIDDEN_MODULES),
                                     f"{name} imports {module}")
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    self.assertNotIn(node.value.upper(), self.FORBIDDEN_STRINGS, name)
                ident = node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else None
                self.assertNotIn(ident, self.FORBIDDEN_NAMES, name)

    def test_only_get_requests_to_allowlisted_endpoint(self):
        tree = ast.parse((ROOT / "scripts/spy_shadow_run.py").read_text())
        methods = [k.value.value for n in ast.walk(tree) if isinstance(n, ast.Call)
                   for k in n.keywords if k.arg == "method"]
        self.assertEqual(methods, ["GET"])
        self.assertEqual(spy_shadow_run.BARS_ENDPOINT, ("https://data.alpaca.markets", "/v2/stocks/bars"))


if __name__ == "__main__":
    unittest.main()
