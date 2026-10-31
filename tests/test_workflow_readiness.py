"""Evidence-summary regressions only: no financial runs or broker access."""

import json
from pathlib import Path
import unittest

from research.workflow_readiness import REVIEW_CHECKS, ReviewCheck, summarize_review


ROOT = Path(__file__).resolve().parents[1]


def complete(review):
    return {name: ReviewCheck("met", reference="synthetic-reviewed-fixture")
            for name in REVIEW_CHECKS[review]}


class WorkflowReadinessTests(unittest.TestCase):
    def test_complete_declarations_are_not_execution_or_independent_proof(self):
        for review in REVIEW_CHECKS:
            result = summarize_review(review, complete(review))
            self.assertEqual(result["status"], "supported_by_declared_checks")
            self.assertFalse(result["authorizes_execution"])
            self.assertFalse(result["independently_verified"])

    def test_missing_evidence_stays_unknown(self):
        result = summarize_review("paper_handoff", {})
        self.assertEqual(result["status"], "unverified_missing_checks")
        self.assertEqual(len(result["unknown"]), len(REVIEW_CHECKS["paper_handoff"]))

    def test_exhausted_budget_expired_deadline_and_repeated_deadend_block(self):
        for name, reason in [
            ("budget_remaining", "All reserved attempts consumed"),
            ("deadline_open", "Frozen deadline expired"),
            ("distinct_mechanism", "Repeats rejected sizing mechanism without new evidence"),
        ]:
            checks = complete("research_selection")
            checks[name] = ReviewCheck("failed", reason=reason)
            self.assertEqual(summarize_review("research_selection", checks)["failed"], [name])

    def test_noncomparable_metrics_cannot_support_ranking(self):
        checks = complete("calmar_comparison")
        checks["metric_conventions"] = ReviewCheck(
            "failed", reason="Intraday and daily-close drawdown conventions differ")
        result = summarize_review("calmar_comparison", checks)
        self.assertEqual(result["status"], "blocked_by_declared_checks")

    def test_paper_stale_unqualified_unknown_submit_and_restart(self):
        for name, reason in [
            ("fresh_inputs", "Quote expired under frozen session policy"),
            ("qualified_inputs", "Prototype normalization is unqualified"),
            ("no_unresolved_submissions", "Timed-out submission is unknown, not rejected"),
            ("restart_recovery", "No account-wide restart reconciliation proof"),
        ]:
            checks = complete("paper_handoff")
            checks[name] = ReviewCheck("failed", reason=reason)
            result = summarize_review("paper_handoff", checks)
            self.assertEqual(result["failed"], [name])
            self.assertFalse(result["authorizes_execution"])

    def test_saved_t11_aggregate_match_does_not_supply_daily_reproduction(self):
        receipt = json.loads((ROOT / "docs/tasks/evidence/2026-10-29-t11-export-validation.json").read_text())
        self.assertTrue(all(case["legacy_aggregate_comparison"]["aggregate_match"]
                            for case in receipt["cases"].values()))
        self.assertFalse(receipt["original_daily_decision_trace"])
        result = summarize_review("daily_reproduction", {
            "daily_decision_reference": ReviewCheck("unknown", reason="Original daily trace missing"),
        })
        self.assertIn("daily_decision_reference", result["unknown"])
        self.assertNotEqual(result["status"], "supported_by_declared_checks")

    def test_saved_t11_preview_remains_unqualified(self):
        receipt = json.loads((ROOT / "docs/tasks/evidence/2026-10-29-t11-paper-rehearsal.json").read_text())
        self.assertFalse(receipt["order_bearing_ready"])
        self.assertEqual(receipt["broker_submissions"], 0)
        result = summarize_review("paper_handoff", {
            "qualified_inputs": ReviewCheck("failed", reason=receipt["missing"][0]),
            "restart_recovery": ReviewCheck("unknown", reason=receipt["missing"][2]),
        })
        self.assertEqual(result["status"], "blocked_by_declared_checks")

    def test_typos_and_unsupported_claims_fail_explicitly(self):
        with self.assertRaises(ValueError):
            summarize_review("paper_handoff", {"aggregate_compatible": ReviewCheck("met", "x")})
        with self.assertRaises(ValueError):
            ReviewCheck("met")
        with self.assertRaises(ValueError):
            ReviewCheck("unknown")
        with self.assertRaises(ValueError):
            ReviewCheck("ready", "x")


if __name__ == "__main__":
    unittest.main()
