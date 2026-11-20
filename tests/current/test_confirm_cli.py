"""Offline tests of scripts/confirm.py: temp roots, injected commit helper, loader and native runner."""
import contextlib
import dataclasses
import hashlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from research.data.manifest import sha256_file, write_manifest
from research.evaluation import acceptance
from research.evaluation.datasets import load_dataset
from research.evaluation.ladder import Rung, run_ladder
from research.evaluation.market_model import MarketConfig
from research.evaluation.parity_fixture import synthetic_fixture
from research.evaluation.run_output import read_run, write_run
from research.evaluation.screening_engine import run_screen
from scripts import analysis, confirm
from tests.current.test_datasets import ID, make_root

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
CLEAN = "c" * 40
BUY_HOLD = {"name": "buy_hold", "gross": 0.95}
SPEC = {"name": "sma_trend", "window": 20, "gross": 0.95}
REPO_REGISTRY = Path(analysis.ROOT) / "research/registry/experiments.jsonl"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ConfirmCliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "data"
        self.root.mkdir()
        self.runs = self.root / "runs"
        self.parity = self.root / "parity"
        self.registry_before = sha(REPO_REGISTRY)

    def tearDown(self):
        self.assertEqual(sha(REPO_REGISTRY), self.registry_before)

    # -- helpers -----------------------------------------------------------------------------
    def screen(self, data, datasets, strategy=SPEC, base_extra=None, wrap=None, universe=None):
        base = {"code_commit": CLEAN, "datasets": datasets, **(base_extra or {})}
        steps = run_ladder(data, [Rung("trend", strategy, MarketConfig())], self.runs, base, NOW,
                           wrap=wrap, universe=universe)
        return steps[0]["run_id"]

    def fixture_run(self, **kwargs):
        return self.screen(synthetic_fixture(), {"dataset_id": "synthetic-fixture"}, **kwargs)

    def dataset_root(self, report="pass"):
        make_root(self.root, report=report)
        data, provenance = load_dataset(ID, ("AAA", "KID", "PAR"), self.root)
        return data, {"dataset_id": ID, **provenance}

    def run_main(self, run_id, *extra, commit=CLEAN, **kwargs):
        argv = ["--run-id", run_id, "--root", str(self.root), "--runs-root", str(self.runs),
                "--parity-root", str(self.parity), *extra]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = confirm.main(argv, commit_fn=lambda: commit, **kwargs)
        return code, out.getvalue(), err.getvalue()

    def receipts(self):
        found = sorted(self.parity.glob("*/receipt.json")) if self.parity.exists() else []
        return [json.loads(p.read_text()) for p in found]

    def native_runs(self):
        out = []
        for folder in sorted(self.runs.iterdir()):
            manifest, _ = read_run(folder)
            if manifest["engine"] == "nautilus":
                out.append(manifest)
        return out

    # -- tests -------------------------------------------------------------------------------
    def test_confirm_writes_native_run_and_passed_receipt(self):
        run_id = self.fixture_run()
        code, out, err = self.run_main(run_id)
        self.assertEqual(code, 0, err)
        (native,) = self.native_runs()
        (receipt,) = self.receipts()
        self.assertEqual(native["parent_run"], run_id)
        self.assertEqual(native["config"]["strategy"], SPEC)
        self.assertEqual(native["code_commit"], CLEAN)
        self.assertEqual(receipt["schema"], "parity-receipt/v1")
        self.assertEqual(receipt["kind"], "candidate-confirmation")
        self.assertEqual((receipt["status"], receipt["passed"], receipt["mismatch_count"]), ("passed", True, 0))
        self.assertEqual(receipt["run_id"], native["run_id"])
        self.assertEqual(receipt["code_commit"], CLEAN)
        self.assertFalse(receipt["bindable"])  # synthetic fixture: engineering only
        self.assertTrue(receipt["stored_screen_identical"])
        self.assertEqual(receipt["runs"]["screen"], {"run_id": run_id, "manifest_sha256": sha(self.runs / run_id / "manifest.json")})
        self.assertEqual(receipt["runs"]["nautilus"]["manifest_sha256"],
                         sha(self.runs / native["run_id"] / "manifest.json"))
        self.assertEqual(receipt["calendar"]["sessions"], len(synthetic_fixture().sessions))
        self.assertIn(native["run_id"], out)
        self.assertIn(receipt["parity_id"], out)
        self.assertIn(str(self.parity / receipt["parity_id"] / "receipt.json"), out)

    def test_dataset_run_is_bindable_and_hash_checked(self):
        data, datasets = self.dataset_root()
        run_id = self.screen(data, datasets, strategy=BUY_HOLD)
        code, out, err = self.run_main(run_id)
        self.assertEqual(code, 0, err)
        (receipt,) = self.receipts()
        self.assertTrue(receipt["bindable"])
        self.assertEqual(receipt["datasets"]["manifest_sha256"], datasets["manifest_sha256"])
        self.assertNotIn("run_use", receipt)  # engineering run

    def test_refuses_when_dataset_hash_differs(self):
        data, datasets = self.dataset_root()
        run_id = self.screen(data, datasets, strategy=BUY_HOLD)

        def other_hash(dataset_id, instruments, root):
            market, provenance = load_dataset(dataset_id, instruments, root)
            return market, {**provenance, "manifest_sha256": "f" * 64}

        code, out, err = self.run_main(run_id, loader=other_hash)
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertIn("manifest_sha256", err)
        self.assertEqual(self.receipts(), [])
        self.assertEqual(len(list(self.runs.iterdir())), 1)

    def test_refuses_non_screen_run(self):
        run_id = self.fixture_run()
        manifest, tables = read_run(self.runs / run_id)
        manifest["run_id"] = "20260101T000000Z-native001"
        manifest["engine"] = "nautilus"
        manifest["config"] = dict(manifest["config"], engine="nautilus")
        native_id = manifest["run_id"]
        manifest.pop("files")
        manifest.pop("schema")
        from research.evaluation.run_output import config_hash
        manifest["config_hash"] = config_hash(manifest["config"])
        write_run(self.runs, manifest, tables)
        code, out, err = self.run_main(native_id)
        self.assertEqual(code, 1)
        self.assertIn("only a screen run", err)
        self.assertEqual(self.receipts(), [])

    def test_refuses_run_that_no_longer_reproduces(self):
        run_id = self.fixture_run()
        # A different strategy is stored under the same data: rebuild the candidate from a doctored config.
        manifest, tables = read_run(self.runs / run_id)
        manifest["run_id"] = "20260101T000000Z-doctored1"
        manifest["config"] = dict(manifest["config"], strategy={**SPEC, "window": 5})
        from research.evaluation.run_output import config_hash
        manifest["config_hash"] = config_hash(manifest["config"])
        manifest.pop("files")
        manifest.pop("schema")
        write_run(self.runs, manifest, tables)
        code, _, err = self.run_main("20260101T000000Z-doctored1")
        self.assertEqual(code, 1)
        self.assertIn("not reproducible", err)
        self.assertEqual(self.receipts(), [])

    def financial_root(self):
        data, datasets = self.dataset_root(report="pass-with-exceptions")
        stamp = Path(datasets["quality_report"]).parent.name
        path = acceptance.write_acceptance(self.root, ID, stamp, "owner", ["all"], "test", NOW)
        gate = analysis._financial_gate({}, self.root, datasets)
        self.assertEqual(gate["status"], "accepted")
        base = {"use": "financial", "acceptance_sha256": gate["acceptance_sha256"]}
        run_id = self.screen(data, {**datasets, "acceptance": gate}, strategy=BUY_HOLD, base_extra=base)
        return run_id, path, gate

    def test_financial_run_reverifies_gate_and_copies_acceptance(self):
        run_id, _, gate = self.financial_root()
        code, out, err = self.run_main(run_id)
        self.assertEqual(code, 0, err)
        (native,) = self.native_runs()
        (receipt,) = self.receipts()
        self.assertEqual((native["use"], native["acceptance_sha256"]), ("financial", gate["acceptance_sha256"]))
        self.assertEqual(receipt["run_use"], "financial")
        self.assertEqual(receipt["acceptance_sha256"], gate["acceptance_sha256"])
        self.assertTrue(receipt["bindable"])

    def test_financial_run_refused_when_acceptance_removed(self):
        run_id, path, _ = self.financial_root()
        path.unlink()
        code, _, err = self.run_main(run_id)
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertIn("accepted quality report", err)
        self.assertEqual(self.receipts(), [])
        self.assertEqual(len(list(self.runs.iterdir())), 1)
        self.assertFalse(path.exists())  # the command never writes an acceptance

    def test_financial_run_refused_when_acceptance_differs_from_manifest(self):
        data, datasets = self.dataset_root()
        run_id = self.screen(data, datasets, strategy=BUY_HOLD,
                             base_extra={"use": "financial", "acceptance_sha256": "e" * 64})
        code, _, err = self.run_main(run_id)
        self.assertEqual(code, 1)
        self.assertIn("acceptance_sha256", err)

    def test_financial_fixture_run_refused(self):
        run_id = self.fixture_run(base_extra={"use": "financial", "acceptance_sha256": None})
        code, _, err = self.run_main(run_id)
        self.assertEqual(code, 1)
        self.assertIn("engineering only", err)

    def test_financial_quality_report_outside_root_refused(self):
        data, datasets = self.dataset_root()
        outside = Path(self._tmp.name) / "report.json"
        outside.write_text("{}")
        run_id = self.screen(data, {**datasets, "quality_report": "../report.json"}, strategy=BUY_HOLD,
                             base_extra={"use": "financial", "acceptance_sha256": None})
        code, _, err = self.run_main(run_id)
        self.assertEqual(code, 1)
        self.assertIn("outside the data root", err)

    def masked_root(self, with_manifest=True):
        from research.data.identity import build_identity
        symbols = ("AAA", "BBB", "CCC")
        sessions = synthetic_fixture().sessions
        archive = {"dataset_id": "arch", "universe": {"equities": [
            {"symbol": s, "name": s, "issuer_identifier": f"id-{s}", "currency": "USD"} for s in symbols]}}
        intervals = {s: [{"start": sessions[0], "end": None}] for s in symbols}
        intervals["BBB"] = [{"start": sessions[100], "end": None}]  # the mask changes the run
        membership = {"schema": "membership/v1", "membership_id": "mem1", "intervals": intervals}
        ident = build_identity(archive, membership, [])
        ident.update(identity_id="idn1", created_utc="2026-11-18T00:00:00Z")
        for folder, name, doc in (("membership", "mem1", membership), ("identity", "idn1", ident)):
            (self.root / folder).mkdir(exist_ok=True)
            (self.root / folder / f"{name}.json").write_text(json.dumps(doc))
        if with_manifest:
            path = self.root / "membership" / "mem1.json"
            write_manifest(self.root, {
                "schema": "dataset-manifest/v1", "dataset_id": "mem1", "kind": "normalised",
                "created_utc": "2026-11-18T00:00:00Z", "source": "test", "inputs": [], "recipe": "r",
                "rights": {}, "files": [{"path": "membership/mem1.json", "sha256": sha256_file(path)}], "notes": "n"})
        wrap, block = analysis._universe({"membership": "mem1", "identity": "idn1"}, synthetic_fixture(), self.root)
        universe = {k: block[k] for k in ("membership_id", "identity_id")}
        (self.root / "manifests").mkdir(exist_ok=True)
        (self.root / "manifests" / "stock-ds.json").write_text("{}")  # presence only; the loader is injected
        datasets = {"dataset_id": "stock-ds", "manifest_sha256": "abc123", "universe_kind": "current-holdings-proxy"}
        run_id = self.screen(synthetic_fixture(), datasets, wrap=wrap, universe=universe)
        loader = lambda dataset_id, instruments, root: (synthetic_fixture(), {k: v for k, v in datasets.items() if k != "dataset_id"})  # noqa: E731
        return run_id, loader

    def test_masked_candidate_rebuilds_mask_and_verifies_hashes(self):
        run_id, loader = self.masked_root()
        manifest, _ = read_run(self.runs / run_id)
        self.assertEqual(manifest["config"]["universe"], {"membership_id": "mem1", "identity_id": "idn1"})
        code, _, err = self.run_main(run_id, loader=loader)
        self.assertEqual(code, 0, err)
        (native,) = self.native_runs()
        (receipt,) = self.receipts()
        self.assertEqual(native["config"]["universe"], {"membership_id": "mem1", "identity_id": "idn1"})
        self.assertEqual(native["labels"], ["survivor-biased", "discovery-only"])
        self.assertEqual(receipt["candidate"]["universe"], {"membership_id": "mem1", "identity_id": "idn1"})
        verified = receipt["universe_verified"]
        self.assertTrue(verified["membership_manifest_verified"])
        self.assertEqual(verified["membership_sha256"], sha(self.root / "membership" / "mem1.json"))
        self.assertEqual(verified["identity_sha256"], sha(self.root / "identity" / "idn1.json"))

    def test_masked_candidate_refused_when_membership_changed(self):
        run_id, loader = self.masked_root()
        path = self.root / "membership" / "mem1.json"
        doc = json.loads(path.read_text())
        doc["intervals"]["BBB"] = [{"start": synthetic_fixture().sessions[0], "end": None}]
        path.write_text(json.dumps(doc))
        code, _, err = self.run_main(run_id, loader=loader)
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertEqual(self.receipts(), [])

    def test_masked_candidate_refused_when_membership_absent(self):
        run_id, loader = self.masked_root()
        (self.root / "membership" / "mem1.json").unlink()
        code, _, err = self.run_main(run_id, loader=loader)
        self.assertEqual(code, 2)
        self.assertIn("data absent", err)

    def test_dirty_tree_refused_unless_allowed(self):
        run_id = self.fixture_run()
        code, out, err = self.run_main(run_id, commit=f"{CLEAN}+dirty")
        self.assertEqual(code, 1)
        self.assertIn("dirty", err)
        self.assertIn("--allow-dirty", err)
        self.assertEqual(self.receipts(), [])
        self.assertEqual(len(list(self.runs.iterdir())), 1)
        code, out, err = self.run_main(run_id, "--allow-dirty", commit=f"{CLEAN}+dirty")
        self.assertEqual(code, 0, err)
        self.assertIn("keep", err)  # warning: this receipt cannot back a keep
        (receipt,) = self.receipts()
        self.assertEqual(receipt["code_commit"], f"{CLEAN}+dirty")
        (native,) = self.native_runs()
        self.assertEqual(native["code_commit"], f"{CLEAN}+dirty")

    def test_mismatch_writes_mismatch_receipt_and_exits_1(self):
        run_id = self.fixture_run()

        def perturbed(data, target_fn, market):
            result = run_screen(data, target_fn, market)
            fills = result.fills.copy()
            fills.loc[0, "price"] += 0.05
            return dataclasses.replace(result, engine="nautilus", fills=fills)

        code, out, err = self.run_main(run_id, native_runner=perturbed)
        self.assertEqual(code, 1)
        (receipt,) = self.receipts()
        self.assertEqual((receipt["status"], receipt["passed"]), ("mismatch", False))
        self.assertGreater(receipt["mismatch_count"], 0)
        self.assertTrue(receipt["mismatches"])
        self.assertIn("mismatch", out + err)
        self.assertEqual(len(self.native_runs()), 1)  # evidence kept, never overwritten
        self.assertEqual(receipt["run_id"], self.native_runs()[0]["run_id"])

    def test_no_registry_ledger_or_acceptance_written(self):
        before = {p: p.read_bytes() for p in Path(analysis.ROOT, "research/registry").rglob("*") if p.is_file()}
        run_id = self.fixture_run()
        code, _, err = self.run_main(run_id)
        self.assertEqual(code, 0, err)
        after = {p: p.read_bytes() for p in Path(analysis.ROOT, "research/registry").rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        written = sorted(p.relative_to(self.root).parts[0] for p in self.root.iterdir())
        self.assertEqual(written, ["parity", "runs"])
        self.assertEqual(list(self.root.rglob("acceptance.json")), [])
        self.assertEqual(list(self.root.rglob("*.jsonl")), [])

    def test_missing_data_exits_2(self):
        code, out, err = self.run_main("20260101T000000Z-absent00")
        self.assertEqual(code, 2)
        self.assertIn("blocked: data absent", err)
        data, datasets = self.dataset_root()
        run_id = self.screen(data, datasets, strategy=BUY_HOLD)
        (self.root / "manifests" / f"{ID}.json").unlink()
        code, _, err = self.run_main(run_id)
        self.assertEqual(code, 2)
        self.assertIn("blocked: data absent", err)

    def test_native_engine_failure_is_a_refusal_not_a_traceback(self):
        from research.evaluation.engine_contract import EngineError

        def failing(data, target_fn, market):
            raise EngineError("order O-1 not accepted: Exceeded MAX_ORDER_SUBMIT_RATE")

        run_id = self.fixture_run()
        code, _, err = self.run_main(run_id, native_runner=failing)
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertIn("MAX_ORDER_SUBMIT_RATE", err)
        self.assertEqual(self.receipts(), [])
        self.assertEqual(len(list(self.runs.iterdir())), 1)  # no native run written


if __name__ == "__main__":
    unittest.main()
