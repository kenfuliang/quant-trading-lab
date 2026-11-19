"""End-to-end scenario for the three enforced research rules (temporary roots only).

Walks financial use -> completed record -> promotion, asserting each rejection before the
success. Never touches the real registry, data root, runs, parity or validation-receipt
directories. Git is faked, so no repository state is read.
"""
import contextlib
import hashlib
import io
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from research.control import experiment_registry as reg
from research.evaluation import acceptance
from research.evaluation.acceptance import AcceptanceError
from research.evaluation.parity_fixture import synthetic_fixture
from scripts import analysis
from scripts import experiments as cli
from scripts import validation as validation_cli

NOW = datetime(2026, 11, 18, tzinfo=timezone.utc)
STAMP = "20261118T000000Z"
ROOT = Path(analysis.ROOT)
SPEC = ROOT / "research/registry/analysis-specs/fixture-ladder.json"
CHECKS = [{"name": "a", "status": "pass", "count": 0}, {"name": "b", "status": "exception", "count": 2}]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class EnforcedRulesScenario(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.data = self.root / "data"
        self.docs = self.root / "docs"
        (self.docs / "tasks/evidence").mkdir(parents=True)
        self.registry = self.root / "experiments.jsonl"
        self.parity, self.receipts = self.root / "parity", self.root / "validation-receipts"
        self.runs = self.data / "runs"
        folder = self.data / "quality/ds-1" / STAMP
        folder.mkdir(parents=True)
        report = {"schema": "quality-report/v1", "dataset_id": "ds-1", "status": "pass-with-exceptions",
                  "checks": CHECKS, "acceptance": {"accepted_by": None, "accepted_utc": None}}
        (folder / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        for target, value in [("DOCS", self.docs), ("RECEIPTS", self.docs / "tasks/evidence"),
                              ("EXEMPTIONS", self.root / "exempt.json"), ("VALIDATION_RECEIPTS", self.receipts)]:
            patcher = mock.patch.object(cli, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        git = mock.patch.object(cli, "run_git", lambda args: (0, ""))  # engine files unchanged
        git.start()
        self.addCleanup(git.stop)

    def financial(self):
        spec = json.loads(SPEC.read_text())
        spec.pop("fixture", None)
        spec.update(dataset_id="ds-1", instruments=["SPY"], use="financial")
        loader = lambda dataset_id, instruments, root: (synthetic_fixture(), {  # noqa: E731
            "manifest_sha256": "e" * 64, "quality_status": "pass-with-exceptions", "quality_report": f"quality/ds-1/{STAMP}/report.json"})
        return analysis.run_spec(spec, self.data, now=NOW, loader=loader, tearsheet=lambda *a: "<html/>")

    def log(self, rid, disposition, *extra):
        argv = ["--registry", str(self.registry), "log", "--id", rid, "--name", "Candidate", "--context", "C1",
                "--period", "2020-2025", "--disposition", disposition, "--lesson", "Held up.",
                "--metrics", json.dumps({"net_cagr": 0.2, "max_drawdown": 0.1}),
                "--runs-root", str(self.runs), "--parity-root", str(self.parity),
                "--receipts-dir", str(self.receipts), *extra]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(argv)
        return code, err.getvalue()

    def rejected(self, text, *args):
        code, err = self.log(*args)
        self.assertEqual(code, 1, err)
        self.assertIn(text, err)

    def write_json(self, path, doc):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, sort_keys=True))

    def validation(self, validator_skill):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = validation_cli.main([
                "create", "--receipt-id", "VR1", "--run-id", self.run_id, "--run-id", "N1",
                "--parity-receipt-id", "P1", "--validator-skill", validator_skill,
                "--researcher-skills", "trade-experiment", "--check", "leakage:pass:no findings",
                "--result", "pass", "--dir", str(self.receipts)])
        return code, err.getvalue()

    def test_end_to_end_rules(self):
        # Rule 1: a financial run on a pass-with-exceptions report is blocked, then unlocked by the owner's acceptance.
        with self.assertRaisesRegex(AcceptanceError, r"uncovered checks \['b'\]"):
            self.financial()
        self.assertFalse(self.runs.exists())
        acceptance.write_acceptance(self.data, "ds-1", STAMP, "owner", ["all"], "fixture", NOW)
        doc = self.financial()["doc"]
        self.assertEqual(doc["use"], "financial")
        self.run_id = doc["runs"][0]["run_id"]
        manifest = json.loads((self.runs / self.run_id / "manifest.json").read_text())
        self.assertEqual(manifest["use"], "financial")
        self.assertEqual(manifest["acceptance_sha256"], doc["acceptance_sha256"])

        # Rule 2: a completed record needs a run output.
        self.rejected("run_manifest_sha256", "c-1", "retire")
        self.assertFalse(self.registry.exists())
        self.assertEqual(self.log("c-1", "retire", "--run-id", self.run_id)[0], 0)
        self.assertEqual(reg.load(self.registry)[0]["refs"]["run_manifest_sha256"],
                         sha(self.runs / self.run_id / "manifest.json"))

        # Rule 3: keep needs a nautilus run, a passing parity receipt and a validation receipt, in turn.
        keep = ("k-1", "keep", "--run-id", self.run_id)
        self.rejected("nautilus_run_id", *keep)
        bound = {**manifest, "run_id": "N1", "engine": "nautilus", "code_commit": "c" * 40,
                 "config": {**manifest["config"], "engine": "nautilus"}}
        self.write_json(self.runs / "N1" / "manifest.json", bound)
        keep += ("--nautilus-run-id", "N1")
        self.rejected("parity_receipt_id", *keep)
        self.write_json(self.parity / "P1" / "receipt.json", {
            "parity_id": "P1", "status": "passed", "passed": True, "mismatch_count": 0, "code_commit": "b" * 40,
            "run_id": "N1"})
        keep += ("--parity-receipt", "P1")
        self.rejected("validation_receipt", *keep)
        keep += ("--validation-receipt", "VR1")
        self.rejected("not found", *keep)
        # A Research skill cannot validate: the CLI refuses it, and a hand-written receipt is refused at log time.
        code, err = self.validation("trade-experiment")
        self.assertEqual(code, 1)
        self.assertIn("Validation skill", err)
        self.assertFalse(self.receipts.exists() and any(self.receipts.glob("*.json")))
        self.write_json(self.receipts / "VR1.json", {
            "schema": "validation-receipt/v1", "receipt_id": "VR1", "created_utc": "2026-11-18T00:00:00+00:00",
            "run_ids": [self.run_id, "N1"], "parity_receipt_id": "P1", "validator": {"skill": "trade-experiment"},
            "researcher": {"skills": ["trade-experiment"]},
            "checks": [{"name": "leakage", "status": "pass", "detail": "x"}], "result": "pass", "notes": ""})
        self.rejected("Validation skill", *keep)
        (self.receipts / "VR1.json").unlink()
        self.assertEqual(self.validation("trade-leakage-audit"), (0, ""))
        # The nautilus run must be a financial run bound to the candidate (an engineering parity run is not).
        engineering = {"run_id": "N1", "engine": "nautilus", "code_commit": "c" * 40,
                       "datasets": {"dataset_id": "synthetic-fixture"}}
        self.write_json(self.runs / "N1" / "manifest.json", engineering)
        self.rejected("not a financial-use run", *keep)
        self.write_json(self.runs / "N1" / "manifest.json", {
            **bound, "datasets": {**manifest["datasets"], "manifest_sha256": "f" * 64}})
        self.rejected("not bound", *keep)
        self.write_json(self.runs / "N1" / "manifest.json", {
            **bound, "config": {**bound["config"], "strategy": {"kind": "other"}}})
        self.rejected("not bound", *keep)
        self.write_json(self.runs / "N1" / "manifest.json", bound)
        self.assertEqual(self.log(*keep)[0], 0)
        refs = reg.load(self.registry)[1]["refs"]
        self.assertEqual(refs["validation_receipt_sha256"], sha(self.receipts / "VR1.json"))

        # Structural check passes with the local run and parity roots removed.
        self.assertEqual(self.render_and_check(), (0, ""))

    def render_and_check(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            cli.main(["--registry", str(self.registry), "render"])
            shutil.rmtree(self.runs)
            shutil.rmtree(self.parity)
            code = cli.main(["--registry", str(self.registry), "check"])
        return code, err.getvalue()


if __name__ == "__main__":
    unittest.main()
