"""Adversarial, synthetic-only research-version registry checks."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest

from research.control.rsi_adoption import (
    AdoptionError, AdoptionRegistry, EVALUATION_VERSION, IndependentEvaluation,
)
from research.control.rsi_contracts import canonical_hash


class AdoptionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "input.json").write_text('{"synthetic": true}')
        self.incumbent = {"version": "v1", "sha256": "a" * 64}
        self.evaluator = {"id": "independent-checker", "sha256": "e" * 64}
        self.registry = self.open_registry()
        self.results = 0

    def open_registry(self, **changes):
        options = dict(artifact_root=self.root, incumbent=self.incumbent,
                       evaluator=self.evaluator, scope="synthetic_engineering")
        options.update(changes)
        registry = AdoptionRegistry(self.root / "registry", **options)
        self.addCleanup(registry.close)
        return registry

    def descriptor(self, path):
        return {"path": path, "sha256": hashlib.sha256((self.root / path).read_bytes()).hexdigest()}

    def cycle(self, cycle_id="cycle-1"):
        return {
            "contract_version": "RSI-CYCLE-1", "program_id": "synthetic-test",
            "cycle_id": cycle_id, "created_utc": "2026-10-27T00:00:00Z",
            "parent": {"cycle_id": "parent", "receipt_sha256": "b" * 64},
            "incumbent": deepcopy(self.incumbent),
            "change": {"kind": "improve_existing_stage", "stage": "verification",
                       "description": "Synthetic integrity fixture", "changed_stages": ["verification"]},
            "proposal": {"hypothesis": "The known invalid case is rejected",
                         "mechanism": "Stricter artifact checks",
                         "falsifier": "An invalid case passes", "prior_lessons": ["Saved failure"],
                         "simpler_control_ids": ["control"]},
            "interface": {"input_fields": [{"name": "case", "meaning": "Synthetic case", "unit": "case"}],
                          "output_fields": [{"name": "resolved", "meaning": "Verified resolution", "unit": "count"}]},
            "timing": {"as_of_utc": "2026-10-27T00:00:00Z",
                       "data_available_utc": "2026-10-26T00:00:00Z",
                       "decision_utc": "2026-10-27T00:00:00Z",
                       "execution_utc": "2026-10-28T00:00:00Z", "target": "synthetic result",
                       "horizon": "one fixture"},
            "evaluation": {"start_utc": "2020-01-01T00:00:00Z", "end_utc": "2025-12-31T00:00:00Z",
                           "exposure": "previously_viewed", "prior_access_count": 1,
                           "prior_access_note": "Previously viewed synthetic case; not financial data"},
            "criteria": {"objective": "Resolve more synthetic cases", "meaningful_effect": 1,
                         "guardrails": ["Zero critical errors"], "tolerance": 0},
            "controls": [{"id": "control", "description": "Unchanged synthetic checker", "sha256": "c" * 64}],
            "budget": {"max_attempts": 1, "wall_seconds": 10, "workers": 1, "automatic_retries": 0},
            "artifacts": [self.descriptor("input.json")],
        }

    def freeze(self, *, cycle=None, candidate=None, gate=None, **changes):
        options = dict(candidate=candidate or {"version": "v2", "sha256": "d" * 64},
                       proposer_id="proposer", code_sha256="f" * 64,
                       data_sha256="1" * 64, score_sha256="2" * 64,
                       gate=gate or {"metric": "resolved", "direction": "higher",
                                     "incumbent_value": 2, "meaningful_effect": 1,
                                     "tolerance": 0, "guardrails": {"critical_errors": {"max": 0}}})
        options.update(changes)
        return self.registry.freeze_plan(cycle or self.cycle(), **options)

    def artifact(self, plan_hash, *, metrics=None, checks=None, context=None,
                 synthetic=True, extra=None):
        result = {"schema_version": EVALUATION_VERSION,
                  "context": context or self.registry.context_for(plan_hash),
                  "metrics": metrics if metrics is not None else {"resolved": 3, "critical_errors": 0},
                  "checks": checks or {"integrity": True, "accounting": True,
                                       "controls": True, "chronology": True},
                  "synthetic": synthetic}
        result.update(extra or {})
        self.results += 1
        path = f"result-{self.results}.json"
        (self.root / path).write_text(json.dumps(result))
        return self.descriptor(path)

    def evaluation(self, plan_hash, **options):
        return self.registry.evaluate_artifact(plan_hash, self.artifact(plan_hash, **options))

    def record(self, plan_hash, result=None, *, decision_id="decision-1"):
        result = result or self.evaluation(plan_hash)
        return self.registry.evaluate_and_record(plan_hash, result,
                                                decision_id=decision_id, reason="Synthetic regression evidence")

    def test_synthetic_adoption_restart_and_rollback_preserve_history(self):
        plan_hash = self.freeze()
        receipt = self.record(plan_hash)
        decision = receipt["event"]["payload"]
        self.assertEqual(decision["status"], "adopted")
        self.assertEqual(decision["prior"], self.incumbent)
        self.assertEqual(decision["new"]["version"], "v2")
        self.registry.close()
        self.registry = self.open_registry()
        self.assertEqual(self.registry.state["current"]["version"], "v2")
        rollback = self.registry.rollback("v1", decision_id="rollback-1", reason="Exercise explicit recovery")
        self.assertEqual(rollback["event"]["payload"]["prior"]["version"], "v2")
        self.assertEqual(self.registry.state["current"], self.incumbent)
        self.assertEqual(len(self.registry.receipts), 4)
        self.assertEqual(self.registry.receipts[2], receipt)
        self.registry.close()
        self.registry = self.open_registry()
        self.assertEqual(self.registry.state["current"]["version"], "v1")
        self.assertEqual(len(self.registry.state["dispositions"]), 1)

    def test_financial_pass_stays_provisional_and_production_is_unsupported(self):
        self.registry.close()
        other = self.root / "registry"
        # New directory, since a protected registry cannot change scope.
        other.rename(self.root / "synthetic-registry")
        self.registry = self.open_registry(scope="financial_research")
        plan_hash = self.freeze()
        result = self.evaluation(plan_hash, synthetic=False)
        receipt = self.record(plan_hash, result)
        self.assertEqual(receipt["event"]["payload"]["status"], "provisional")
        self.assertEqual(self.registry.state["current"], self.incumbent)
        with self.assertRaises(AdoptionError):
            self.registry.rollback("v2", decision_id="no", reason="Not adopted")
        with self.assertRaises(AdoptionError):
            AdoptionRegistry(self.root / "production", artifact_root=self.root,
                             incumbent=self.incumbent, evaluator=self.evaluator, scope="production")

    def test_valid_failure_and_failed_integrity_keep_incumbent(self):
        plan_hash = self.freeze()
        result = self.evaluation(plan_hash, metrics={"resolved": 2.99, "critical_errors": 0})
        self.assertFalse(result.passed)
        self.assertEqual(self.record(plan_hash, result)["event"]["payload"]["status"], "rejected")
        self.assertEqual(self.registry.state["current"], self.incumbent)
        second = self.freeze(cycle=self.cycle("cycle-2"), candidate={"version": "v3", "sha256": "3" * 64})
        result = self.evaluation(second, checks={"integrity": False, "accounting": True,
                                                "controls": True, "chronology": True})
        self.assertFalse(result.passed)
        self.assertEqual(self.record(second, result, decision_id="decision-2")["event"]["payload"]["status"], "rejected")

    def test_forged_pass_and_mutated_typed_evaluation_are_denied(self):
        plan_hash = self.freeze()
        with self.assertRaises(AdoptionError):
            self.record(plan_hash, {"passed": True})
        failed = self.evaluation(plan_hash, metrics={"resolved": 2, "critical_errors": 0})
        for forged in (replace(failed, passed=True), replace(failed, metrics={"resolved": 999, "critical_errors": 0})):
            with self.subTest(forged=forged), self.assertRaises(AdoptionError):
                self.record(plan_hash, forged)
        valid = self.evaluation(plan_hash)
        for forged in (replace(valid, passed=1), replace(valid, synthetic=1),
                       replace(valid, metrics={"resolved": 3, "critical_errors": False})):
            with self.subTest(forged=forged), self.assertRaises(AdoptionError):
                self.record(plan_hash, forged)
        self.assertEqual(self.registry.state["current"], self.incumbent)
        self.assertFalse(self.registry.state["dispositions"])

    def test_exact_protected_context_is_required(self):
        plan_hash = self.freeze()
        original = self.registry.context_for(plan_hash)
        for key in original:
            changed = deepcopy(original)
            if key in ("incumbent", "candidate"):
                changed[key]["sha256"] = "0" * 64
            elif key == "evaluation":
                changed[key]["exposure"] = "protected_forward"
                changed[key]["prior_access_count"] = 0
            elif key == "evaluator":
                changed[key]["id"] = "proposer"
            else:
                changed[key] = "changed"
            with self.subTest(key=key), self.assertRaises(AdoptionError):
                self.evaluation(plan_hash, context=changed)
        for count in (True, 1.0):
            changed = deepcopy(original)
            changed["evaluation"]["prior_access_count"] = count
            with self.subTest(count=count), self.assertRaises(AdoptionError):
                self.evaluation(plan_hash, context=changed)

    def test_criteria_frozen_before_results_and_detached_from_caller(self):
        cycle = self.cycle()
        plan_hash = self.freeze(cycle=cycle)
        cycle["criteria"]["meaningful_effect"] = 0
        result = self.evaluation(plan_hash, metrics={"resolved": 2, "critical_errors": 0})
        self.assertFalse(result.passed)
        stored = self.registry.state["plans"][plan_hash]
        stored["gate"]["meaningful_effect"] = 0
        with self.assertRaises(AdoptionError):
            self.registry.context_for(canonical_hash(stored))
        self.assertEqual(self.registry.state["plans"][plan_hash]["gate"]["meaningful_effect"], 1)

    def test_gate_cannot_weaken_cycle_effect_or_use_unknown_configuration(self):
        original = {"metric": "resolved", "direction": "higher", "incumbent_value": 2,
                    "meaningful_effect": 1, "tolerance": 0, "guardrails": {"critical_errors": {"max": 0}}}
        for change in ({"meaningful_effect": 0.5}, {"tolerance": 1}, {"direction": "unknown"},
                       {"guardrails": {}}, {"guardrails": {"errors": {"max": True}}},
                       {"guardrails": {"errors": {"min": 2, "max": 1}}}, {"extra": True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.freeze(gate=original | change)
        with self.assertRaises(AdoptionError):
            self.freeze(proposer_id=self.evaluator["id"])

    def test_all_metrics_must_be_finite_typed_and_exact(self):
        plan_hash = self.freeze()
        bad_metrics = [{"resolved": value, "critical_errors": 0}
                       for value in (True, "3", float("nan"), float("inf"), None)]
        bad_metrics += [{"resolved": 3}, {"resolved": 3, "critical_errors": 0, "unknown": 0}]
        for metrics in bad_metrics:
            with self.subTest(metrics=metrics), self.assertRaises(ValueError):
                self.evaluation(plan_hash, metrics=metrics)
        with self.assertRaises(AdoptionError):
            self.evaluation(plan_hash, checks={"integrity": "pass", "accounting": True,
                                              "controls": True, "chronology": True})
        with self.assertRaises(AdoptionError):
            self.evaluation(plan_hash, extra={"passed": True})

    def test_lower_objective_and_guardrail_tolerance_are_applied(self):
        cycle = self.cycle()
        cycle["criteria"]["tolerance"] = 0.01
        gate = {"metric": "errors", "direction": "lower", "incumbent_value": 5,
                "meaningful_effect": 1, "tolerance": 0.01,
                "guardrails": {"resolved": {"min": 3, "max": 4}}}
        plan_hash = self.freeze(cycle=cycle, gate=gate)
        self.assertTrue(self.evaluation(plan_hash, metrics={"errors": 4, "resolved": 2.995}).passed)
        self.assertFalse(self.evaluation(plan_hash, metrics={"errors": 4.001, "resolved": 3}).passed)
        self.assertFalse(self.evaluation(plan_hash, metrics={"errors": 4, "resolved": 4.02}).passed)

    def test_output_tampering_and_missing_artifacts_fail_before_adoption(self):
        plan_hash = self.freeze()
        result = self.evaluation(plan_hash)
        (self.root / result.artifact["path"]).write_text("tampered")
        with self.assertRaises(ValueError):
            self.record(plan_hash, result)
        (self.root / result.artifact["path"]).unlink()
        with self.assertRaises(ValueError):
            self.record(plan_hash, result)
        self.assertEqual(self.registry.state["current"], self.incumbent)

    def test_input_tampering_is_rejected_on_replay(self):
        self.freeze()
        (self.root / "input.json").write_text("changed")
        with self.assertRaises(ValueError):
            _ = self.registry.state
        self.registry.close()
        with self.assertRaises(ValueError):
            self.open_registry()

    def test_adopted_output_tampering_is_rejected_on_restart(self):
        plan_hash = self.freeze()
        result = self.evaluation(plan_hash)
        self.record(plan_hash, result)
        self.registry.close()
        (self.root / result.artifact["path"]).write_text("changed")
        with self.assertRaises(ValueError):
            self.open_registry()

    def test_output_containment_and_symlinks_are_rejected(self):
        plan_hash = self.freeze()
        artifact = self.artifact(plan_hash)
        for path in ("../outside", str(self.root / artifact["path"]), "./" + artifact["path"]):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.registry.evaluate_artifact(plan_hash, artifact | {"path": path})
        (self.root / "link.json").symlink_to(self.root / artifact["path"])
        with self.assertRaises(ValueError):
            self.registry.evaluate_artifact(plan_hash, artifact | {"path": "link.json"})

    def test_duplicate_cycles_versions_and_decisions_cannot_replay(self):
        plan_hash = self.freeze()
        for cycle, candidate in ((self.cycle(), {"version": "v3", "sha256": "3" * 64}),
                                 (self.cycle("cycle-2"), {"version": "v2", "sha256": "3" * 64})):
            with self.assertRaises(AdoptionError):
                self.freeze(cycle=cycle, candidate=candidate)
        result = self.evaluation(plan_hash)
        self.record(plan_hash, result)
        for decision in ("decision-1", "decision-other"):
            with self.assertRaises(AdoptionError):
                self.record(plan_hash, result, decision_id=decision)
        with self.assertRaises(AdoptionError):
            self.registry.rollback("v1", decision_id="decision-1", reason="Duplicate ID")

    def test_stale_incumbent_cannot_be_replaced_by_parallel_frozen_plan(self):
        first = self.freeze()
        second = self.freeze(cycle=self.cycle("cycle-2"), candidate={"version": "v3", "sha256": "3" * 64})
        result = self.evaluation(second)
        self.record(first)
        with self.assertRaises(AdoptionError):
            self.record(second, result, decision_id="decision-2")
        self.assertEqual(self.registry.state["current"]["version"], "v2")

    def test_unknown_plan_synthetic_status_and_rollback_target_fail_closed(self):
        with self.assertRaises(AdoptionError):
            self.registry.context_for("0" * 64)
        plan_hash = self.freeze()
        with self.assertRaises(AdoptionError):
            self.evaluation(plan_hash, synthetic=False)
        for version in ("v2", "unknown", "v1"):
            with self.subTest(version=version), self.assertRaises(AdoptionError):
                self.registry.rollback(version, decision_id="rollback", reason="Not a valid prior version")

    def test_registry_context_cannot_change_and_only_one_writer(self):
        with self.assertRaises(AdoptionError):
            self.open_registry()
        self.registry.close()
        for change in ({"evaluator": self.evaluator | {"sha256": "0" * 64}},
                       {"scope": "financial_research"},
                       {"incumbent": self.incumbent | {"version": "other"}}):
            with self.subTest(change=change), self.assertRaises(AdoptionError):
                self.open_registry(**change)

    def test_journal_mutation_replay_truncation_and_partial_append_are_rejected(self):
        self.freeze()
        self.registry.close()
        path = self.root / "registry/adoption.jsonl"
        original = path.read_bytes()
        altered = original.replace(b"Synthetic integrity fixture", b"Changed integrity fixture")
        for bad in (altered, original + original.splitlines(keepends=True)[-1],
                    original.splitlines(keepends=True)[0], original + b"{"):
            path.write_bytes(bad)
            with self.subTest(length=len(bad)), self.assertRaises(ValueError):
                self.open_registry()
        path.write_bytes(original)
        self.registry = self.open_registry()
        self.assertEqual(len(self.registry.receipts), 2)

    def test_incomplete_head_update_requires_reconciliation(self):
        self.registry.close()
        (self.root / "registry/head.json").unlink()
        with self.assertRaises(AdoptionError):
            self.open_registry()

    def test_lost_authority_after_adoption_cannot_reinitialize_or_rollback(self):
        plan = self.freeze()
        result = self.evaluation(plan)
        self.registry.evaluate_and_record(plan, result, decision_id="adopt", reason="Synthetic fixture")
        self.assertEqual(self.registry.state["current"]["version"], "v2")
        self.registry.close()
        marker = self.root / "registry/initialized.json"
        before = marker.read_bytes()
        for name in ("adoption.jsonl", "head.json"):
            (self.root / "registry" / name).unlink()
        with self.assertRaises(AdoptionError):
            self.open_registry()
        self.assertEqual(marker.read_bytes(), before)
        self.assertFalse((self.root / "registry/adoption.jsonl").exists())
        self.assertFalse((self.root / "registry/head.json").exists())

    def test_open_writer_detects_authority_loss_before_any_new_decision(self):
        self.freeze()
        for name in ("adoption.jsonl", "head.json"):
            (self.root / "registry" / name).unlink()
        with self.assertRaises(AdoptionError):
            _ = self.registry.state
        with self.assertRaises(AdoptionError):
            self.registry.rollback("v1", decision_id="reset", reason="Must not reconstruct")
        self.assertFalse((self.root / "registry/adoption.jsonl").exists())

    def test_active_writer_rejects_even_hash_valid_old_authority(self):
        paths = [self.root / "registry" / name for name in ("adoption.jsonl", "head.json")]
        old = {path: path.read_bytes() for path in paths}
        self.freeze()
        for path, data in old.items():
            path.write_bytes(data)
        with self.assertRaisesRegex(AdoptionError, "changed while writer"):
            _ = self.registry.state

    def test_unmarked_existing_history_requires_reconciliation_without_migration(self):
        self.registry.close()
        marker = self.root / "registry/initialized.json"
        marker.unlink()
        old = {p: p.read_bytes() for p in (self.root / "registry").iterdir() if p.is_file()}
        with self.assertRaisesRegex(AdoptionError, "marker missing"):
            self.open_registry()
        self.assertFalse(marker.exists())
        self.assertEqual(old, {p: p.read_bytes() for p in old})

    def test_marker_only_initialization_is_not_silently_repaired(self):
        self.registry.close()
        for name in ("adoption.jsonl", "head.json"):
            (self.root / "registry" / name).unlink()
        with self.assertRaises(AdoptionError):
            self.open_registry()
        self.assertFalse((self.root / "registry/adoption.jsonl").exists())
        self.assertFalse((self.root / "registry/head.json").exists())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX authority-file behavior")
    def test_fifo_journal_head_marker_and_lock_reject_without_blocking(self):
        self.registry.close()
        directory = self.root / "registry"
        originals = {p: p.read_bytes() for p in directory.iterdir() if p.is_file()}
        code = """import sys
