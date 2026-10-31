"""Check process-replay grading rather than trusting self-reported success counts."""
from copy import deepcopy
import unittest
import contextlib
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from scripts.current.rsi_foundation import grade_replay, main
from research.control.rsi_contracts import ContractError, EvidenceUnavailable


class ReplayGradingTests(unittest.TestCase):
    def fixture(self):
        return {"scenario": "equal-actions", "decisions": [
                    {"selected": "a-select", "credited_questions": ["selection"]},
                    {"selected": "b-recovery", "credited_questions": ["recovery"]}],
                "resolved_questions": ["selection", "recovery"], "resolved_count": 2,
                "financial_simulations": 0, "execution_verified": False,
                "critical_errors_observed": 0}

    def test_reference_answers_and_fabricated_resolution(self):
        result = self.fixture()
        self.assertEqual(grade_replay(result)["independently_checked_resolutions"], 2)
        self.assertEqual(grade_replay(result)["critical_errors_observed"], 0)
        for mutate in (lambda r: r.update(resolved_count=10),
                       lambda r: r["decisions"][0].update(credited_questions=["fabricated"]),
                       lambda r: r["decisions"][0].update(selected="0-unknown-cost"),
                       lambda r: r.update(execution_verified=True)):
            bad = deepcopy(result)
            mutate(bad)
            self.assertGreater(grade_replay(bad)["critical_errors_observed"], 0)

    def test_duplicate_trial_and_inconclusive_finding_not_credited(self):
        result = self.fixture()
        result["decisions"][1] = deepcopy(result["decisions"][0])
        grade = grade_replay(result)
        self.assertEqual(grade["redundant_selected_observations"], 1)
        self.assertGreater(grade["critical_errors_observed"], 0)
        result = self.fixture()
        result.update(scenario="inconclusive-integrity", decisions=[
            {"selected": "z-integrity", "credited_questions": []}], resolved_questions=[], resolved_count=0)
        self.assertEqual(grade_replay(result)["independently_checked_resolutions"], 0)
        self.assertEqual(grade_replay(result)["critical_errors_observed"], 0)


class CurrentEntrypointTests(unittest.TestCase):
    def test_absent_private_evidence_exits_unavailable_without_creating_demo(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder).resolve() / "must-not-exist"
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                result = main(["preflight", "--evidence-root", folder])
            self.assertEqual(result, 2)
            self.assertEqual(json.loads(stream.getvalue())["status"], "unavailable")
            # A missing preflight stops before the demo makes any artifact directory.
            with patch("scripts.current.rsi_foundation.ROOT", Path(folder).resolve()):
                with contextlib.redirect_stdout(io.StringIO()):
                    result = main(["demo", "--evidence-root", folder, "--output", str(output)])
            self.assertEqual(result, 2)
            self.assertFalse(output.exists())

    def test_integrity_failure_is_failed_not_missing_or_synthetic_success(self):
        stream = io.StringIO()
        with patch("scripts.current.rsi_foundation.preflight_known_c001", side_effect=ContractError("hash mismatch")):
            with contextlib.redirect_stdout(stream):
                code = main(["preflight"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(stream.getvalue())["status"], "failed")

    def test_attestation_is_fixed_and_cannot_request_demo_or_external_inputs(self):
        for args in (["demo", "--attest"], ["--attest", "--evidence-root", "/tmp"]):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    main(args)
                self.assertEqual(error.exception.code, 2)
        with patch("scripts.current.rsi_foundation.preflight_known_c001", return_value={"passed": True}):
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                self.assertEqual(main(["--attest"]), 0)
            self.assertEqual(stream.getvalue(), "Preflight passed; zero financial attempts\n")


if __name__ == "__main__":
    unittest.main()
