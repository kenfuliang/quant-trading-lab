"""The health view must read what the repo's real producers write, not only fixtures."""
from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from paper_trading.durable_journal import atomic_write_json
from paper_trading.health import HealthConfig, collect
from paper_trading.kill_switch import KillSwitch
from scripts import spy_shadow_run

NOW = datetime(2024, 4, 1, 15, 0, tzinfo=timezone.utc)


def pages(n=60):
    dates = pd.bdate_range("2024-01-02", periods=n)
    closes = np.round(100 + 10 * np.sin(np.arange(n) / 5) + np.arange(n) * .05, 2)
    bars = [{"t": pd.Timestamp(d, tz="America/New_York").tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
             "o": c, "h": c + 1, "l": c - 1, "c": c, "v": 1000} for d, c in zip(dates, closes)]
    return [{"bars": {"SPY": bars}}]


class RealProducerHealthTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def check(self, **kw):
        report = collect(HealthConfig(root=self.root, now=kw.pop("now", NOW), **kw))
        return report, {c["name"]: c for c in report["checks"]}

    def shadow(self, at):
        return spy_shadow_run.run(pages(), None, self.root / "shadow", at, days=10, fast=3, slow=8)

    def test_real_shadow_run_is_fresh_and_feeds_the_data_check(self):
        self.shadow(NOW - timedelta(hours=1))
        _, checks = self.check()
        self.assertEqual(checks["shadow"]["state"], "fresh")
        self.assertIn(checks["data"]["state"], ("fresh", "stale"))  # fixture dates are old; not 'missing'
        self.assertNotEqual(checks["data"]["state"], "missing")

    def test_old_real_shadow_run_is_stale(self):
        self.shadow(NOW - timedelta(hours=100))
        _, checks = self.check()
        self.assertEqual(checks["shadow"]["state"], "stale")

    def test_failed_real_shadow_run_is_unhealthy(self):
        spy_shadow_run.run([{"bars": {}}], None, self.root / "shadow", NOW - timedelta(hours=1))
        _, checks = self.check()
        self.assertFalse(checks["shadow"]["healthy"])
        self.assertEqual(checks["shadow"]["state"], "failed")

    def test_real_kill_switch_sentinel_is_engaged_until_released(self):
        switch = KillSwitch(self.root / "kill-switch" / "HALT")
        switch.engage("manual", actor="ken")
        _, checks = self.check()
        self.assertEqual(checks["kill_switch"]["state"], "engaged")
        switch.release("ken", "reviewed")
        _, checks = self.check()
        self.assertEqual(checks["kill_switch"]["state"], "released")

    def test_unreadable_real_sentinel_counts_as_engaged(self):
        sentinel = self.root / "kill-switch" / "HALT"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("garbage")
        _, checks = self.check()
        self.assertFalse(checks["kill_switch"]["healthy"])
        self.assertIn("unreadable", checks["kill_switch"]["detail"])

    def journal(self, status):
        run = self.root / "alpaca-paper" / "runs" / "r1"
        run.mkdir(parents=True, exist_ok=True)
        atomic_write_json(run / "journal.json", [{"client_order_id": "a", "side": "buy", "status": status}])

    def test_real_journal_states_map_to_health(self):
        for status, healthy in [("filled", True), ("rejected", True), ("never_sent", True),
                                ("accepted", True), ("unknown_submission", False),
                                ("reconciliation_required", False), ("cancel_requested_unconfirmed", False)]:
            with self.subTest(status=status):
                self.journal(status)
                _, checks = self.check()
                self.assertEqual(checks["journal"]["healthy"], healthy, checks["journal"])

    def test_old_reserved_entry_is_stuck(self):
        self.journal("reserved")
        _, checks = self.check(now=datetime.now(timezone.utc) + timedelta(hours=1))
        self.assertEqual(checks["journal"]["state"], "stuck")

    def test_unknown_journal_status_fails_closed(self):
        self.journal("mystery")
        _, checks = self.check()
        self.assertEqual(checks["journal"]["state"], "unreadable")


if __name__ == "__main__":
    unittest.main()
