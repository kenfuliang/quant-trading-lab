import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research.control import run_refs
from research.control.experiment_registry import RegistryError

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "validation-receipt-pass.json"


def write(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, sort_keys=True))
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReaderTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_run_manifest_round_trip_and_sha_check(self):
        sha = write(self.root / "R1" / "manifest.json", {"run_id": "R1", "engine": "screen"})
        manifest, found = run_refs.read_run_manifest(self.root, "R1", sha)
        self.assertEqual((manifest["engine"], found), ("screen", sha))
        with self.assertRaisesRegex(RegistryError, "sha256 mismatch"):
            run_refs.read_run_manifest(self.root, "R1", "0" * 64)

    def test_missing_file_and_unsafe_ids_raise_registry_error(self):
        with self.assertRaisesRegex(RegistryError, "not found"):
            run_refs.read_run_manifest(self.root, "nope")
        for bad in ("../x", "a/b", "..", "", ".hidden", "a..b", None):
            with self.subTest(bad=bad), self.assertRaisesRegex(RegistryError, "safe path segment"):
                run_refs.read_run_manifest(self.root, bad)
            with self.subTest(parity=bad), self.assertRaisesRegex(RegistryError, "safe path segment"):
                run_refs.read_parity_receipt(self.root, bad)

    def test_manifest_naming_another_run_is_refused(self):
        write(self.root / "R1" / "manifest.json", {"run_id": "R2"})
        with self.assertRaisesRegex(RegistryError, "different run_id"):
            run_refs.read_run_manifest(self.root, "R1")

    def test_parity_receipt_round_trip(self):
        sha = write(self.root / "P1" / "receipt.json", {"parity_id": "P1", "status": "passed"})
        receipt, found = run_refs.read_parity_receipt(self.root, "P1", sha)
        self.assertEqual((receipt["status"], found), ("passed", sha))

    def test_invalid_json_is_a_registry_error(self):
        (self.root / "R1").mkdir()
        (self.root / "R1" / "manifest.json").write_text("{nope")
        with self.assertRaisesRegex(RegistryError, "not valid JSON"):
            run_refs.read_run_manifest(self.root, "R1")

    def test_validation_receipt_fixture_checks(self):
        doc = json.loads(FIXTURE.read_text())
        doc["run_ids"] = ["R1", "N1"]
        sha = write(self.root / "VR-fixture.json", doc)
        run_refs.read_validation_receipt(self.root, "VR-fixture", sha, ["R1", "N1"])
        with self.assertRaisesRegex(RegistryError, "does not cover"):
            run_refs.read_validation_receipt(self.root, "VR-fixture", sha, ["R1", "OTHER"])
        for change in ({"result": "fail"}, {"schema": "other/v1"}):
            sha = write(self.root / "VR-fixture.json", {**doc, **change})
            with self.subTest(change=change), self.assertRaises(RegistryError):
                run_refs.read_validation_receipt(self.root, "VR-fixture", sha, ["R1"])

    def test_financial_run_requirements(self):
        good = {"run_id": "R1", "use": "financial", "datasets": {"quality_status": "pass"}}
        run_refs.require_financial_run(good)
        accepted = {"run_id": "R1", "use": "financial", "datasets": {
            "quality_status": "pass-with-exceptions", "acceptance": {"status": "accepted", "acceptance_sha256": "a" * 64}}}
        run_refs.require_financial_run(accepted)
        bad = [{**good, "use": "engineering"}, {"run_id": "R1", "datasets": {"quality_status": "pass"}},
               {**good, "datasets": {"quality_status": "fail"}},
               {**good, "datasets": {"quality_status": "pass-with-exceptions"}}]
        for manifest in bad:
            with self.subTest(manifest=manifest), self.assertRaises(RegistryError):
                run_refs.require_financial_run(manifest)

    def test_parity_requirements(self):
        good = {"parity_id": "P1", "status": "passed", "passed": True, "mismatch_count": 0,
                "code_commit": "abc123", "runs": {"nautilus": {"run_id": "N1"}}}
        run_refs.require_passed_parity(good)
        run_refs.require_passed_parity({**good, "runs": {"nautilus": {"run_id": "N2"}}})  # candidate run may differ
        bad = [{**good, "status": "failed"}, {**good, "mismatch_count": 2}, {**good, "code_commit": "abc+dirty"},
               {**good, "passed": False}]
        for receipt in bad:
            with self.subTest(receipt=receipt), self.assertRaises(RegistryError):
                run_refs.require_passed_parity(receipt)

    def test_confirmation_must_name_exactly_the_cited_runs(self):
        good = {"parity_id": "P1", "kind": "candidate-confirmation", "stored_screen_identical": True,
                "bindable": True, "runs": {"screen": {"run_id": "S1", "manifest_sha256": "a" * 64},
                                           "nautilus": {"run_id": "N1", "manifest_sha256": "b" * 64}}}
        cited = ("S1", "a" * 64, "N1", "b" * 64)
        run_refs.require_confirmation(good, *cited)
        runs = good["runs"]
        bad = {
            "kind": {**good, "kind": None},
            "foreign native run": {**good, "runs": {**runs, "nautilus": {"run_id": "N9", "manifest_sha256": "b" * 64}}},
            "native sha": {**good, "runs": {**runs, "nautilus": {"run_id": "N1", "manifest_sha256": "c" * 64}}},
            "stale screen run": {**good, "runs": {**runs, "screen": {"run_id": "S0", "manifest_sha256": "a" * 64}}},
            "screen sha": {**good, "runs": {**runs, "screen": {"run_id": "S1", "manifest_sha256": "d" * 64}}},
            "no runs": {k: v for k, v in good.items() if k != "runs"},
            "not identical": {**good, "stored_screen_identical": False},
            "not bindable": {**good, "bindable": False},
        }
        for label, receipt in bad.items():
            with self.subTest(label), self.assertRaises(RegistryError):
                run_refs.require_confirmation(receipt, *cited)
        with self.assertRaisesRegex(RegistryError, "runs.nautilus"):
            run_refs.require_confirmation(bad["foreign native run"], *cited)
        with self.assertRaisesRegex(RegistryError, "candidate-confirmation"):
            run_refs.require_confirmation(bad["kind"], *cited)


if __name__ == "__main__":
    unittest.main()
