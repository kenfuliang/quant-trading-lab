"""Stage view model: where each record sits in the pipeline and what each matched pair shows.

A challenger is a record tagged `challenger` or a record whose reviewed stage-map entry names a
control: the reviewed sidecar is the authority, so a record the registry could not tag (it is
immutable) can still be paired.

Pure functions over registry records and the reviewed stage map. A stage effect is only
computed for a matched pair (a challenger and the control the stage map names, in the same
context). Effects use Pareto dominance on the two policy objectives; Sharpe, Calmar and
underwater length are diagnostics and never decide an effect. Nothing here blends metrics
or rolls a cell up to one label.
"""
from research.control.registry_views import dominates
from research.control.stage_map import MULTIPLE, STAGES

POLICY_METRICS = ("net_cagr", "max_drawdown")
DIAGNOSTIC_METRICS = ("calmar", "sharpe", "longest_underwater_sessions", "longest_underwater_days")
AMBIGUOUS = "ambiguous control"


def classify(record, entry):
    """A stage name, "unclassified" (no reviewed entry or stage) or "unattributable"."""
    if entry is None or not entry["reviewed"] or entry["stage_under_test"] is None:
        return "unclassified"
    if entry["stage_under_test"] == MULTIPLE:
        return "unattributable"
    return entry["stage_under_test"]


def effect(challenger, control):
    """improved, worse, tie, tradeoff, or unmeasured when a policy metric is missing."""
    if any(m.get(k) is None for m in (challenger, control) for k in POLICY_METRICS):
        return "unmeasured"
    if dominates(challenger, control):
        return "improved"
    if dominates(control, challenger):
        return "worse"
    if all(challenger[k] == control[k] for k in POLICY_METRICS):
        return "tie"
    return "tradeoff"


def _context(record):
    return record["context"]["code"], record["context"]["period"]


def _bump(counts, key):
    counts[key] = counts.get(key, 0) + 1


def _pair(challenger, entry, by_id):
    control = by_id.get(entry["control"]) if entry["control"] else None
    matched = control is not None and _context(control) == _context(challenger)
    pair = {"challenger": challenger["record_id"], "control": entry["control"],
            "status": "matched" if matched else AMBIGUOUS, "effect": None,
            "disposition": challenger["disposition"], "delta": {}}
    if matched:
        cm, km = challenger["metrics"], control["metrics"]
        pair["effect"] = effect(cm, km)
        pair["delta"] = {k: (cm[k] - km[k] if cm.get(k) is not None and km.get(k) is not None else None)
                         for k in POLICY_METRICS + DIAGNOSTIC_METRICS}
    return pair


def build_model(records, stage_map):
    """{"stages": per-stage cells for every stage, "unclassified": [id], "unattributable": [id],
    "contexts": {"code · period": [id]}}. Cells count records, list pairs, and count pair effects
    (a pair with no matched control counts as "ambiguous control") and challenger dispositions."""
    by_id = {r["record_id"]: r for r in records}
    stages = {s: {"records": [], "pairs": [], "effects": {}, "dispositions": {}} for s in STAGES}
    model = {"stages": stages, "unclassified": [], "unattributable": [], "contexts": {}}
    for record in records:
        rid = record["record_id"]
        code, period = _context(record)
        model["contexts"].setdefault(f"{code} · {period}", []).append(rid)
        entry = stage_map.get(rid)
        place = classify(record, entry)
        if place in ("unclassified", "unattributable"):
            model[place].append(rid)
            continue
        cell = stages[place]
        cell["records"].append(rid)
        if "challenger" in (record.get("tags") or []) or entry["control"] is not None:
            pair = _pair(record, entry, by_id)
            cell["pairs"].append(pair)
            _bump(cell["effects"], pair["effect"] or AMBIGUOUS)
            _bump(cell["dispositions"], pair["disposition"])
    return model
