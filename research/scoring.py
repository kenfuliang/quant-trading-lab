"""Stage-specific evidence, descriptive Pareto tradeoffs and bounded action priority.

No learned critic, GAE, expected information value or investment approval is
implemented. Callers freeze the applicable checks and comparison context first.
"""
from __future__ import annotations

import copy
from decimal import Decimal
import hashlib
import json
import math
from numbers import Real

POLICY_VERSION = "research-score-v0.2"
POLICY = {
    "version": POLICY_VERSION,
    "eligibility": "required applicable fail invalid; unknown blocked; no weighted average",
    "objectives": {"net_cagr": "maximize", "max_drawdown": "minimize magnitude"},
    "metric_units": "normalize primary percent via decimal text to fraction; undefined remains null; exact comparisons retained",
    "action_order": ["class desc", "decision_value desc", "unique shared questions capped2 desc", "cost_upper_bound asc", "id asc"],
    "action_classes": {"integrity": 3, "falsification": 2, "exploration": 1},
    "observation_credit": "one observation_key per context; exclude duplicate and zero-value actions",
    "decision_witness": "value2 distinct observation regions and distinct decisions; value1 named uncertainty observation",
    "required_applicability": "required checks cannot be exempted with not_applicable; choose required list per frozen stage",
    "sample_count": "if supplied, nonnegative integer; null or zero blocks strategy comparison",
    "numeric_domains": "finite real nonbool; CAGR greater than-1 or null; drawdown magnitude nonnegative; ratios null when undefined",
    "context": "required nonempty stage and context; mixed stage/context/policy rejected",
    "score_integrity": "Pareto reconstructs the whole score from canonical eligibility, raw metrics and explicit units; inconsistent derived fields rejected",
    "evidence_boundary": "pointer existence/truth and frozen stage-required contract remain caller verification; records are not signed attestations",
    "EVSI": None,
    "learned_critic": False,
    "GAE": False,
}
POLICY_HASH = hashlib.sha256(json.dumps(POLICY, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _stamp():
    return {"policy_version": POLICY_VERSION, "policy_hash": POLICY_HASH}


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonempty string")
    return value


def _texts(value, field, *, nonempty=False):
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"{field} must be a list of strings")
    return [_text(item, field) for item in value]


def _number(value, field, *, nullable=False, minimum=None):
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number" + (" or null" if nullable else ""))
    value = float(value)
    if minimum is not None and value < minimum:
        raise ValueError(f"{field} must be >= {minimum}")
    return value


def assess_evidence(checks, *, stage, context_id, required_checks):
    """Assess explicitly supplied stage checks; omitted required checks are unknown.

    Check fields: name, status(pass/fail/unknown/not_applicable), applicable(bool),
    evidence(list of pointers), reason. Nonapplicability needs an explanation;
    pass/fail needs actual evidence. The caller supplies the frozen required list.
    """
    _text(stage, "stage"); _text(context_id, "context_id")
    names = _texts(required_checks, "required_checks", nonempty=True)
    if len(set(names)) != len(names) or not isinstance(checks, list):
        raise ValueError("required checks must be unique and checks must be a list")
    by_name = {}
    for raw in checks:
        if not isinstance(raw, dict):
            raise ValueError("each check must be a mapping")
        check = dict(raw)
        name = _text(check.get("name"), "check name")
        if name in by_name:
            raise ValueError("duplicate check: " + name)
        status = check.get("status")
        if status not in {"pass", "fail", "unknown", "not_applicable"}:
            raise ValueError("unknown check status")
        if not isinstance(check.get("applicable"), bool):
            raise ValueError("applicability must be explicit boolean")
        if (status == "not_applicable") != (check["applicable"] is False):
            raise ValueError("nonapplicability must use not_applicable status")
        check["evidence"] = _texts(check.get("evidence", []), "check evidence")
        if status in {"pass", "fail"} and not check["evidence"]:
            raise ValueError("pass/fail requires an evidence pointer")
        if status in {"unknown", "not_applicable"}:
            _text(check.get("reason"), "unknown/nonapplicable reason")
        if name in names and status == "not_applicable":
            raise ValueError("required check cannot be waived as not_applicable")
        check["required"] = name in names
        by_name[name] = check
    for name in names:
        if name not in by_name:
            by_name[name] = {"name": name, "status": "unknown", "applicable": True,
                             "required": True, "evidence": [], "reason": "required check missing"}
    failed = [n for n in names if by_name[n]["status"] == "fail"]
    unknown = [n for n in names if by_name[n]["status"] == "unknown"]
    state = "invalid" if failed else ("blocked" if unknown else "eligible")
    return {**_stamp(), "stage": stage, "context_id": context_id, "state": state,
            "required_checks": list(names), "failed": failed, "unknown": unknown,
            "checks": list(by_name.values())}


def score_strategy(*, candidate_id, context_id, eligibility, metrics, evidence, units=None):
    """Keep a nullable outcome vector; eligibility cannot be rescued by high returns.

    Primary keys are net_cagr and max_drawdown (positive loss magnitude). Units
    default to fractions; explicit percent values are normalized, while raw inputs
    remain recorded. Drawdown >1 is allowed for losses beyond initial equity.
    """
    _text(candidate_id, "candidate_id"); _text(context_id, "context_id")
    pointers = _texts(evidence, "evidence", nonempty=True)
    if not isinstance(eligibility, dict) or eligibility.get("policy_hash") != POLICY_HASH:
        raise ValueError("eligibility policy mismatch")
    if eligibility.get("policy_version") != POLICY_VERSION:
        raise ValueError("eligibility version mismatch")
    if eligibility.get("context_id") != context_id:
        raise ValueError("eligibility comparison context mismatch")
    if eligibility.get("state") not in {"eligible", "blocked", "invalid"}:
        raise ValueError("invalid eligibility state")
    verified = assess_evidence(eligibility.get("checks"), stage=eligibility.get("stage"),
                               context_id=context_id, required_checks=eligibility.get("required_checks"))
    if verified["state"] != eligibility["state"]:
        raise ValueError("eligibility state disagrees with checks")
    if not isinstance(metrics, dict) or not all(isinstance(k, str) and k for k in metrics):
        raise ValueError("metrics must be a named mapping")
    if units is None:
        units = {}
    if not isinstance(units, dict) or set(units) - {"net_cagr", "max_drawdown"}:
        raise ValueError("units may describe only primary objectives")
    normalized = {}
    for name, value in metrics.items():
        normalized[name] = _number(value, name, nullable=True)
    for name in ("net_cagr", "max_drawdown"):
        value = normalized.setdefault(name, None)
        unit = units.get(name, "fraction")
        if unit not in {"fraction", "percent"}:
            raise ValueError("unsupported primary metric unit")
        if value is not None:
            normalized[name] = float(Decimal(str(value)) / Decimal(100)) if unit == "percent" else value
    if normalized["max_drawdown"] is not None and normalized["max_drawdown"] < 0:
        raise ValueError("max_drawdown is a nonnegative loss magnitude")
    if normalized["net_cagr"] is not None and normalized["net_cagr"] <= -1:
        raise ValueError("CAGR outside positive-equity domain; use null and record insolvency")
    missing = [name for name in ("net_cagr", "max_drawdown") if normalized[name] is None]
    if "sample_count" in normalized:
        n = normalized["sample_count"]
        if n is not None and (n < 0 or not n.is_integer()):
            raise ValueError("sample_count must be a nonnegative integer or null")
        if n is None or n == 0:
            missing.append("sample_count")
    rankable = eligibility["state"] == "eligible" and not missing
    return {**_stamp(), "candidate_id": candidate_id, "context_id": context_id,
            "stage": eligibility["stage"], "eligibility": eligibility["state"],
            "rankable": rankable, "missing_objectives": missing,
            "raw_metrics": dict(metrics), "input_units": dict(units),
            "metrics": normalized, "evidence": pointers,
            "eligibility_record": copy.deepcopy(verified),
            "eligibility_checks": copy.deepcopy(verified["checks"])}


def pareto_front(scores):
    """Return descriptive nondominated candidates in one context, never a promotion.

    Undefined or invalid evidence is retained in excluded records, not imputed.
    Exact ties remain nondominated. Mixed contexts/stages/policies and inconsistent
    derived score records are errors. Canonical inputs still require independent
    provenance/contract verification; this function cannot authenticate source claims.
    """
    if not isinstance(scores, list):
        raise ValueError("scores must be a list")
    contexts = set(); stages = set(); identifiers = set()
    for score in scores:
        if not isinstance(score, dict) or score.get("policy_hash") != POLICY_HASH:
            raise ValueError("score policy mismatch")
        identifier = _text(score.get("candidate_id"), "candidate_id")
        if identifier in identifiers:
            raise ValueError("duplicate candidate identity")
        identifiers.add(identifier)
        contexts.add(_text(score.get("context_id"), "context_id"))
        stages.add(_text(score.get("stage"), "stage"))
        if not isinstance(score.get("rankable"), bool):
            raise ValueError("rankability must be explicit boolean")
        for key, value in score.get("metrics", {}).items():
            _number(value, key, nullable=True)
        # Inputs remain caller-supplied, but derived copies may not contradict them.
        # A hash alone would not authenticate a fabricated gate or edited metric.
        expected = score_strategy(candidate_id=identifier,
                                  context_id=score["context_id"],
                                  eligibility=score.get("eligibility_record"),
                                  metrics=score.get("raw_metrics"),
                                  evidence=score.get("evidence"),
                                  units=score.get("input_units"))
        if score != expected:
            raise ValueError("score disagrees with its canonical eligibility/raw metric inputs")
    if len(contexts) > 1 or len(stages) > 1:
        raise ValueError("incompatible comparison context or stage")
    good = [s for s in scores if s["rankable"]]
    dominated_by = {}
    for b in good:
        bm = b["metrics"]
        dominated_by[b["candidate_id"]] = sorted(a["candidate_id"] for a in good if
            a["metrics"]["net_cagr"] >= bm["net_cagr"] and
            a["metrics"]["max_drawdown"] <= bm["max_drawdown"] and
            (a["metrics"]["net_cagr"] > bm["net_cagr"] or
             a["metrics"]["max_drawdown"] < bm["max_drawdown"]))
    return {**_stamp(), "context_id": next(iter(contexts), None),
            "stage": next(iter(stages), None),
            "front": sorted(k for k, v in dominated_by.items() if not v),
            "dominated_by": dominated_by,
            "evidence": {s["candidate_id"]: list(s["evidence"]) for s in scores},
            "excluded": [{"candidate_id": s["candidate_id"], "eligibility": s["eligibility"],
                          "missing_objectives": s["missing_objectives"]} for s in scores if not s["rankable"]]}


def rank_actions(actions, *, context_id, budget_remaining):
    """Rank feasible next actions by fixed tuple, retaining every exclusion reason.

    Costs and budget use the caller's same declared resource units. A decision
    value2 witness has distinct observation and next-decision regions. This is an
    ordinal rubric, not an estimate of expected return/information or a critic.
    """
    _text(context_id, "context_id")
    budget = _number(budget_remaining, "budget_remaining", minimum=0)
    if not isinstance(actions, list):
        raise ValueError("actions must be a list")
    ids = set(); candidates = []; excluded = []
    for raw in actions:
        if not isinstance(raw, dict):
            raise ValueError("each action must be a mapping")
        a = dict(raw)
        aid = _text(a.get("id"), "action id")
        if aid in ids:
            raise ValueError("duplicate action id")
        ids.add(aid)
        if a.get("context_id") != context_id:
            raise ValueError("action context mismatch")
        _text(a.get("question_id"), "question_id")
        _text(a.get("observation_key"), "observation_key")
        a["evidence"] = _texts(a.get("evidence"), "action evidence", nonempty=True)
        cls = a.get("class"); value = a.get("decision_value")
        if isinstance(cls, bool) or not isinstance(cls, int) or cls not in (1, 2, 3):
            raise ValueError("action class must be1,2 or3")
        if isinstance(value, bool) or (value is not None and (not isinstance(value, int) or value not in (0, 1, 2))):
            raise ValueError("decision_value must be0,1,2 or null")
        shared = _texts(a.get("shared_questions", []), "shared_questions")
        if a["question_id"] not in shared:
            shared.append(a["question_id"])
        a["shared_questions"] = sorted(set(shared))
        cost = _number(a.get("cost_upper_bound"), "cost_upper_bound", nullable=True, minimum=0)
        reason = a.get("blocked_reason")
        if reason is not None:
            _text(reason, "blocked_reason")
        elif value is None:
            reason = "decision value unknown"
        elif cost is None:
            reason = "resource upper bound unknown"
        elif cost > budget:
            reason = "resource budget insufficient"
        elif value == 0:
            reason = "duplicate or no decision value"
        if reason:
            excluded.append({"id": aid, "state": "blocked" if value != 0 else "no_information", "reason": reason, "evidence": list(a["evidence"])})
            continue
        witness = a.get("witness")
        if not isinstance(witness, list) or not witness or not all(isinstance(w, dict) for w in witness):
            raise ValueError("scheduled action requires an executable witness")
        observations = {_text(w.get("observation"), "witness observation") for w in witness}
        decisions = {_text(w.get("decision"), "witness decision") for w in witness}
        if value == 2 and (len(observations) < 2 or len(decisions) < 2):
            raise ValueError("decision-changing witness requires distinct observations and decisions")
        a["cost_upper_bound"] = cost
        a["priority_tuple"] = [cls, value, min(2, len(a["shared_questions"])), -cost]
        candidates.append(a)
    candidates.sort(key=lambda a: (-a["class"], -a["decision_value"],
                                   -min(2, len(a["shared_questions"])), a["cost_upper_bound"], a["id"]))
    ranked = []; observations = set()
    for a in candidates:
        if a["observation_key"] in observations:
            excluded.append({"id": a["id"], "state": "duplicate", "reason": "observation already represented", "evidence": list(a["evidence"])})
        else:
            observations.add(a["observation_key"])
            ranked.append(a)
    return {**_stamp(), "context_id": context_id, "budget_remaining": budget,
            "ranked": ranked, "excluded": excluded,
            "selected": ranked[0] if ranked else None,
            "state": "ready" if ranked else "no_feasible_action"}
