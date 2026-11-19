"""Offline tests of scripts/portfolio.py: combine, trial counting, labels and report (temp roots and ledger)."""
import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from research.control.trial_ledger import read_ledger
from research.evaluation.portfolio import manifest_sha256
from research.evaluation.run_output import config_hash, read_run, write_run
from scripts import portfolio as cli

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
DATES = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2024-01-02", periods=30)]
CLEAN = "abc123"


def _tables(rets, dates=DATES):
    equity, prev = [], 100_000.0
    for r in rets:
        prev *= 1 + r
        equity.append(prev)
    returns = pd.DataFrame({"date": dates, "gross_return": list(map(float, rets)), "cost": 0.0,
                            "net_return": list(map(float, rets)), "equity": equity})
    return {"returns": returns,
            "positions": pd.DataFrame({"date": pd.Series([], dtype=object), "instrument": pd.Series([], dtype=object),
                                       "quantity": pd.Series([], dtype="int64"),
                                       "weight": pd.Series([], dtype="float64")}),
            "signals": pd.DataFrame({"date": pd.Series([], dtype=object), "instrument": pd.Series([], dtype=object),
                                     "stage": pd.Series([], dtype=object), "value": pd.Series([], dtype="float64")}),
            "fills": pd.DataFrame({"date": pd.Series([], dtype=object), "instrument": pd.Series([], dtype=object),
                                   "side": pd.Series([], dtype=object), "quantity": pd.Series([], dtype="int64"),
                                   "price": pd.Series([], dtype="float64"),
                                   "cost": pd.Series([], dtype="float64")})}


def _component(runs: Path, name: str, seed: int, dates=DATES, **extra) -> str:
    rets = np.random.default_rng(seed).normal(0.0005, 0.01, len(dates))
    config = {"name": name}
    manifest = {"run_id": name, "created_utc": NOW.isoformat(), "code_commit": CLEAN, "config": config,
                "config_hash": config_hash(config), "engine": "screening", "engine_version": "t",
                "datasets": {"dataset_id": name}, "coverage": {"instruments": ["X"], "sessions": len(dates)},
                "parent_run": None, **extra}
    write_run(runs, manifest, _tables(rets, dates))
    return name


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.runs = self.root / "runs"
        self.ledger = self.root / "ledger"
        patch = mock.patch.object(cli, "_code_commit", return_value=CLEAN)
        patch.start()
        self.addCleanup(patch.stop)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue().strip(), err.getvalue()

    def combine(self, ids, *extra, method="equal"):
        args = ["combine", "--method", method, "--runs-root", str(self.runs), "--ledger-dir", str(self.ledger),
                "--root", str(self.root)]
        for i in ids:
            args += ["--run-id", i]
        return self.run_cli(*args, *extra)

    def two(self, **extra_b):
        a = _component(self.runs, "comp-a", 1)
        b = _component(self.runs, "comp-b", 2, **extra_b)
        return [a, b]


