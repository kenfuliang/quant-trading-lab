#!/usr/bin/env python3
"""Bounded offline RSI seam proof: saved preflight or explicit synthetic demo.

No financial adapter, model fitting, network, service or broker operation exists
here. Existing policy-replay tasks are known development fixtures, not withheld
tasks. An exclusive output directory preserves failed/partial demonstrations.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.rsi_adoption import AdoptionRegistry
from research.rsi_contracts import canonical_hash, preflight_known_c001, validate_cycle, verify_artifacts
from research.rsi_coordinator import RSIError, RSIProgram, freeze_program, incremental_preflight_case, synthetic_case


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def cycle(program_id, cycle_id, input_path, incumbent):
    now = datetime.now(timezone.utc)
    stamp = lambda dt: dt.isoformat()
    receipt = ROOT / "docs/tasks/evidence/2026-10-27-grs-c001.json"
    return validate_cycle({
        "contract_version": "RSI-CYCLE-1", "program_id": program_id,
        "cycle_id": cycle_id, "created_utc": stamp(now),
        "parent": {"cycle_id": "GRS-C001", "receipt_sha256": digest(receipt)},
        "incumbent": incumbent,
        "change": {"kind": "improve_existing_stage", "stage": "research preflight",
                   "description": "Synthetic engineering check; no financial policy change",
                   "changed_stages": ["research preflight"]},
        "proposal": {"hypothesis": "A known saved lesson can reject incompatible records before launch",
                     "mechanism": "Strict frozen identities, causal declarations and artifact checks",
                     "falsifier": "Changed evidence is accepted or the closed financial cycle is reopened",
                     "prior_lessons": ["GRS-C001 failed its strict diagnostic control; original failure remains"],
                     "simpler_control_ids": ["unchanged-fixture"]},
        "interface": {"input_fields": [{"name": "fixture", "meaning": "Frozen synthetic declaration", "unit": "JSON record"}],
                      "output_fields": [{"name": "passed", "meaning": "Registered offline output contract matches", "unit": "boolean"}]},
        "timing": {"as_of_utc": stamp(now), "data_available_utc": stamp(now),
                   "decision_utc": stamp(now), "execution_utc": stamp(now + timedelta(seconds=1)),
                   "target": "offline evidence compatibility", "horizon": "one engineering check"},
        "evaluation": {"start_utc": "2020-01-01T00:00:00Z", "end_utc": "2025-12-31T00:00:00Z",
                       "exposure": "previously_viewed", "prior_access_count": 1,
                       "prior_access_note": "Known synthetic fixtures and previously inspected C001 outputs"},
        "criteria": {"objective": "Execute only frozen offline checks; no new financial launch",
                     "meaningful_effect": 1, "guardrails": ["zero financial launches", "preserve failed C001 gate"], "tolerance": 0},
        "controls": [{"id": "unchanged-fixture", "description": "Same synthetic input bytes", "sha256": digest(input_path)}],
        "budget": {"max_attempts": 2, "wall_seconds": 120, "workers": 1, "automatic_retries": 0},
        "artifacts": [{"path": input_path.relative_to(ROOT).as_posix(), "sha256": digest(input_path)}],
    })


def grade_replay(result):
    """Check replay claims against the frozen fictional task answers, not its score."""
    expected = {"a-select": {"selection"}, "b-recovery": {"recovery"}}
    if result["scenario"] == "shared-integrity":
        expected["z-integrity"] = {"cost", "recovery"}
    elif result["scenario"] == "inconclusive-integrity":
        expected["z-integrity"] = set()
    elif result["scenario"] != "equal-actions":
        raise ValueError("Unknown fixture reference answers")
    resolved, selected, errors = set(), [], 0
    for decision in result["decisions"]:
        identity = decision["selected"]
        wanted = expected.get(identity)
        if wanted is None or identity in selected:
            errors += 1
        else:
            wanted = wanted - resolved
            if set(decision["credited_questions"]) != wanted:
                errors += 1
            resolved.update(wanted)
        selected.append(identity)
    if set(result["resolved_questions"]) != resolved or result["resolved_count"] != len(resolved):
        errors += 1
    if result["financial_simulations"] != 0 or result["execution_verified"] is not False:
        errors += 1
    return {"critical_errors_observed": errors, "independently_checked_resolutions": len(resolved),
            "redundant_selected_observations": len(selected) - len(set(selected)),
            "grading_scope": "deterministic fictional reference answers; not independent financial replication"}


def process_comparison(output):
    """Reuse the existing win/loss/tie fixture set with identical limits per arm."""
    source = ROOT / "tests/test_research_policy_adversarial.py"
    replay = runpy.run_path(str(source), run_name="rsi_known_fixture_replay")["replay_case"]
    scenarios = ["shared-integrity", "inconclusive-integrity", "equal-actions"]
    arms = []
    for scenario in scenarios:
        pair = []
        for policy in ("priority", "breadth_first"):
            started = time.perf_counter()
            result = replay(scenario, policy)
            result["elapsed_seconds"] = time.perf_counter() - started
            result["reference_grade"] = grade_replay(result)
            pair.append(result)
            arms.append(result)
        if pair[0]["candidate_set_sha256"] != pair[1]["candidate_set_sha256"] or pair[0]["usage"] != pair[1]["usage"]:
            raise ValueError("Unmatched process comparison information or budgets")
    summary = {}
    for policy in ("priority", "breadth_first"):
        selected = [r for r in arms if r["policy"] == policy]
        summary[policy] = {
            "resolved_questions": sum(r["resolved_count"] for r in selected),
            "critical_errors_observed": sum(r["reference_grade"]["critical_errors_observed"] for r in selected),
            "independently_checked_resolutions": sum(r["reference_grade"]["independently_checked_resolutions"] for r in selected),
            "logical_attempts": sum(r["usage"]["attempts"] for r in selected),
            "fixture_resource_units": sum(r["usage"]["resource_units_committed"] for r in selected),
            "elapsed_seconds": sum(r["elapsed_seconds"] for r in selected),
            "redundant_selected_observations": sum(r["reference_grade"]["redundant_selected_observations"] for r in selected),
        }
    result = {"schema_version": "RSI-PROCESS-FIXTURE-1", "fixture_source": str(source.relative_to(ROOT)),
              "fixture_sha256": digest(source), "task_exposure": "known development fixtures; not withheld",
              "financial_launches": 0, "summary": summary, "arms": arms,
              "generalization_established": False,
              "lesson": "Priority wins one, loses one and ties one; aggregate resolved-question totals tie. No overall research-policy advantage established."}
    save(output, result)
    return result


def demo(output):
    output = output.resolve()
    output.relative_to(ROOT)  # Demo artifacts must stay inside this local project.
    output.mkdir(parents=True, exist_ok=False)
    preflight = preflight_known_c001(ROOT)
    save(output / "known-lesson-preflight.json", preflight)
    input_path = output / "fixture-input.json"
    save(input_path, {"synthetic": True, "purpose": "engineering seam; no market strategy"})
    incumbent = {"version": "engineering-fixture-v1", "sha256": digest(input_path)}
    candidate = {"version": "engineering-fixture-v2", "sha256": canonical_hash({"synthetic": "challenger-v2"})}
    program_id = "rsi-foundation-demo-v1"
    contracts = [cycle(program_id, cid, input_path, incumbent) for cid in ("fixture", "saved")]
    for contract in contracts:
        save(output / (contract["cycle_id"] + "-contract.json"), contract)
    cycles = [{"cycle_id": c["cycle_id"], "parent_identities": {str(input_path): digest(input_path)},
               "criteria": c["criteria"], "contract": c,
               "cases": ([synthetic_case("check", payload={"known_lesson_checked": True}),
                          synthetic_case("over-budget", payload={"unexecuted": True})]
                         if c["cycle_id"] == "fixture" else [incremental_preflight_case("check")])}
              for c in contracts]
    directory = output / "program"
    spec = freeze_program(directory, program_id=program_id, cycles=cycles,
                          bounds={"max_launches": 2, "max_financial_slots": 0, "wall_seconds": 120})
    save(output / "frozen-program.json", spec)
    with RSIProgram(directory, spec=spec) as program:
        receipts = [program.execute(cid, "check") for cid in ("fixture", "saved")]
        if any(r["status"] != "completed" for r in receipts):
            raise ValueError("Offline seam did not complete")
        usage = program.usage()
        try:
            program.execute("fixture", "over-budget")
        except RSIError as exc:
            exhausted = str(exc)
        else:
            raise ValueError("Aggregate bound was bypassed")
    with RSIProgram(directory, spec=spec) as program:
        reused = program.execute("fixture", "check")
        if not reused["cached"] or program.usage()["launch_reservations"] != 2:
            raise ValueError("Restart caused duplicate execution")
    save(output / "execution-receipts.json", {"receipts": receipts, "usage": usage,
         "exhaustion_reason": exhausted, "verified_restart_cache": reused["cached"]})

    registry_directory = output / "versions"
    with AdoptionRegistry(registry_directory, artifact_root=ROOT, incumbent=incumbent,
                          evaluator={"id": "synthetic-declaration-check-v1", "sha256": digest(ROOT / "research/rsi_adoption.py")}) as registry:
        plan_hash = registry.freeze_plan(contracts[0], candidate=candidate, proposer_id="fixture-proposer",
            code_sha256=digest(Path(__file__)), data_sha256=digest(input_path),
            score_sha256=canonical_hash(contracts[0]["criteria"]),
            gate={"metric": "verified_checks", "direction": "higher", "incumbent_value": 0,
                  "meaningful_effect": 1, "tolerance": 0, "guardrails": {"financial_launches": {"max": 0}}})
        result_path = output / "synthetic-evaluation.json"
        save(result_path, {"schema_version": "RSI-EVALUATION-1", "context": registry.context_for(plan_hash),
            "metrics": {"verified_checks": 1, "financial_launches": 0},
            "checks": {"integrity": True, "accounting": True, "controls": True, "chronology": True}, "synthetic": True})
        entry = {"path": result_path.relative_to(ROOT).as_posix(), "sha256": digest(result_path)}
        evaluation = registry.evaluate_artifact(plan_hash, entry)
        decision = registry.evaluate_and_record(plan_hash, evaluation, decision_id="synthetic-only-adopt",
            reason="Synthetic declaration gate only; not financial evaluation or authenticated evaluator provenance")
        rollback = registry.rollback(incumbent["version"], decision_id="synthetic-only-rollback",
                                     reason="Demonstrate explicit reversible engineering disposition")
    save(output / "version-decisions.json", {"decision": decision, "rollback": rollback, "financial_adoption": False})
    comparison = process_comparison(output / "process-comparison.json")
    summary = {"status": "completed-offline-engineering-demo", "financial_launches": 0,
               "process_launches": usage["launches_observed"], "verified_restart_cache": True,
               "known_lesson_financial_launches": preflight["financial_launches"],
               "frozen_gate_overridden": False, "financial_incumbent_changed": False,
               "research_policy_generalization_established": False,
               "process_summary": comparison["summary"]}
    save(output / "summary.json", summary)
    entries = [{"path": p.relative_to(output).as_posix(), "sha256": digest(p)}
               for p in sorted(output.rglob("*")) if p.is_file()]
    verify_artifacts(entries, output)
    save(output / "manifest.json", {"artifacts": entries})
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", choices=("preflight", "demo"), default="preflight")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mode == "demo":
        if args.output is None:
            parser.error("demo needs an exclusive --output directory")
        result = demo(args.output)
    else:
        if args.output is not None:
            parser.error("preflight writes no files; --output is for demo")
        result = preflight_known_c001(ROOT)
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
