"""Observable scoring boundaries; synthetic accounting outcomes are not market evidence."""
import copy
import hashlib
import json
import math
import unittest

from research.scoring import (POLICY, POLICY_HASH, POLICY_VERSION, assess_evidence,
                              score_strategy, pareto_front, rank_actions)


def gate(status="pass", context="same", stage="development"):
    return assess_evidence([{"name": "integrity", "status": status, "applicable": True,
                            "evidence": ["receipt#integrity"] if status != "unknown" else [],
                            "reason": "missing proof"}], stage=stage, context_id=context,
                           required_checks=["integrity"])


def score(name="a", cagr=.1, dd=.2, state="pass", context="same", units=None, extra=None):
    return score_strategy(candidate_id=name, context_id=context, eligibility=gate(state, context),
                          metrics={"net_cagr": cagr, "max_drawdown": dd, **(extra or {})},
                          evidence=["ledger.csv"], units=units)


def action(name="a", question="q", observation="obs", cls=2, value=2, cost=1):
    return {"id": name, "context_id": "same", "question_id": question,
            "observation_key": observation, "class": cls, "decision_value": value,
            "shared_questions": [question], "cost_upper_bound": cost,
            "evidence": ["plan.json#question"],
            "witness": [{"observation": "advantage positive", "decision": "retain"},
                        {"observation": "advantage negative", "decision": "retire"}]}


