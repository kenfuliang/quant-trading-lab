"""End-to-end `keep` path: screening run -> confirmation -> validation receipt -> keep record.

Temporary roots only: a temp data root (tiny dataset + accepted quality report), temp registry,
temp parity root and temp validation-receipts directory. Git is faked. Never touches the real
registry, trial ledger, acceptances or run outputs. Each rejection is asserted before its success.
"""
import contextlib
import dataclasses
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
from research.evaluation.datasets import load_dataset
from research.evaluation.run_output import read_run
from research.evaluation.screening_engine import run_screen
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

    # -- rule 3 ties the receipt to the cited runs ---------------------------------------------
    def financial_run(self, spec, now):
        return analysis.run_spec(spec, self.data, registry_path=self.registry, now=now,
                                 tearsheet=lambda *a: "<html/>")["doc"]["runs"][0]["run_id"]

    def keep_args(self, screen_id, native_id, parity_id, receipt_id):
        self.validation(receipt_id, [screen_id, native_id], parity_id)
        return ("--run-id", screen_id, "--nautilus-run-id", native_id, "--parity-receipt", parity_id,
                "--validation-receipt", receipt_id)

    def test_keep_needs_the_confirmation_of_exactly_the_cited_runs(self):
        make_root(self.data, report="pass-with-exceptions")
        stamp = Path(load_dataset(ID, ("AAA", "KID", "PAR"), self.data)[1]["quality_report"]).parent.name
        acceptance.write_acceptance(self.data, ID, stamp, "owner", ["all"], "fixture", NOW)
        x = self.financial_run(dict(SPEC), NOW)
        other = dict(SPEC, spec_id="other", rungs=[{"name": "bh", "strategy": {"name": "buy_hold", "gross": 0.5},
                                                    "market": {"cost_bps": 0, "commission_usd": 0}}])
        y = self.financial_run(other, datetime(2026, 11, 19, 12, 5, tzinfo=timezone.utc))
        n_x, p_x = self.confirm(x, CLEAN)
        n_y, p_y = self.confirm(y, CLEAN)

        # a mismatching native run for X (perturbed fills) cited with a foreign passing receipt for Y
        def perturbed(data, fn, market):
            result = run_screen(data, fn, market)
            fills = result.fills.copy()
            fills.loc[0, "price"] += 5.0
            return dataclasses.replace(result, engine="nautilus", fills=fills)
        argv = ["--run-id", x, "--root", str(self.data), "--runs-root", str(self.runs),
                "--parity-root", str(self.parity)]
        with mock.patch.object(confirm, "datetime", **{"now.return_value": datetime(2026, 11, 19, 14, 0, tzinfo=timezone.utc)}):
            code, out, err = self.quiet(confirm.main, argv, native_runner=perturbed, commit_fn=lambda: CLEAN)
        self.assertEqual(code, 1, err)
        bad_native = out.splitlines()[0].removeprefix("native run: ")
        self.rejected("use=None", *self.keep_args(x, bad_native, p_y, "VRA"))  # defence in depth: not financial
        # even with the financial fields restored by hand, the receipt is not the confirmation of these runs
        path = self.runs / bad_native / "manifest.json"
        doc = json.loads(path.read_text())
        doc.update(use="financial", acceptance_sha256=json.loads((self.runs / x / "manifest.json").read_text())["acceptance_sha256"])
        path.write_text(json.dumps(doc, sort_keys=True))
        self.rejected("runs.", *self.keep_args(x, bad_native, p_y, "VRA2"))

        # the receipt of another screening run, and a native run that is not the receipt's
        self.rejected("runs.", *self.keep_args(x, n_x, p_y, "VRB"))
        self.rejected("not bound", *self.keep_args(x, n_y, p_x, "VRC"))  # caught earlier by the run binding

        # a stale screening run: the same spec re-run later is a different run than the one confirmed
        stale = self.financial_run(dict(SPEC), datetime(2026, 11, 19, 12, 30, tzinfo=timezone.utc))
        self.assertNotEqual(stale, x)
        self.rejected("runs.screen", *self.keep_args(stale, n_x, p_x, "VRD"))

        # a universe swap: a masked run M with X's strategy, market, instruments and dataset, kept
        # with the native run and receipt of the unmasked confirmation of X
        manifest = json.loads((self.runs / x / "manifest.json").read_text())
        masked = dict(manifest, run_id="masked-1", config=dict(manifest["config"], universe={
            "membership_id": "m", "identity_id": "i"}))
        shutil.copytree(self.runs / x, self.runs / "masked-1")
        (self.runs / "masked-1" / "manifest.json").write_text(json.dumps(masked, sort_keys=True))
        self.rejected("runs.screen", *self.keep_args("masked-1", n_x, p_x, "VRE"))

        # a plain engine-parity receipt (no kind) is refused
        plain = json.loads((self.parity / p_x / "receipt.json").read_text())
        plain.pop("kind")
        plain["parity_id"] = "plain-1"
        (self.parity / "plain-1").mkdir()
        (self.parity / "plain-1" / "receipt.json").write_text(json.dumps(plain, sort_keys=True))
        self.rejected("candidate-confirmation", *self.keep_args(x, n_x, "plain-1", "VRF"))

        # the matching confirmation is accepted
        code, _, err = self.log(*self.keep_args(x, n_x, p_x, "VRG"))
        self.assertEqual(code, 0, err)


if __name__ == "__main__":
    unittest.main()
