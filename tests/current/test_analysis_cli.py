"""Offline tests of scripts/analysis.py: run, DSR trial counts and the golden summary."""
import contextlib
import io
import json
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from research.control import experiment_registry as registry
from scripts import analysis

SPEC = Path(analysis.ROOT) / "research/registry/analysis-specs/fixture-ladder.json"


def record(record_id, code, sharpe):
    return {"schema": registry.SCHEMA, "record_id": record_id, "logged_at": "2026-11-18T00:00:00+00:00",
            "name": record_id, "context": {"code": code, "period": "2005-2025", "costs_bp": 5.0},
            "evidence_class": "development", "disposition": "control", "lesson": "test",
            "metrics": {"sharpe": sharpe, "net_cagr": 0.1}}


class AnalysisCliTests(unittest.TestCase):
    def test_cli_run_on_fixture_spec_writes_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with mock.patch.dict(os.environ, {"QTL_DATA_ROOT": tmp}), contextlib.redirect_stdout(out):
                self.assertEqual(analysis.main(["run", "--spec", str(SPEC)]), 0)
            folder = Path(out.getvalue().strip())
            self.assertEqual(folder.parent, Path(tmp) / "analysis")
            doc = json.loads((folder / "analysis.json").read_text())
            self.assertEqual(doc["schema"], "analysis-output/v1")
            self.assertEqual([r["rung"] for r in doc["runs"]], ["buy_hold", "sma_trend", "sma_trend_costs"])
            self.assertEqual(doc["lookahead"]["status"], "pass")
            self.assertTrue(all(c["compared_signals"] > 0 for c in doc["lookahead"]["compared"]))
            self.assertIsNotNone(doc["trust"]["psr"]["value"])
            self.assertIsNone(doc["trust"]["dsr"]["value"])  # no comparison record: trial count undefined
            self.assertIsNone(doc["trust"]["pbo"]["value"])
            self.assertTrue((folder / "report.md").is_file())
            self.assertTrue((folder / "tearsheet.html").is_file())
            self.assertEqual(len(list((Path(tmp) / "runs").iterdir())), 3)

    def test_run_with_comparison_and_grid(self):
        spec = json.loads(SPEC.read_text())
        spec["comparison"] = {"record_ids": ["c-1", "missing-id"]}
        spec["pbo_grid"] = [{"name": "sma_trend", "window": w, "gross": 0.95} for w in (5, 10, 20, 40)]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reg.jsonl"
            for rec in (record("c-1", "C01-5bp", 1.0), record("c-2", "C01-5bp", 0.5), record("c-3", "C01-5bp", 0.8),
                        record("o-1", "OTHER", 9.0)):
                registry.append(path, rec)
            doc = analysis.run_spec(spec, Path(tmp), path)["doc"]
        self.assertEqual(doc["trust"]["dsr"]["n_trials"], 3)
        self.assertEqual(doc["comparison"]["missing"], ["missing-id"])
        self.assertEqual([r["record_id"] for r in doc["comparison"]["records"]], ["c-1"])
        self.assertIn("illustrative grid", " ".join(doc["notes"]))
        self.assertIn("value", doc["trust"]["pbo"])

    def test_dsr_counts_registry_records_by_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reg.jsonl"
            for rec in (record("a-1", "C01-5bp", 1.0), record("a-2", "C01-5bp", 0.5), record("a-3", "C01-5bp", 0.8),
                        record("b-1", "U1-25bp", 3.0)):
                registry.append(path, rec)
            n, variance = analysis.trial_stats(registry.load(path), "C01-5bp")
        self.assertEqual(n, 3)
        per = [s / math.sqrt(252) for s in (1.0, 0.5, 0.8)]
        mean = sum(per) / 3
        self.assertAlmostEqual(variance, sum((x - mean) ** 2 for x in per) / 2)
        self.assertEqual(analysis.trial_stats([], "C01-5bp"), (0, None))
        one = [record("a-1", "C01-5bp", 1.0)]
        self.assertEqual(analysis.trial_stats(one, "C01-5bp"), (1, None))

    def test_golden_detects_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "golden.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(analysis.main(["golden", "--update", "--file", str(target)]), 0)
                self.assertEqual(analysis.main(["golden", "--file", str(target)]), 0)
            data = json.loads(target.read_text())
            data["sma_trend"]["sharpe"] += 0.5
            target.write_text(json.dumps(data))
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(analysis.main(["golden", "--file", str(target)]), 1)
            self.assertIn(str(target), err.getvalue())

    def test_committed_golden_matches(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(analysis.main(["golden"]), 0)


if __name__ == "__main__":
    unittest.main()
