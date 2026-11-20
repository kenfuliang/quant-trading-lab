"""End-to-end `keep` path: screening run -> confirmation -> validation receipt -> keep record.

Temporary roots only: a temp data root (tiny dataset + accepted quality report), temp registry,
temp parity root and temp validation-receipts directory. Git is faked. Never touches the real
registry, trial ledger, acceptances or run outputs. Each rejection is asserted before its success.
"""
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from research.control import experiment_registry as reg
from research.evaluation import acceptance
from research.evaluation.datasets import load_dataset
from research.evaluation.run_output import read_run
from scripts import analysis, confirm
from scripts import experiments as cli
from scripts import validation as validation_cli
from tests.current.test_datasets import ID, make_root

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
CLEAN = "c" * 40
REPO_REGISTRY = Path(analysis.ROOT) / "research/registry/experiments.jsonl"
SPEC = {
    "spec_id": "keep-path", "title": "Keep path fixture", "dataset_id": ID, "instruments": ["AAA", "KID", "PAR"],
    "use": "financial", "comparison": None, "pbo_grid": None, "cutoffs": 3,
    "rungs": [{"name": "buy_hold", "strategy": {"name": "buy_hold", "gross": 0.95},
               "market": {"cost_bps": 0, "commission_usd": 0}}]}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class KeepPathTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.data = self.base / "data"
        self.data.mkdir()
        self.runs, self.parity = self.data / "runs", self.data / "parity"
        self.receipts = self.base / "validation-receipts"
        self.registry = self.base / "experiments.jsonl"
        self.real_registry_sha = sha(REPO_REGISTRY)
        self.addCleanup(lambda: self.assertEqual(sha(REPO_REGISTRY), self.real_registry_sha))
        for target, value in [("DOCS", self.base / "docs"), ("RECEIPTS", self.base / "docs/tasks/evidence"),
                              ("EXEMPTIONS", self.base / "exempt.json"), ("VALIDATION_RECEIPTS", self.receipts)]:
            patcher = mock.patch.object(cli, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for patcher in (mock.patch.object(cli, "run_git", lambda args: (0, "")),  # engine files unchanged; receipt tracked
                        mock.patch.object(analysis, "_code_commit", lambda: CLEAN)):
            patcher.start()
            self.addCleanup(patcher.stop)

    # -- helpers -----------------------------------------------------------------------------
    def quiet(self, fn, *args, **kwargs):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = fn(*args, **kwargs)
        return code, out.getvalue(), err.getvalue()

    def confirm(self, run_id, commit, *extra, now=None):
        argv = ["--run-id", run_id, "--root", str(self.data), "--runs-root", str(self.runs),
                "--parity-root", str(self.parity), *extra]
        with mock.patch.object(confirm, "datetime", **{"now.return_value": now or datetime.now(timezone.utc)}):
            code, out, err = self.quiet(confirm.main, argv, commit_fn=lambda: commit)
        self.assertEqual(code, 0, err)
        lines = out.splitlines()
        return lines[0].removeprefix("native run: "), lines[1].removeprefix("parity id: ")

    def validation(self, receipt_id, run_ids, parity_id, skill="trade-leakage-audit"):
        argv = ["create", "--receipt-id", receipt_id, "--parity-receipt-id", parity_id, "--validator-skill", skill,
                "--researcher-skills", "trade-experiment", "--check", "leakage:pass:no findings",
                "--result", "pass", "--dir", str(self.receipts)]
        for run_id in run_ids:
            argv += ["--run-id", run_id]
        code, _, err = self.quiet(validation_cli.main, argv)
        self.assertEqual(code, 0, err)

    def log(self, *extra, dry_run=True):
        argv = ["--registry", str(self.registry), "log", "--id", "k-1", "--name", "Candidate", "--context", "C1",
                "--period", "2020-2025", "--disposition", "keep", "--lesson", "Held up.",
                "--metrics", json.dumps({"net_cagr": 0.2, "max_drawdown": 0.1}),
                "--runs-root", str(self.runs), "--parity-root", str(self.parity),
                "--receipts-dir", str(self.receipts), *extra, *(["--dry-run"] if dry_run else [])]
        code, out, err = self.quiet(cli.main, argv)
        return code, out, err

    def rejected(self, text, *extra):
        code, _, err = self.log(*extra)
        self.assertEqual(code, 1, err)
        self.assertIn(text, err)

    # -- the scenario ------------------------------------------------------------------------
    def test_keep_path_end_to_end(self):
        make_root(self.data, report="pass-with-exceptions")
        # Rule 1: a financial run needs the owner's acceptance first.
        stamp = Path(load_dataset(ID, ("AAA", "KID", "PAR"), self.data)[1]["quality_report"]).parent.name
        acceptance.write_acceptance(self.data, ID, stamp, "owner", ["all"], "fixture", NOW)

        # 1. a financial screening run through run_spec
        result = analysis.run_spec(dict(SPEC), self.data, registry_path=self.registry, now=NOW,
                                   tearsheet=lambda *a: "<html/>")
        self.assertEqual(result["doc"]["use"], "financial")
        screen_id = result["doc"]["runs"][0]["run_id"]
        self.assertEqual(read_run(self.runs / screen_id)[0]["engine"], "screen")

        # 2. confirm: a NautilusTrader run and a passing receipt (clean commit)
        native_id, parity_id = self.confirm(screen_id, CLEAN)
        receipt = json.loads((self.parity / parity_id / "receipt.json").read_text())
        self.assertEqual((receipt["status"], receipt["passed"], receipt["bindable"]), ("passed", True, True))
        native, _ = read_run(self.runs / native_id)
        self.assertEqual((native["engine"], native["use"], native["parent_run"]), ("nautilus", "financial", screen_id))

        # 3. keep without a validation receipt is rejected, naming it; nothing is written
        refs = ("--run-id", screen_id, "--nautilus-run-id", native_id, "--parity-receipt", parity_id)
        self.rejected("validation_receipt", *refs)
        self.assertFalse(self.registry.exists())

        # 4a. a validation receipt that does not cover both runs is rejected
        self.validation("VR0", [screen_id], parity_id)
        self.rejected("VR0", *refs, "--validation-receipt", "VR0")
        # 4b. a Research skill cannot validate
        code, _, err = self.quiet(validation_cli.main, [
            "create", "--receipt-id", "VRX", "--run-id", screen_id, "--run-id", native_id,
            "--parity-receipt-id", parity_id, "--validator-skill", "trade-experiment",
            "--researcher-skills", "trade-experiment", "--check", "leakage:pass:x", "--result", "pass",
            "--dir", str(self.receipts)])
        self.assertEqual(code, 1)
        self.assertIn("Validation skill", err)
        # 4c. a valid receipt from a Validation skill, covering both runs and the parity receipt: accepted
        self.validation("VR1", [screen_id, native_id], parity_id)
        code, out, err = self.log(*refs, "--validation-receipt", "VR1")
        self.assertEqual(code, 0, err)
        record = json.loads(out)
        self.assertEqual(record["disposition"], "keep")
        self.assertEqual((record["refs"]["run_id"], record["refs"]["nautilus_run_id"],
                          record["refs"]["parity_receipt_id"], record["refs"]["validation_receipt"]),
                         (screen_id, native_id, parity_id, "VR1"))
        self.assertEqual(record["refs"]["validation_receipt_sha256"], sha(self.receipts / "VR1.json"))
        self.assertFalse(self.registry.exists())  # dry run
        # a real (non-dry) log into the temp registry works too
        self.assertEqual(self.log(*refs, "--validation-receipt", "VR1", dry_run=False)[0], 0)
        self.assertEqual(reg.load(self.registry)[0]["refs"]["parity_receipt_id"], parity_id)

        # 5. a --allow-dirty confirmation (+dirty) cannot back a keep
        dirty_native, dirty_parity = self.confirm(screen_id, CLEAN + "+dirty", "--allow-dirty",
                                                   now=datetime(2026, 11, 19, 13, 0, tzinfo=timezone.utc))
        dirty_receipt = json.loads((self.parity / dirty_parity / "receipt.json").read_text())
        self.assertTrue(dirty_receipt["code_commit"].endswith("+dirty"))
        self.validation("VR2", [screen_id, dirty_native], dirty_parity)
        self.rejected("dirty", "--run-id", screen_id, "--nautilus-run-id", dirty_native,
                      "--parity-receipt", dirty_parity, "--validation-receipt", "VR2")


if __name__ == "__main__":
    unittest.main()
