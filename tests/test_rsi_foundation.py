"""Check process-replay grading rather than trusting self-reported success counts."""
from copy import deepcopy
import unittest

from scripts.rsi_foundation import grade_replay


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


if __name__ == "__main__":
    unittest.main()