class CombineTests(Base):
    def test_combine_writes_run_with_combination_manifest(self):
        ids = self.two()
        code, out, err = self.combine(ids, "--exploratory")
        self.assertEqual((code, err), (0, ""))
        manifest, tables = read_run(self.runs / out)
        self.assertEqual(manifest["engine"], "combiner")
        self.assertEqual(manifest["combination"]["components"], ids)
        self.assertEqual(manifest["combination"]["method"], "equal")
        recorded = {c["run_id"]: c["manifest_sha256"] for c in manifest["config"]["components"]}
        for i in ids:
            on_disk = (self.runs / i / "manifest.json").read_bytes()
            import hashlib
            self.assertEqual(recorded[i], hashlib.sha256(on_disk).hexdigest())
        self.assertEqual(len(tables["returns"]), len(DATES))
        self.assertEqual(len(tables["fills"]), 0)

    def test_requires_cycle_id_or_exploratory(self):
        ids = self.two()
        code, _, err = self.combine(ids)
        self.assertEqual(code, 1)
        self.assertIn("exactly one", err)
        code, _, err = self.combine(ids, "--exploratory", "--cycle-id", "C1")
        self.assertEqual(code, 1)
        self.assertIn("exactly one", err)
        self.assertEqual(sorted(p.name for p in self.runs.iterdir()), sorted(ids))  # nothing written
        self.assertEqual(read_ledger(self.ledger).trial_count("C1"), 0)

    def test_trial_recorded_in_ledger_and_manifest(self):
        ids = self.two()
        self.assertEqual(read_ledger(self.ledger).trial_count("C1"), 0)
        code, out, err = self.combine(ids, "--cycle-id", "C1")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(read_ledger(self.ledger).trial_count("C1"), 1)
        manifest, _ = read_run(self.runs / out)
        self.assertEqual(manifest["combination"]["trial"], {"cycle_id": "C1", "trial_number": 1})
        self.assertNotIn("exploratory", manifest["combination"])
        code, out2, _ = self.combine(ids, "--cycle-id", "C1", "--rebalance", "daily")
        self.assertEqual(code, 0)
        self.assertEqual(read_ledger(self.ledger).trial_count("C1"), 2)
        self.assertEqual(read_run(self.runs / out2)[0]["combination"]["trial"]["trial_number"], 2)

    def test_failed_combine_records_no_trial(self):
        a = _component(self.runs, "comp-a", 1)
        b = _component(self.runs, "comp-b", 2, dates=DATES[:-1])
        code, _, err = self.combine([a, b], "--cycle-id", "C1")
        self.assertEqual(code, 1)
        self.assertEqual(read_ledger(self.ledger).trial_count("C1"), 0)

    def test_dirty_tree_refused_for_a_trial_but_recorded_for_exploratory(self):
        ids = self.two()
        with mock.patch.object(cli, "_code_commit", return_value="abc+dirty"):
            code, _, err = self.combine(ids, "--cycle-id", "C1")
            self.assertEqual(code, 1)
            self.assertEqual(read_ledger(self.ledger).trial_count("C1"), 0)
            code, out, _ = self.combine(ids, "--exploratory")
        self.assertEqual(code, 0)
        self.assertEqual(read_run(self.runs / out)[0]["code_commit"], "abc+dirty")

    def test_exploratory_records_no_trial_and_says_so(self):
        ids = self.two()
        code, out, _ = self.combine(ids, "--exploratory")
        self.assertEqual(code, 0)
        manifest, _ = read_run(self.runs / out)
        self.assertIs(manifest["combination"]["exploratory"], True)
        self.assertNotIn("trial", manifest["combination"])
        self.assertFalse((self.ledger / "ledger.jsonl").exists())

    def test_stock_label_inherited(self):
        ids = self.two(labels=["survivor-biased", "discovery-only"], universe_kind="current-constituents")
        _, out, _ = self.combine(ids, "--exploratory")
        manifest, _ = read_run(self.runs / out)
        self.assertEqual(manifest["labels"], ["discovery-only", "survivor-biased"])
        self.assertEqual(manifest["universe_kind"], "current-constituents")
        self.assertEqual(manifest["use"], "engineering")

    def test_engineering_plus_financial_is_engineering(self):
        fin = {"use": "financial", "acceptance_sha256": "f" * 64}
        a = _component(self.runs, "comp-a", 1, **fin)
        b = _component(self.runs, "comp-b", 2)
        _, out, _ = self.combine([a, b], "--exploratory")
        self.assertEqual(read_run(self.runs / out)[0]["use"], "engineering")
        c = _component(self.runs, "comp-c", 3, **fin)
        _, out2, _ = self.combine([a, c], "--exploratory")
        self.assertEqual(read_run(self.runs / out2)[0]["use"], "financial")

    def test_missing_run_and_tampered_manifest_rejected_naming_component(self):
        ids = self.two()
        code, _, err = self.combine([ids[0], "no-such-run"], "--exploratory")
        self.assertEqual(code, 1)
        self.assertIn("no-such-run", err)
        path = self.runs / ids[1] / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["config"]["name"] = "tampered"
        path.write_text(json.dumps(manifest, sort_keys=True, indent=2))
        code, _, err = self.combine(ids, "--exploratory")
        self.assertEqual(code, 1)
        self.assertIn(ids[1], err)
        self.assertEqual(sorted(p.name for p in self.runs.iterdir()), sorted(ids))

    def test_tampered_table_rejected_naming_component(self):
        ids = self.two()
        with open(self.runs / ids[0] / "returns.parquet", "ab") as stream:
            stream.write(b"x")
        code, _, err = self.combine(ids, "--exploratory")
        self.assertEqual(code, 1)
        self.assertIn(ids[0], err)


