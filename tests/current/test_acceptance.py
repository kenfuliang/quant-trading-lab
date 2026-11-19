"""Offline tests of quality acceptance and the financial-use gate (temporary roots only)."""
import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from research.evaluation import acceptance
from research.evaluation.acceptance import AcceptanceError
from research.evaluation.parity_fixture import synthetic_fixture
from scripts import analysis
from scripts import data as data_cli

NOW = datetime(2026, 11, 18, tzinfo=timezone.utc)
STAMP = "20261118T000000Z"
SPEC = Path(analysis.ROOT) / "research/registry/analysis-specs/fixture-ladder.json"


def make_report(root, status="pass-with-exceptions", dataset_id="ds-1", stamp=STAMP):
    checks = [{"name": "a", "status": "pass", "count": 0},
              {"name": "b", "status": "exception", "count": 2},
              {"name": "c", "status": "blocked", "count": 0}]
    if status == "pass":
        checks = [dict(c, status="pass") for c in checks]
    report = {"schema": "quality-report/v1", "dataset_id": dataset_id, "status": status, "checks": checks,
              "acceptance": {"accepted_by": None, "accepted_utc": None}}
    folder = Path(root) / "quality" / dataset_id / stamp
    folder.mkdir(parents=True)
    (folder / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return folder, report


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def accept(self, accepts=("all",), by="owner"):
        return acceptance.write_acceptance(self.root, "ds-1", STAMP, by, list(accepts), "ok", NOW)

    def test_pass_report_needs_no_acceptance(self):
        folder, report = make_report(self.root, "pass")
        self.assertEqual(acceptance.verify_for_financial_use(self.root, folder, report),
                         {"status": "pass", "acceptance_sha256": None})

    def test_exceptions_without_acceptance_block_financial_use(self):
        folder, report = make_report(self.root)
        with self.assertRaisesRegex(AcceptanceError, r"uncovered checks \['b', 'c'\]"):
            acceptance.verify_for_financial_use(self.root, folder, report)

    def test_acceptance_covering_all_exceptions_unlocks(self):
        folder, report = make_report(self.root)
        self.accept(["b", "c"])
        result = acceptance.verify_for_financial_use(self.root, folder, report)
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(len(result["acceptance_sha256"]), 64)
        (folder / "acceptance.json").unlink()
        self.accept(["all"])
        self.assertEqual(acceptance.verify_for_financial_use(self.root, folder, report)["status"], "accepted")

    def test_partial_acceptance_names_uncovered_checks(self):
        folder, report = make_report(self.root)
        self.accept(["b"])
        with self.assertRaisesRegex(AcceptanceError, r"does not cover checks \['c'\]"):
            acceptance.verify_for_financial_use(self.root, folder, report)

    def test_acceptance_for_changed_report_is_rejected(self):
        folder, report = make_report(self.root)
        self.accept()
        report["checks"][1]["count"] = 3
        (folder / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(AcceptanceError, "report_sha256"):
            acceptance.verify_for_financial_use(self.root, folder, report)

    def test_acceptance_copied_to_another_report_is_rejected(self):
        folder, _ = make_report(self.root)
        self.accept()
        other, other_report = make_report(self.root, stamp="20261119T000000Z")
        (other / "acceptance.json").write_text((folder / "acceptance.json").read_text(), encoding="utf-8")
        with self.assertRaisesRegex(AcceptanceError, "report_stamp"):
            acceptance.verify_for_financial_use(self.root, other, other_report)

    def test_fail_report_never_loadable(self):
        folder, report = make_report(self.root, "fail")
        with self.assertRaisesRegex(AcceptanceError, "'fail'"):
            acceptance.verify_for_financial_use(self.root, folder, report)
        with self.assertRaises(AcceptanceError):
            self.accept()

    def test_write_is_exclusive_and_requires_name(self):
        make_report(self.root)
        with self.assertRaises(AcceptanceError):
            self.accept(by="  ")
        with self.assertRaises(AcceptanceError):
            acceptance.write_acceptance(self.root, "ds-1", STAMP, "owner", [], "n", NOW)
        with self.assertRaisesRegex(AcceptanceError, "unknown checks"):
            self.accept(["zzz"])
        path = self.accept()
        doc = json.loads(path.read_text())
        self.assertEqual((doc["schema"], doc["accepted_by"], doc["accepts"]), (acceptance.SCHEMA, "owner", ["all"]))
        with self.assertRaises(FileExistsError):
            self.accept()

    def test_cli_accept(self):
        folder, _ = make_report(self.root)
        base = ["accept", "--dataset-id", "ds-1", "--report-stamp", STAMP, "--by", "owner",
                "--accepts", "b,c", "--note", "n", "--root", str(self.root)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(data_cli.main(base), 0)
        self.assertTrue((folder / "acceptance.json").is_file())
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(data_cli.main(base), 1)  # exclusive
            self.assertEqual(data_cli.main(base[:6] + ["", *base[7:]]), 1)  # empty name
            bad = base[:]
            bad[bad.index("--report-stamp") + 1] = "20200101T000000Z"
            self.assertEqual(data_cli.main(bad), 2)  # absent report


class FinancialRunTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.folder, _ = make_report(self.root)

    def spec(self, use=None):
        spec = json.loads(SPEC.read_text())
        spec.pop("fixture", None)
        spec.update(dataset_id="ds-1", instruments=["SPY"])
        if use:
            spec["use"] = use
        return spec

    def loader(self, dataset_id, instruments, root):
        return synthetic_fixture(), {"quality_status": "pass-with-exceptions",
                                     "quality_report": f"quality/ds-1/{STAMP}/report.json"}

    def run_spec(self, spec, root=None):
        return analysis.run_spec(spec, root or self.root, now=NOW, loader=self.loader, tearsheet=lambda *a: "<html/>")

    def manifests(self):
        return [json.loads(p.read_text()) for p in sorted((self.root / "runs").glob("*/manifest.json"))]

    def test_engineering_run_unchanged(self):
        default = self.run_spec(self.spec())["doc"]
        with tempfile.TemporaryDirectory() as other:
            _, _ = make_report(other)
            explicit = self.run_spec(self.spec("engineering"), Path(other))["doc"]
        for doc in (default, explicit):
            self.assertNotIn("use", doc)
            self.assertNotIn("acceptance_sha256", doc)
        self.assertEqual([r["run_id"] for r in default["runs"]],
                         [r["run_id"] for r in explicit["runs"]])
        self.assertTrue(all("use" not in m and "acceptance_sha256" not in m for m in self.manifests()))

    def test_financial_run_is_refused_without_acceptance_and_writes_nothing(self):
        with self.assertRaisesRegex(AcceptanceError, r"uncovered checks \['b', 'c'\]"):
            self.run_spec(self.spec("financial"))
        self.assertFalse((self.root / "runs").exists())
        self.assertFalse((self.root / "analysis").exists())

    def test_financial_run_records_use_and_acceptance(self):
        acceptance.write_acceptance(self.root, "ds-1", STAMP, "owner", ["all"], "n", NOW)
        doc = self.run_spec(self.spec("financial"))["doc"]
        self.assertEqual(doc["use"], "financial")
        self.assertEqual(len(doc["acceptance_sha256"]), 64)
        self.assertEqual(doc["datasets"]["acceptance"]["status"], "accepted")
        manifests = self.manifests()
        self.assertEqual(len(manifests), 3)
        self.assertTrue(all(m["use"] == "financial" and m["acceptance_sha256"] == doc["acceptance_sha256"]
                            for m in manifests))

    def test_fixture_cannot_be_financial_and_cli_conflict_errors(self):
        spec = json.loads(SPEC.read_text())
        spec["use"] = "financial"
        with self.assertRaises(AcceptanceError):
            analysis.run_spec(spec, self.root, now=NOW)
        path = self.root / "spec.json"
        path.write_text(json.dumps({**json.loads(SPEC.read_text()), "use": "engineering"}))
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(analysis.main(["run", "--spec", str(path), "--root", str(self.root),
                                            "--use", "financial"]), 1)
        self.assertIn("conflicts", err.getvalue())


if __name__ == "__main__":
    unittest.main()