from research.control.rsi_adoption import AdoptionRegistry, AdoptionError
try:
    AdoptionRegistry(sys.argv[1], artifact_root=sys.argv[2],
                     incumbent={"version":"v1","sha256":"a"*64},
                     evaluator={"id":"independent-checker","sha256":"e"*64})
except AdoptionError:
    print("rejected"); sys.exit(17)
sys.exit(3)
"""
        for name in ("adoption.jsonl", "head.json", "initialized.json", ".writer.lock"):
            path = directory / name
            path.unlink()
            os.mkfifo(path)
            try:
                result = subprocess.run([sys.executable, "-c", code, str(directory), str(self.root)],
                                        cwd=Path(__file__).resolve().parents[1], capture_output=True,
                                        text=True, timeout=3)
                self.assertEqual(result.returncode, 17, result.stderr)
                self.assertEqual(result.stdout.strip(), "rejected")
                self.assertTrue(path.is_fifo())
                self.assertTrue(all(p.read_bytes() == data for p, data in originals.items() if p != path))
            finally:
                path.unlink()
                path.write_bytes(originals[path])

    def test_missing_lock_with_live_writer_cannot_admit_a_second_writer_or_retry(self):
        directory = self.root / "registry"
        authority = {p: p.read_bytes() for p in directory.iterdir() if p.name != ".writer.lock"}
        lock = directory / ".writer.lock"
        lock.unlink()
        for _ in range(2):
            with self.assertRaisesRegex(AdoptionError, "lock missing"):
                self.open_registry()
            self.assertFalse(lock.exists())
            with self.assertRaises(AdoptionError):
                _ = self.registry.state
        with self.assertRaises(AdoptionError):
            self.freeze()
        self.assertEqual(authority, {p: p.read_bytes() for p in authority})

    def test_replaced_lock_with_live_writer_fails_persistent_and_active_identity(self):
        directory = self.root / "registry"
        authority = {p: p.read_bytes() for p in directory.iterdir() if p.name != ".writer.lock"}
        lock = directory / ".writer.lock"
        lock.unlink()
        lock.write_bytes(b"replacement inode")
        for _ in range(2):
            with self.assertRaises(AdoptionError):
                self.open_registry()
        with self.assertRaisesRegex(AdoptionError, "lock authority changed"):
            _ = self.registry.state
        with self.assertRaises(AdoptionError):
            self.freeze()
        self.assertEqual(lock.read_bytes(), b"replacement inode")
        self.assertEqual(authority, {p: p.read_bytes() for p in authority})

    def test_symlink_lock_and_authority_do_not_modify_external_target(self):
        self.registry.close()
        external = self.root / "external"
        external.write_bytes(b"untouched")
        for name in ("adoption.jsonl", "head.json", "initialized.json", ".writer.lock"):
            path = self.root / "registry" / name
            saved = path.read_bytes()
            path.unlink()
            path.symlink_to(external)
            try:
                with self.assertRaises(AdoptionError):
                    self.open_registry()
                self.assertEqual(external.read_bytes(), b"untouched")
                self.assertTrue(path.is_symlink())
            finally:
                path.unlink()
                path.write_bytes(saved)

    def test_duplicate_json_keys_and_nonboolean_claims_are_rejected(self):
        plan_hash = self.freeze()
        artifact = self.artifact(plan_hash)
        path = self.root / artifact["path"]
        path.write_text(path.read_text().replace('"synthetic": true', '"synthetic": true, "synthetic": true'))
        with self.assertRaises(ValueError):
            self.registry.evaluate_artifact(plan_hash, self.descriptor(artifact["path"]))
        valid = self.evaluation(plan_hash)
        self.assertIs(type(valid), IndependentEvaluation)


if __name__ == "__main__":
    unittest.main()