class ReportTests(Base):
    def make(self, method="equal", *extra):
        ids = ["comp-a", "comp-b"] if (self.runs / "comp-a").exists() else self.two()
        _, out, _ = self.combine(ids, "--exploratory", "--vol-window", "5", *extra, method=method)
        return ids, out

    def test_report_has_metrics_correlation_diversification_and_reconciliation(self):
        for method in ("equal", "inverse_vol"):
            ids, run_id = self.make(method, *(["--rebalance", "daily"] if method == "inverse_vol" else []))
            code, out, err = self.run_cli("report", "--run-id", run_id, "--runs-root", str(self.runs),
                                          "--root", str(self.root))
            self.assertEqual((code, err), (0, ""))
            path = self.root / "portfolio" / run_id / "report.json"
            self.assertEqual(Path(out), path)
            report = json.loads(path.read_text())
            self.assertEqual(report["schema"], "portfolio-report/v1")
            self.assertEqual(report["components"], ids)
            self.assertEqual(set(report["metrics"]["sleeves"]), set(ids))
            self.assertIn("sharpe", report["metrics"]["combined"])
            matrix = np.array(report["correlation"]["matrix"])
            np.testing.assert_allclose(np.diag(matrix), 1.0)
            self.assertEqual(matrix.shape, (2, 2))
            div = report["diversification"]
            self.assertGreater(div["diversification_ratio"], 1.0)  # imperfectly correlated sleeves
            self.assertAlmostEqual(sum(div["weights"]), 1.0)
            self.assertAlmostEqual(div["risk_contribution_sum"], 1.0, delta=0.15)  # weights drift from the first rebalance
            self.assertEqual(report["reconciliation"]["status"], "PASS")
            self.assertLessEqual(report["reconciliation"]["max_abs_return_error"], 1e-12)
            self.assertTrue(report["exploratory"])
            self.assertIsNone(report["trial"])
            self.assertEqual(report["use"], "engineering")
            self.assertTrue(any("sleeve-level" in s.lower() for s in report["limitations"]))
            self.assertTrue(any("cash earns zero" in s.lower() for s in report["limitations"]))

    def test_report_carries_labels_and_trial(self):
        a = _component(self.runs, "comp-a", 1, labels=["survivor-biased"], universe_kind="current-constituents")
        b = _component(self.runs, "comp-b", 2)
        _, run_id, _ = self.combine([a, b], "--cycle-id", "C9")
        self.run_cli("report", "--run-id", run_id, "--runs-root", str(self.runs), "--root", str(self.root))
        report = json.loads((self.root / "portfolio" / run_id / "report.json").read_text())
        self.assertEqual(report["labels"], ["survivor-biased"])
        self.assertEqual(report["trial"], {"cycle_id": "C9", "trial_number": 1})
        self.assertFalse(report["exploratory"])

    def test_report_is_exclusive(self):
        _, run_id = self.make()
        argv = ["report", "--run-id", run_id, "--runs-root", str(self.runs), "--root", str(self.root)]
        self.assertEqual(self.run_cli(*argv)[0], 0)
        path = self.root / "portfolio" / run_id / "report.json"
        before = path.read_bytes()
        code, _, err = self.run_cli(*argv)
        self.assertEqual(code, 1)
        self.assertIn("already exists", err)
        self.assertEqual(path.read_bytes(), before)

    def test_report_rejects_tampered_component_naming_it(self):
        ids, run_id = self.make()
        path = self.runs / ids[0] / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["code_commit"] = "other"  # still a valid run, but not the one the combination recorded
        path.write_text(json.dumps(manifest, sort_keys=True, indent=2))
        code, _, err = self.run_cli("report", "--run-id", run_id, "--runs-root", str(self.runs),
                                    "--root", str(self.root))
        self.assertEqual(code, 1)
        self.assertIn(ids[0], err)
        self.assertFalse((self.root / "portfolio" / run_id / "report.json").exists())

    def test_report_on_a_non_combination_run_errors(self):
        ids = self.two()
        code, _, err = self.run_cli("report", "--run-id", ids[0], "--runs-root", str(self.runs),
                                    "--root", str(self.root))
        self.assertEqual(code, 1)
        self.assertIn("not a combination", err)


if __name__ == "__main__":
    unittest.main()
