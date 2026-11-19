import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from research.control import run_refs
from research.control import validation_receipts as vr
from research.control.experiment_registry import RegistryError
from scripts import validation as cli

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "validation-receipt-pass.json"


def good(**fields):
    doc = json.loads(FIXTURE.read_text())
    doc.update(receipt_id="VR1", run_ids=["R1", "N1"], **fields)
    return doc


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def write(self, doc, name="VR1"):
        path = self.dir / f"{name}.json"
        path.write_text(json.dumps(doc, sort_keys=True))
        return path

    def test_good_receipt_loads(self):
        self.assertEqual(vr.load_receipt(self.write(good()))["result"], "pass")

    def test_research_skill_cannot_validate(self):
        for skill in vr.RESEARCH_SKILLS:
            with self.subTest(skill=skill), self.assertRaisesRegex(vr.ValidationReceiptError, "Validation skill"):
                vr.load_receipt(self.write(good(validator={"skill": skill})))

    def test_validator_must_not_be_among_researcher_skills(self):
        doc = good(researcher={"skills": ["trade-experiment", "trade-leakage-audit"]})
        with self.assertRaisesRegex(vr.ValidationReceiptError, "unknown researcher skills|must not be among"):
            vr.load_receipt(self.write(doc))

    def test_unknown_skill_rejected(self):
        with self.assertRaisesRegex(vr.ValidationReceiptError, "allowed"):
            vr.load_receipt(self.write(good(validator={"skill": "trade-made-up"})))
        with self.assertRaisesRegex(vr.ValidationReceiptError, "unknown researcher skills"):
            vr.load_receipt(self.write(good(researcher={"skills": ["trade-made-up"]})))

    def test_shape_and_pass_rules(self):
        base = good()
        bad = {"extra key": {**base, "x": 1},
               "wrong stem": {**base, "receipt_id": "OTHER"},
               "unsafe id": {**base, "receipt_id": "../x"},
               "no run ids": {**base, "run_ids": []},
               "naive time": {**base, "created_utc": "2026-11-18T00:00:00"},
               "pass without checks": {**base, "checks": []},
               "pass with failed check": {**base, "checks": [{"name": "a", "status": "fail", "detail": "d"}]},
               "pass with empty detail": {**base, "checks": [{"name": "a", "status": "pass", "detail": " "}]},
               "pass with only waived checks": {**base, "checks": [{"name": "a", "status": "waived", "detail": "skipped"}]},
               "bad result": {**base, "result": "maybe"}}
        for label, doc in bad.items():
            with self.subTest(label), self.assertRaises(vr.ValidationReceiptError):
                vr.load_receipt(self.write(doc))
        mixed = {**base, "checks": [{"name": "a", "status": "waived", "detail": "n/a"},
                                    {"name": "b", "status": "pass", "detail": "ok"}]}
        vr.load_receipt(self.write(mixed))
        failed = {**base, "result": "fail", "checks": [{"name": "a", "status": "fail", "detail": ""}]}
        vr.load_receipt(self.write(failed))

    def test_receipt_parity_id_must_match_the_records(self):
        self.write(good())
        run_refs.read_validation_receipt(self.dir, "VR1", None, ["R1", "N1"], parity_id="P1")
        with self.assertRaisesRegex(RegistryError, "parity receipt"):
            run_refs.read_validation_receipt(self.dir, "VR1", None, ["R1", "N1"], parity_id="OTHER")

    def test_receipt_must_list_the_records_run_ids(self):
        self.write(good())
        run_refs.read_validation_receipt(self.dir, "VR1", None, ["R1", "N1"])
        with self.assertRaisesRegex(RegistryError, "does not cover"):
            run_refs.read_validation_receipt(self.dir, "VR1", None, ["R1", "OTHER"])

    def test_failed_validation_cannot_back_a_keep(self):
        self.write(good(result="fail"))
        with self.assertRaisesRegex(RegistryError, "not 'pass'"):
            run_refs.read_validation_receipt(self.dir, "VR1", None, ["R1"])

    def test_research_validator_is_rejected_by_the_log_time_reader(self):
        self.write(good(validator={"skill": "trade-experiment"}))
        with self.assertRaisesRegex(RegistryError, "Validation skill"):
            run_refs.read_validation_receipt(self.dir, "VR1", None, ["R1"])


class CommandTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name) / "receipts"

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main([*argv])
        return code, out.getvalue(), err.getvalue()

    def create_args(self, **over):
        values = {"--receipt-id": "VR1", "--parity-receipt-id": "P1", "--validator-skill": "trade-leakage-audit",
                  "--researcher-skills": "trade-experiment,trade-research-design", "--result": "pass",
                  "--notes": "n", "--dir": str(self.dir), **over}
        args = ["create", "--run-id", "R1", "--run-id", "N1", "--check", "leakage:pass:none in scope",
                "--check", "costs:waived:engineering run"]
        for key, value in values.items():
            args += [key, value]
        return args

    def test_create_writes_a_loadable_sorted_receipt_and_is_exclusive(self):
        code, _, err = self.run_cli(*self.create_args())
        self.assertEqual(code, 0, err)
        path = self.dir / "VR1.json"
        doc = vr.load_receipt(path)
        self.assertEqual(doc["run_ids"], ["R1", "N1"])
        self.assertEqual(doc["researcher"]["skills"], ["trade-experiment", "trade-research-design"])
        self.assertEqual(path.read_text(), json.dumps(doc, indent=2, sort_keys=True) + "\n")
        before = path.read_bytes()
        code, _, err = self.run_cli(*self.create_args())
        self.assertEqual(code, 1)
        self.assertEqual(path.read_bytes(), before)

    def test_create_validates_before_writing(self):
        code, _, err = self.run_cli(*self.create_args(**{"--validator-skill": "trade-experiment"}))
        self.assertEqual(code, 1)
        self.assertIn("Validation skill", err)
        self.assertFalse((self.dir / "VR1.json").exists())
        code, _, _ = self.run_cli(*self.create_args(**{"--validator-skill": "trade-leakage-audit",
                                                       "--researcher-skills": "trade-leakage-audit"}))
        self.assertEqual(code, 1)

    def test_check_command_passes_on_empty_directory(self):
        self.dir.mkdir()
        (self.dir / ".gitkeep").write_text("")
        code, out, _ = self.run_cli("check", "--dir", str(self.dir))
        self.assertEqual(code, 0)
        self.assertIn("Validation receipts passed: 0 receipts.", out)

    def test_check_command_names_the_bad_receipt(self):
        self.run_cli(*self.create_args())
        (self.dir / "VR2.json").write_text(json.dumps({"schema": vr.SCHEMA}))
        code, _, err = self.run_cli("check", "--dir", str(self.dir))
        self.assertEqual(code, 1)
        self.assertIn("VR2.json", err)

    def test_real_tracked_directory_passes(self):
        code, out, err = self.run_cli("check")
        self.assertEqual(code, 0, err)


if __name__ == "__main__":
    unittest.main()