class ScoringTests(unittest.TestCase):
    def test_invalid_high_return_never_ranked(self):
        x=score(cagr=1.5, dd=.01, state="fail")
        self.assertFalse(x["rankable"])
        self.assertEqual(pareto_front([x])["front"], [])
        self.assertEqual(x["metrics"]["net_cagr"],1.5)

    def test_unknown_is_blocked_not_failure_or_zero(self):
        x=gate("unknown")
        self.assertEqual(x["state"],"blocked")
        self.assertEqual(x["failed"],[])
        self.assertEqual(x["unknown"],["integrity"])

    def test_optional_unknown_does_not_claim_permission(self):
        checks=gate()["checks"]+[{"name":"redistribution_rights","status":"unknown",
                                  "applicable":True,"evidence":[],"reason":"not established"}]
        x=assess_evidence(checks,stage="internal_accounting_read",context_id="same",required_checks=["integrity"])
        self.assertEqual(x["state"],"eligible")
        self.assertEqual(x["checks"][-1]["status"],"unknown")
        self.assertFalse(x["checks"][-1]["required"])

    def test_stage_independence_gate_blocks_confirmation(self):
        x=assess_evidence(gate()["checks"],stage="confirmation",context_id="same",
                          required_checks=["integrity","unused_evaluation"])
        self.assertEqual(x["state"],"blocked")
        self.assertEqual(x["unknown"],["unused_evaluation"])

    def test_required_unknown_cannot_be_relabelled_nonapplicable(self):
        with self.assertRaises(ValueError):
            assess_evidence([{"name":"integrity","status":"not_applicable","applicable":False,
                              "evidence":[],"reason":"prefer to skip"}],stage="development",
                            context_id="same",required_checks=["integrity"])

    def test_no_vacuous_eligibility_or_fabricated_pass(self):
        with self.assertRaises(ValueError):
            assess_evidence([],stage="development",context_id="same",required_checks=[])
        with self.assertRaises(ValueError):
            assess_evidence([{"name":"x","status":"pass","applicable":True}],
                            stage="development",context_id="same",required_checks=["x"])

    def test_gate_average_cannot_rescue_required_failure(self):
        checks=[{"name":str(i),"status":"pass","applicable":True,"evidence":["r"]} for i in range(9)]
        checks += [{"name":"leak","status":"fail","applicable":True,"evidence":["future-label.csv"]}]
        x=assess_evidence(checks,stage="development",context_id="same",required_checks=[c["name"] for c in checks])
        self.assertEqual(x["state"],"invalid")

    def test_missing_objective_remains_null(self):
        x=score(dd=None)
        self.assertIsNone(x["metrics"]["max_drawdown"])
        self.assertFalse(x["rankable"])
        self.assertEqual(pareto_front([x])["excluded"][0]["missing_objectives"],["max_drawdown"])

    def test_zero_variance_ratios_not_infinity(self):
        x=score(cagr=0,dd=0,extra={"sharpe":None,"calmar":None})
        self.assertIsNone(x["metrics"]["sharpe"])
        self.assertIsNone(x["metrics"]["calmar"])

    def test_no_samples_cannot_rank(self):
        for n in [None,0]:
            x=score(extra={"sample_count":n})
            self.assertFalse(x["rankable"])
        for n in [-1,2.5]:
            with self.assertRaises(ValueError):score(extra={"sample_count":n})

    def test_insolvency_metrics_not_clipped(self):
        x=score(cagr=None,dd=1.05,extra={"terminal_equity":-5})
        self.assertEqual(x["metrics"]["max_drawdown"],1.05)
        self.assertFalse(x["rankable"])
        with self.assertRaises(ValueError):score(cagr=-1)

    def test_tradeoff_and_exact_ties_retained(self):
        self.assertEqual(pareto_front([score("a",.12,.25),score("b",.08,.15)])["front"],["a","b"])
        self.assertEqual(pareto_front([score("a"),score("b")])["front"],["a","b"])

    def test_dominated_candidate_identified(self):
        x=pareto_front([score("a",.12,.15),score("b",.08,.2)])
        self.assertEqual(x["front"],["a"])
        self.assertEqual(x["dominated_by"]["b"],["a"])

    def test_percent_rescaling_invariant(self):
        x=pareto_front([score("fraction",.12,.15),score("percent",12,15,
                         units={"net_cagr":"percent","max_drawdown":"percent"})])
        self.assertEqual(x["front"],["fraction","percent"])

    def test_mixed_context_or_stage_rejected(self):
        with self.assertRaises(ValueError):pareto_front([score("a"),score("b",context="other")])
        x=score("b");x["stage"]="confirmation"
        with self.assertRaises(ValueError):pareto_front([score("a"),x])

    def test_nonfinite_bool_strings_and_negative_units_rejected(self):
        for bad in [float("nan"),float("inf"),float("-inf"),True,"0.1"]:
            with self.assertRaises(ValueError):score(cagr=bad)
        with self.assertRaises(ValueError):score(dd=-.1)
        with self.assertRaises(ValueError):score(units={"net_cagr":"USD"})

    def test_pareto_rechecks_mutated_nonfinite(self):
        x=score();x["metrics"]["sharpe"]=float("inf")
        with self.assertRaises(ValueError):pareto_front([x])

    def test_priority_is_lexicographic_not_return_blend(self):
        a=action("a",cls=1,cost=0);a["CAGR"]=100
        b=action("b",observation="other",cls=3,cost=2)
        self.assertEqual(rank_actions([a,b],context_id="same",budget_remaining=2)["selected"]["id"],"b")

    def test_informative_negative_has_same_witness_priority(self):
        a=action();b=action("b",observation="other")
        a["expected_favorable_return"]=False;b["expected_favorable_return"]=True
        x=rank_actions([b,a],context_id="same",budget_remaining=1)
        self.assertEqual(x["selected"]["id"],"a")
        self.assertEqual(x["ranked"][0]["priority_tuple"],x["ranked"][1]["priority_tuple"])

    def test_renamed_shared_observation_credited_once(self):
        a=action();b=action("renamed",question="different_question")
        x=rank_actions([b,a],context_id="same",budget_remaining=5)
        self.assertEqual(len(x["ranked"]),1)
        self.assertEqual(x["excluded"][0]["state"],"duplicate")

    def test_unknown_and_zero_value_excluded(self):
        xs=[action("unknown_value",value=None),action("unknown_cost",cost=None),action("irrelevant",value=0)]
        x=rank_actions(xs,context_id="same",budget_remaining=5)
        self.assertIsNone(x["selected"])
        self.assertEqual(len(x["excluded"]),3)

    def test_budget_exhaustion_and_zero_cost_no_division(self):
        x=rank_actions([action()],context_id="same",budget_remaining=0)
        self.assertIsNone(x["selected"])
        self.assertIsNotNone(rank_actions([action(cost=0)],context_id="same",budget_remaining=0)["selected"])

    def test_action_context_and_malformed_witness_rejected(self):
        with self.assertRaises(ValueError):rank_actions([action()],context_id="other",budget_remaining=1)
        a=action();a["witness"][1]["decision"]="retain"
        with self.assertRaises(ValueError):rank_actions([a],context_id="same",budget_remaining=1)

    def test_shared_question_cap_and_input_preservation(self):
        a=action();a["shared_questions"]=["q","q","q2","q3"]
        original=copy.deepcopy(a)
        x=rank_actions([a],context_id="same",budget_remaining=1)
        self.assertEqual(x["selected"]["priority_tuple"][2],2)
        self.assertEqual(a,original)

    def test_forged_eligibility_state_rejected(self):
        x=gate("fail");x["state"]="eligible"
        with self.assertRaises(ValueError):
            score_strategy(candidate_id="x",context_id="same",eligibility=x,
                           metrics={"net_cagr":.5,"max_drawdown":.1},evidence=["r"])

    def test_fractional_priority_classes_rejected(self):
        for key in ["class","decision_value"]:
            a=action();a[key]=2.0
            with self.assertRaises(ValueError):rank_actions([a],context_id="same",budget_remaining=1)

    def test_policy_identity_and_no_fake_critic(self):
        expected=hashlib.sha256(json.dumps(POLICY,sort_keys=True,separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(POLICY_HASH,expected)
        for x in [gate(),score(),pareto_front([]),rank_actions([],context_id="same",budget_remaining=0)]:
            self.assertEqual(x["policy_hash"],expected)
            self.assertEqual(x["policy_version"],POLICY_VERSION)
        self.assertIsNone(POLICY["EVSI"])
        self.assertFalse(POLICY["learned_critic"])
        self.assertFalse(POLICY["GAE"])


if __name__ == "__main__":unittest.main()
