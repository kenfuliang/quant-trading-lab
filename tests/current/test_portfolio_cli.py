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
from scripts import portfolio_repro

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
DATES = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2024-01-02", periods=30)]
CLEAN = "abc123"


def _fills(dates):
    n = 6
    return pd.DataFrame({"date": dates[:n], "instrument": ["X"] * n, "side": ["buy", "sell"] * (n // 2),
                         "quantity": [10] * n, "price": [100.0] * n, "cost": [1.0] * n})


def _tables(rets, dates=DATES, with_fills=False):
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
            "fills": _fills(dates) if with_fills else
            pd.DataFrame({"date": pd.Series([], dtype=object), "instrument": pd.Series([], dtype=object),
                          "side": pd.Series([], dtype=object), "quantity": pd.Series([], dtype="int64"),
                          "price": pd.Series([], dtype="float64"), "cost": pd.Series([], dtype="float64")})}


def _component(runs: Path, name: str, seed: int, dates=DATES, with_fills=False, **extra) -> str:
    rets = np.random.default_rng(seed).normal(0.0005, 0.01, len(dates))
    config = {"name": name}
    manifest = {"run_id": name, "created_utc": NOW.isoformat(), "code_commit": CLEAN, "config": config,
                "config_hash": config_hash(config), "engine": "screening", "engine_version": "t",
                "datasets": {"dataset_id": name}, "coverage": {"instruments": ["X"], "sessions": len(dates)},
                "parent_run": None, **extra}
    write_run(runs, manifest, _tables(rets, dates, with_fills))
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

    def report(self, run_id, stamp="20261118T120000Z"):
        with mock.patch.object(cli, "_now", return_value=datetime.strptime(stamp, "%Y%m%dT%H%M%SZ")
                               .replace(tzinfo=timezone.utc)):
            return self.run_cli("report", "--run-id", run_id, "--runs-root", str(self.runs), "--root", str(self.root))

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
            code, out, err = self.report(run_id)
            self.assertEqual((code, err), (0, ""))
            path = self.root / "portfolio" / run_id / "20261118T120000Z" / "report.json"
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
            self.assertAlmostEqual(div["risk_contribution_sum"], 1.0, places=12)  # actual start weights: exact
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
        self.report(run_id)
        report = json.loads((self.root / "portfolio" / run_id / "20261118T120000Z" / "report.json").read_text())
        self.assertEqual(report["labels"], ["survivor-biased"])
        self.assertEqual(report["trial"], {"cycle_id": "C9", "trial_number": 1})
        self.assertFalse(report["exploratory"])

    def test_report_is_exclusive_per_timestamp_and_tolerates_old_layout(self):
        _, run_id = self.make()
        folder = self.root / "portfolio" / run_id
        folder.mkdir(parents=True)
        (folder / "report.json").write_text("old history\n")  # the previous flat layout stays untouched
        self.assertEqual(self.report(run_id)[0], 0)
        path = folder / "20261118T120000Z" / "report.json"
        before = path.read_bytes()
        code, _, err = self.report(run_id)  # same second: exclusive
        self.assertEqual(code, 1)
        self.assertIn("already exists", err)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.report(run_id, "20261118T120001Z")[0], 0)  # a later report is a new file
        self.assertEqual((folder / "report.json").read_text(), "old history\n")

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
        self.assertFalse((self.root / "portfolio" / run_id).exists())

    def test_report_on_a_non_combination_run_errors(self):
        ids = self.two()
        code, _, err = self.run_cli("report", "--run-id", ids[0], "--runs-root", str(self.runs),
                                    "--root", str(self.root))
        self.assertEqual(code, 1)
        self.assertIn("not a combination", err)

    def test_sleeve_metrics_use_real_fills_and_combined_reports_rebalance_turnover(self):
        a = _component(self.runs, "comp-a", 1, with_fills=True)
        b = _component(self.runs, "comp-b", 2)
        _, run_id, _ = self.combine([a, b], "--exploratory")
        self.report(run_id)
        report = json.loads((self.root / "portfolio" / run_id / "20261118T120000Z" / "report.json").read_text())
        sleeves = report["metrics"]["sleeves"]
        self.assertGreater(sleeves[a]["turnover"], 0.0)   # real fills: 6 x 10 x $100
        self.assertEqual(sleeves[b]["turnover"], 0.0)     # genuinely no fills
        combined = report["metrics"]["combined"]
        self.assertIsNone(combined["turnover"])
        self.assertIn("rebalance", combined["turnover_note"])
        # Monthly rebalances: all-cash start (1.0) plus small drift resets; strictly positive, per year.
        self.assertGreater(combined["rebalance_turnover_per_year"], 1.0 / (len(DATES) / 252) - 1e-9)

    def test_sleeve_initial_cash_from_config_else_first_equity(self):
        returns = pd.DataFrame({"date": ["d"], "gross_return": [0.1], "cost": [0.0], "net_return": [0.1],
                                "equity": [55_000.0]})
        sleeve = cli.Sleeve("s", {"config": {"market": {"initial_cash": 50_000.0}}}, returns)
        self.assertEqual(cli._sleeve_initial_cash(sleeve, 1.0), 50_000.0)
        sleeve = cli.Sleeve("s", {"config": {}}, returns)
        self.assertAlmostEqual(cli._sleeve_initial_cash(sleeve, 1.0), 50_000.0)

    def test_diversification_describes_the_weights_actually_used(self):
        rng = np.random.default_rng(2)
        n = 200
        r = pd.DataFrame({"A": rng.normal(0, 0.01, n), "B": rng.normal(0, 0.02, n), "C": rng.normal(0, 0.015, n)})
        w = np.tile([0.2, 0.5, 0.3], (n, 1))
        w[n // 2:] = [0.6, 0.1, 0.3]  # re-targeted half way
        gross = pd.Series((w * r.to_numpy()).sum(axis=1))
        d = cli.diversification(r, gross, w)
        self.assertAlmostEqual(d["risk_contribution_sum"], 1.0, places=12)
        np.testing.assert_allclose(d["weights"], w.mean(axis=0))
        expected = float((w.mean(axis=0) * r.std(ddof=1).to_numpy()).sum() / gross.std(ddof=1))
        self.assertAlmostEqual(d["diversification_ratio"], expected, places=12)
        # Constant weights reduce to the first-rebalance formula (equal weight is numerically unchanged).
        c = np.full((n, 3), 1 / 3)
        g = pd.Series(r.to_numpy() @ np.full(3, 1 / 3))
        d = cli.diversification(r, g, c)
        old = float((np.full(3, 1 / 3) * r.std(ddof=1).to_numpy()).sum() / g.std(ddof=1))
        self.assertAlmostEqual(d["diversification_ratio"], old, places=12)

    def test_stock_class_component_without_labels_is_refused_before_a_trial(self):
        a = _component(self.runs, "comp-a", 1, datasets={"dataset_id": "x", "universe_kind": "current-holdings-proxy"})
        b = _component(self.runs, "comp-b", 2)
        code, _, err = self.combine([a, b], "--cycle-id", "C1")
        self.assertEqual(code, 1)
        self.assertIn("comp-a", err)
        self.assertEqual(read_ledger(self.ledger).trial_count("C1"), 0)

    def test_reproduction_script_matches_the_recorded_combination(self):
        ids = self.two()
        _, run_id, _ = self.combine(ids, "--exploratory", "--rebalance", "daily")
        result = portfolio_repro.reproduce(self.runs, run_id)
        self.assertTrue(result["all_identical"])
        self.assertEqual(set(result["tables_equal"]), {"returns", "positions", "signals", "fills"})
        self.assertEqual(sorted(p.name for p in self.runs.iterdir()), sorted(ids + [run_id]))  # nothing written


if __name__ == "__main__":
    unittest.main()
