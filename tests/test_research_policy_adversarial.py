"""Fresh policy-boundary and matched synthetic replay evaluation.

These cases were authored after design review; outcomes are fictional deterministic
fixtures, not market observations or a statistically representative task sample.
The replay intentionally includes a priority win, loss and tie.
"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from research.scoring import assess_evidence, score_strategy, pareto_front, rank_actions
from research.research_controller import ResearchController


CTX = "fresh-adversarial-review"


def gate(status="pass", context=CTX, stage="development"):
    return assess_evidence([{"name": "timing", "status": status, "applicable": True,
                             "evidence": ["fixture:timing"] if status != "unknown" else [],
                             "reason": "availability timestamp is missing" if status == "unknown" else "fixture assertion"}],
                           stage=stage, context_id=context, required_checks=["timing"])


def scored(name="candidate", *, status="pass", context=CTX, metrics=None, units=None):
    return score_strategy(candidate_id=name, context_id=context,
                          eligibility=gate(status, context),
                          metrics=metrics or {"net_cagr": .10, "max_drawdown": .20, "sample_count": 43},
                          units=units, evidence=["fixture:account"])


def replay_case(scenario, policy):
    """Two logical actions/two resource units, identical gates/candidate definitions."""
    if scenario not in {"shared-integrity", "inconclusive-integrity", "equal-actions"}:
        raise ValueError("unknown fixture")
    with tempfile.TemporaryDirectory() as folder:
        with ResearchController(folder, context={"score_version": "fresh-fixture", "scenario": scenario},
                                budget={"max_attempts": 2, "max_resource_units": 2,
                                        "resource_unit": "fixture_unit", "max_active_branches": 3}) as c:
            for q in ("selection", "recovery", "cost"):
                c.register_question("q-" + q, q, {"estimand": q, "fixture": scenario})
                c.register_branch("b-" + q, branch_id=q, question_id=q, mechanism=q)
            def action(id, q, cls, shared=None):
                return {"id": id, "branch_id": q, "question_id": q, "context_id": c.context_id,
                        "observation_key": id, "observation_spec": {"fixture": scenario, "check": q},
                        "class": cls, "decision_value": 2, "shared_questions": shared or [],
                        "cost_upper_bound": 1, "evidence": ["fixture:documented-" + q + "-question"],
                        "witness": [{"observation": "valid", "decision": "retain"},
                                    {"observation": "invalid", "decision": "reject"}]}
            actions = [action("a-select", "selection", 1), action("b-recovery", "recovery", 1)]
            if scenario != "equal-actions":
                actions.append(action("z-integrity", "cost", 3, ["recovery"]))
            unknown = action("0-unknown-cost", "cost", 3)
            unknown["cost_upper_bound"] = None
            actions.append(unknown)
            canonical = json.dumps(actions, sort_keys=True, separators=(",", ":"))
            decisions = []
            for iteration in range(2):
                trace = c.preview(actions, policy=policy)
                selected = trace["selected"]
                if selected is None:
                    break
                reservation = c.select("select-" + str(iteration), selected)
                identity = selected["id"]
                questions = [] if identity == "z-integrity" and scenario == "inconclusive-integrity" else [selected["question_id"]]
                if identity == "z-integrity" and scenario == "shared-integrity":
                    questions.append("recovery")
                evidence = "fixture-receipt:" + scenario + ":" + identity
                result = c.record("record-" + str(iteration), reservation["attempt_id"], {
                    "status": "completed", "summary": "Synthetic finding only; no financial result",
                    "evidence": [evidence], "actual_resource_units": 1,
                    "inspection_trace": ["Read frozen fictional outcome table", "Recorded a negative or inconclusive finding"],
                    "observation_kind": "synthetic_fixture",
                    "resolutions": [{"question_id": q, "decision": "reject", "finding": "Specified synthetic falsifier met", "evidence": [evidence]} for q in questions]})
                decisions.append({"selected": identity, "credited_questions": result["credited_questions"],
                                  "excluded": [{"id": x["id"], "state": x["state"]} for x in trace["excluded"]],
                                  "inspection_trace": result["inspection_trace"]})
            return {"scenario": scenario, "policy": policy,
                    "candidate_set_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
                    "decisions": decisions, "resolved_questions": c.state["resolved_questions"],
                    "resolved_count": len(c.state["resolved_questions"]), "usage": c.usage(),
                    "execution_verified": False, "financial_simulations": 0,
                    "critical_errors_observed": 0,
                    "critical_error_scope": "No blocked/unknown-cost action selected; no fabricated financial result or execution claim"}


class FreshScoringBoundaryTests(unittest.TestCase):
    def test_blocked_record_cannot_be_promoted_by_top_level_edits(self):
        s = scored(status="unknown")
        s.update(eligibility="eligible", rankable=True, missing_objectives=[])
        with self.assertRaisesRegex(ValueError, "canonical"):
            pareto_front([s])

    def test_finite_normalized_metric_edit_is_not_accepted(self):
        s = scored(metrics={"net_cagr": 10, "max_drawdown": 20},
                   units={"net_cagr": "percent", "max_drawdown": "percent"})
        s["metrics"]["net_cagr"] = 10
        with self.assertRaisesRegex(ValueError, "canonical"):
            pareto_front([s])

    def test_input_unit_or_raw_metric_change_without_rederivation_rejected(self):
        for field, key, value in [("raw_metrics", "net_cagr", .50),
                                  ("input_units", "max_drawdown", "percent")]:
            s = scored(); s[field][key] = value
            with self.assertRaisesRegex(ValueError, "canonical"):
                pareto_front([s])

    def test_edited_check_and_duplicated_projection_must_agree(self):
        s = scored()
        s["eligibility_checks"][0]["status"] = "fail"
        with self.assertRaisesRegex(ValueError, "canonical"):
            pareto_front([s])
        s = scored()
        s["eligibility_record"]["checks"][0]["status"] = "fail"
        with self.assertRaises(ValueError):
            pareto_front([s])

    def test_zero_sample_and_version_edits_cannot_bypass_derivation(self):
        s = scored(metrics={"net_cagr": .1, "max_drawdown": .2, "sample_count": 0})
        self.assertFalse(s["rankable"])
        s.update(rankable=True, missing_objectives=[])
        with self.assertRaises(ValueError):
            pareto_front([s])
        s = scored(); s["policy_version"] = "pre-results-version"
        with self.assertRaises(ValueError):
            pareto_front([s])

    def test_no_minimal_fabricated_score_without_canonical_inputs(self):
        from research.scoring import POLICY_HASH, POLICY_VERSION
        fake = {"candidate_id": "forged", "context_id": CTX, "stage": "development",
                "policy_hash": POLICY_HASH, "policy_version": POLICY_VERSION,
                "eligibility": "eligible", "rankable": True,
                "metrics": {"net_cagr": 9, "max_drawdown": 0}}
        with self.assertRaises(ValueError):
            pareto_front([fake])

    def test_consistent_percent_conversion_preserves_front_and_drawdown_over_one(self):
        a = scored("fraction", metrics={"net_cagr": .137, "max_drawdown": 1.2})
        b = scored("percent", metrics={"net_cagr": 13.7, "max_drawdown": 120},
                   units={"net_cagr": "percent", "max_drawdown": "percent"})
        self.assertEqual(pareto_front([a, b])["front"], ["fraction", "percent"])

    def test_confirmation_context_cannot_be_silently_relabelled(self):
        s = scored()
        s["context_id"] = "untouched-confirmation"
        s["stage"] = "confirmation"
        with self.assertRaises(ValueError):
            pareto_front([s])

    def test_missing_pass_pointer_rejected_but_truth_is_external_boundary(self):
        with self.assertRaises(ValueError):
            assess_evidence([{"name": "timing", "status": "pass", "applicable": True, "evidence": []}],
                            stage="development", context_id=CTX, required_checks=["timing"])
        # Explicitly characterize a limit, not a desired truth-verification feature:
        # a structurally valid nonexistent pointer is not dereferenced by scoring.
        asserted = assess_evidence([{"name": "timing", "status": "pass", "applicable": True,
                                     "evidence": ["nonexistent:caller-assertion"]}],
                                    stage="development", context_id=CTX, required_checks=["timing"])
        self.assertEqual(asserted["state"], "eligible")

    def test_invented_required_contract_is_not_authenticated_by_context_string(self):
        # The coordinator must bind the actual required checks into its frozen plan.
        asserted = assess_evidence([{"name": "cosmetic", "status": "pass", "applicable": True,
                                     "evidence": ["fictional:label"]}],
                                    stage="development", context_id=CTX, required_checks=["cosmetic"])
        s = score_strategy(candidate_id="caller-contract", context_id=CTX, eligibility=asserted,
                           metrics={"net_cagr": .1, "max_drawdown": .2}, evidence=["fictional:account"])
        self.assertEqual(pareto_front([s])["front"], ["caller-contract"])


class MatchedReplayTests(unittest.TestCase):
    def pair(self, scenario):
        a, b = replay_case(scenario, "priority"), replay_case(scenario, "breadth_first")
        self.assertEqual(a["candidate_set_sha256"], b["candidate_set_sha256"])
        self.assertEqual(a["usage"], b["usage"])
        self.assertEqual(a["usage"]["attempts"], 2)
        for arm in (a, b):
            self.assertEqual(arm["critical_errors_observed"], 0)
            self.assertFalse(arm["execution_verified"])
            self.assertEqual(arm["financial_simulations"], 0)
            self.assertTrue(all(d["selected"] != "0-unknown-cost" for d in arm["decisions"]))
        return a, b

    def test_shared_integrity_fixture_priority_resolves_more(self):
        a, b = self.pair("shared-integrity")
        self.assertEqual((a["resolved_count"], b["resolved_count"]), (3, 2))

    def test_inconclusive_integrity_fixture_priority_resolves_less(self):
        a, b = self.pair("inconclusive-integrity")
        self.assertEqual((a["resolved_count"], b["resolved_count"]), (1, 2))

    def test_equal_actions_fixture_ties(self):
        a, b = self.pair("equal-actions")
        self.assertEqual((a["resolved_count"], b["resolved_count"]), (2, 2))

    def test_replay_reconstruction_does_not_change_deterministic_result(self):
        # Repeated reconstruction verifies no dependence on prior temporary journals.
        first, second = replay_case("shared-integrity", "priority"), replay_case("shared-integrity", "priority")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
