"""Offline contract and saved-evidence regressions; no financial launches."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.control.rsi_contracts import (
    ContractError, canonical_hash, preflight_known_c001, validate_cycle,
    verify_artifacts,
)


def valid_cycle():
    """Portable valid RSI-CYCLE-1 declaration for other offline seam fixtures."""
    digest = "a" * 64
    return {
        "contract_version": "RSI-CYCLE-1", "program_id": "synthetic-seam-v1",
        "cycle_id": "fixture-cycle-1", "created_utc": "2026-10-27T00:00:00Z",
        "parent": {"cycle_id": "fixture-parent", "receipt_sha256": digest},
        "incumbent": {"version": "fixture-incumbent-v1", "sha256": digest},
        "change": {"kind": "improve_existing_stage", "stage": "position sizing",
                   "description": "Synthetic schema check only", "changed_stages": ["position sizing"]},
        "proposal": {"hypothesis": "Known diagnostic semantics can be checked before launch",
                     "mechanism": "Hash and typed field checks reject incompatible inputs",
                     "falsifier": "An incompatible artifact is accepted",
                     "prior_lessons": ["C001 stopped on a known semantic diagnostic difference"],
                     "simpler_control_ids": ["fixed-control"]},
        "interface": {"input_fields": [{"name": "eligibility", "meaning": "Causal EMA eligibility", "unit": "boolean"}],
                      "output_fields": [{"name": "target", "meaning": "Fraction of nominal budget", "unit": "fraction"}]},
        "timing": {"as_of_utc": "2026-10-27T00:00:00Z",
                   "data_available_utc": "2026-10-26T00:00:00Z",
                   "decision_utc": "2026-10-27T00:00:00Z",
                   "execution_utc": "2026-10-28T00:00:00Z",
                   "target": "whole-budget eligibility", "horizon": "one daily session"},
        "evaluation": {"start_utc": "2020-01-01T00:00:00Z", "end_utc": "2025-12-31T00:00:00Z",
                       "exposure": "previously_viewed", "prior_access_count": 1,
                       "prior_access_note": "Synthetic saved fixture; no unseen evidence"},
        "criteria": {"objective": "reject incompatible records", "meaningful_effect": 1,
                     "guardrails": ["No financial launch"], "tolerance": 0},
        "controls": [{"id": "fixed-control", "description": "Synthetic unchanged control", "sha256": digest}],
        "budget": {"max_attempts": 1, "wall_seconds": 30, "workers": 1, "automatic_retries": 0},
        "artifacts": [{"path": "fixture.json", "sha256": digest}],
    }


class CanonicalHashTests(unittest.TestCase):
    def test_stable_order_strict_types_and_content_identity(self):
        self.assertEqual(canonical_hash({"b": 2, "a": [1]}), canonical_hash({"a": [1], "b": 2}))
        self.assertNotEqual(canonical_hash(1), canonical_hash(1.0))
        self.assertNotEqual(canonical_hash(True), canonical_hash(1))
        for value in (float("nan"), float("inf"), {1: "bad"}, (1, 2), Path("x"), {"x": float("-inf")}):
            with self.subTest(value=value), self.assertRaises(ContractError):
                canonical_hash(value)


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "nested").mkdir()
        (self.root / "nested/file").write_bytes(b"frozen")
        self.entry = {"path": "nested/file", "sha256": hashlib.sha256(b"frozen").hexdigest()}

    def test_verify_returns_detached_verified_identity(self):
        result = verify_artifacts([self.entry], self.root)
        self.assertEqual(result, (self.entry,))
        self.assertIsNot(result[0], self.entry)
        self.assertEqual(verify_artifacts([], self.root), ())

    def test_missing_wrong_hash_and_tamper(self):
        for entry in ({"path": "missing", "sha256": "a" * 64},
                      self.entry | {"sha256": "a" * 64}):
            with self.subTest(entry=entry), self.assertRaises(ContractError):
                verify_artifacts([entry], self.root)
        (self.root / "nested/file").write_bytes(b"changed")
        with self.assertRaises(ContractError):
            verify_artifacts([self.entry], self.root)

    def test_reject_path_traversal_absolute_and_ambiguous_paths(self):
        for path in ("../outside", "/etc/passwd", "nested/../nested/file", "nested/./file", "nested//file",
                     "nested/file/", "nested\\file", "", "\0bad"):
            with self.subTest(path=path), self.assertRaises(ContractError):
                verify_artifacts([self.entry | {"path": path}], self.root)

    def test_reject_file_and_directory_symlinks_even_inside_root(self):
        (self.root / "link-file").symlink_to(self.root / "nested/file")
        (self.root / "link-dir").symlink_to(self.root / "nested", target_is_directory=True)
        (self.root / "escape").symlink_to(self.root.parent, target_is_directory=True)
        for path in ("link-file", "link-dir/file", "escape/anything"):
            with self.subTest(path=path), self.assertRaises(ContractError):
                verify_artifacts([self.entry | {"path": path}], self.root)

    def test_reject_directories_duplicates_unknown_fields_and_invalid_digest(self):
        bad = [self.entry | {"path": "nested"}, self.entry | {"sha256": "A" * 64},
               self.entry | {"extra": True}, {"path": "nested/file"}]
        for entry in bad:
            with self.subTest(entry=entry), self.assertRaises(ContractError):
                verify_artifacts([entry], self.root)
        with self.assertRaises(ContractError):
            verify_artifacts([self.entry, self.entry], self.root)


class CycleContractTests(unittest.TestCase):
    def test_valid_plan_is_detached_and_hash_changes_with_rules(self):
        plan = valid_cycle()
        result = validate_cycle(plan)
        self.assertEqual(result, plan)
        result["criteria"]["guardrails"].append("another")
        self.assertNotEqual(canonical_hash(result), canonical_hash(plan))
        self.assertEqual(len(plan["criteria"]["guardrails"]), 1)

    def test_required_and_unknown_fields(self):
        for field in valid_cycle():
            plan = valid_cycle()
            del plan[field]
            with self.subTest(missing=field), self.assertRaises(ContractError):
                validate_cycle(plan)
        for section in (None, "criteria", "parent", "incumbent", "change", "proposal", "interface", "timing", "evaluation", "budget"):
            plan = valid_cycle()
            (plan if section is None else plan[section])["extra"] = 1
            with self.subTest(section=section), self.assertRaises(ContractError):
                validate_cycle(plan)

    def test_no_bool_as_number_invalid_budget_and_nonfinite(self):
        cases = [("budget", key, True) for key in ("max_attempts", "wall_seconds", "workers", "automatic_retries")]
        cases += [("criteria", "meaningful_effect", False), ("criteria", "tolerance", True),
                  ("evaluation", "prior_access_count", True), ("budget", "max_attempts", 1.0),
                  ("budget", "wall_seconds", 0), ("budget", "workers", 2), ("budget", "automatic_retries", 1),
                  ("criteria", "tolerance", -1), ("criteria", "meaningful_effect", 0),
                  ("criteria", "meaningful_effect", float("inf"))]
        for section, field, value in cases:
            plan = valid_cycle()
            plan[section][field] = value
            with self.subTest(section=section, field=field, value=value), self.assertRaises(ContractError):
                validate_cycle(plan)

    def test_one_stage_exact_identity_controls_and_artifacts(self):
        mutations = [lambda p: p["parent"].update(cycle_id=p["cycle_id"]),
                     lambda p: p["change"].update(changed_stages=[]),
                     lambda p: p["change"].update(changed_stages=["position sizing", "proposal"]),
                     lambda p: p["change"].update(changed_stages=["different"]),
                     lambda p: p["incumbent"].update(sha256="bad"),
                     lambda p: p.update(controls=[]), lambda p: p.update(artifacts=[]),
                     lambda p: p["controls"].append(deepcopy(p["controls"][0])),
                     lambda p: p["artifacts"][0].update(path="../unsafe"),
                     lambda p: p["criteria"].update(guardrails=[]),
                     lambda p: p["proposal"].update(prior_lessons=[]),
                     lambda p: p["proposal"].update(simpler_control_ids=["missing"]),
                     lambda p: p["proposal"].update(simpler_control_ids=[]),
                     lambda p: p["interface"].update(input_fields=[]),
                     lambda p: p["interface"]["output_fields"][0].update(unit=""),
                     lambda p: p["interface"]["input_fields"].append(deepcopy(p["interface"]["input_fields"][0])),
                     lambda p: p.update(contract_version="next-unreviewed")]
        for mutate in mutations:
            plan = valid_cycle()
            mutate(plan)
            with self.subTest(plan=plan), self.assertRaises(ContractError):
                validate_cycle(plan)

    def test_timestamp_types_offsets_and_chronology(self):
        for value in ("2026-10-27", "2026-10-27T00:00:00", "2026-10-27T00:00:00+01:00", "bad", True):
            plan = valid_cycle()
            plan["created_utc"] = value
            with self.subTest(value=value), self.assertRaises(ContractError):
                validate_cycle(plan)
        for section, field, value in (("timing", "data_available_utc", "2026-10-28T00:00:00Z"),
                                      ("timing", "decision_utc", "2026-10-28T00:00:00Z"),
                                      ("timing", "as_of_utc", "2026-10-28T00:00:00Z"),
                                      ("evaluation", "end_utc", "2019-01-01T00:00:00Z")):
            plan = valid_cycle()
            plan[section][field] = value
            with self.subTest(field=field), self.assertRaises(ContractError):
                validate_cycle(plan)

    def test_protected_forward_cannot_rename_viewed_or_past_history(self):
        plan = valid_cycle()
        plan["evaluation"].update(exposure="protected_forward", prior_access_count=0,
                                  start_utc="2026-10-28T00:00:00Z", end_utc="2026-12-31T00:00:00Z")
        validate_cycle(plan)
        for changed in ({"prior_access_count": 1}, {"start_utc": plan["created_utc"]},
                        {"start_utc": "2020-01-01T00:00:00Z"}):
            bad = deepcopy(plan)
            bad["evaluation"].update(changed)
            with self.subTest(changed=changed), self.assertRaises(ContractError):
                validate_cycle(bad)
        plan = valid_cycle()
        plan["evaluation"]["prior_access_count"] = 0
        with self.assertRaises(ContractError):
            validate_cycle(plan)
        plan["evaluation"].update(exposure="protected_forward", prior_access_count=0,
                                  start_utc="2026-10-28T00:00:00Z", end_utc="2026-12-31T00:00:00Z")
        plan["timing"].update(as_of_utc="2026-10-28T00:00:00Z", decision_utc="2026-10-28T00:00:00Z",
                               execution_utc="2026-10-29T00:00:00Z")
        with self.assertRaises(ContractError):
            validate_cycle(plan)


class C001PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def saved_fixture(self, *, drift=None):
        """Synthetic hash-linked historical tree; caller patches only test anchor."""
        def write(path, value):
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(value if isinstance(value, bytes) else value.encode())
            return {"path": path, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}

        def save_json(path, value):
            return write(path, json.dumps(value, sort_keys=True))

        helper_path = Path(__file__).resolve().parents[1] / "research/control/legacy_control_contract.py"
        helper = write("research/legacy_control_contract.py", helper_path.read_bytes())
        source = write("source.json", "[]")
        code = write("fixture.py", "# saved fixture; never executed\n")
        design = write("design.json", "{}")
        standard = write("docs/research-standard.md", "fixture standard")
        old_ledger = "date,cash,shares,equity_usd,effective_target_leverage\n2020-01-02,100.0,0,100.0,0.0\n2020-01-03,0.0,1,101.0,1.0\n"
        new_ledger = old_ledger.replace("100.0,0.0\n", "100.0,1.0\n")
        trades = "date,delta,fill_price\n2020-01-03,1,100.0\n"
        old_signal = "date,want_long,allocation_factor,base_target,intended_target\n2020-01-02,False,0.0,0.0,0.0\n2020-01-03,True,1.0,1.0,1.0\n"
        new_signal = old_signal.replace("False,0.0,0.0,0.0", "False,1.0,0.0,0.0")
        if drift == "cash":
            new_ledger = new_ledger.replace("100.0,0,", "100.01,0,")
        if drift == "trade":
            trades_new = trades.replace(",1,100.0", ",2,100.0")
        else:
            trades_new = trades
        if drift == "field":
            new_ledger = new_ledger.replace("shares", "other")
        if drift == "semantic":
            new_ledger = new_ledger.replace("100.0,1.0", "100.0,0.5")
        if drift == "eligibility":
            new_signal = new_signal.replace("False,1.0", "yes,1.0")
        if drift == "date":
            new_signal = new_signal.replace("2020-01-03", "2020-01-02")
        old_files = [write("parent/5_ema/ledger.csv", old_ledger), write("parent/5_ema/trades.csv", trades),
                     write("parent/5_ema/signal.csv", old_signal)]
        parent = save_json("parent/manifest.json", {"artifact_hashes": {
            item["path"].removeprefix("parent/"): item["sha256"] for item in old_files}})
        plan = {"cycle": "GRS-C001", "code_hashes": {code["path"]: code["sha256"]}, "source": source,
                "design_path": design["path"], "design_sha256": design["sha256"],
                "golden_standard_sha256": standard["sha256"],
                "parent_manifests": {"parent": parent["sha256"]}, "control_paths": {"5bp_ema": "parent/5_ema"}}
        plan_entry = save_json("plan.json", plan)
        current_plan = save_json("saved/c001/plan.json", plan)
        state = save_json("saved/c001/state.json", {"cycle": "GRS-C001", "status": "closed-inconclusive-no-retry",
                          "actual_attempts": 1, "plan_sha256": plan_entry["sha256"], "attempts": [{"status": "failed"}]})
        new_files = [write("saved/c001/5bp_ema/ledger.csv", new_ledger), write("saved/c001/5bp_ema/trades.csv", trades_new),
                     write("saved/c001/5bp_ema/signal.csv", new_signal), current_plan, state]
        current = save_json("saved/c001/manifest.json", {"cycle": "GRS-C001", "status": "closed-inconclusive-no-retry",
                            "artifact_hashes": {item["path"].removeprefix("saved/c001/"): item["sha256"] for item in new_files}})
        return save_json("receipt.json", {"cycle": "GRS-C001", "status": "closed-inconclusive-control-schema-mismatch",
                         "actual_financial_attempts": 1, "incumbent_changed": False, "completed_comparisons": 0,
                         "plan": plan_entry["path"], "plan_sha256": plan_entry["sha256"], "artifacts": "saved/c001",
                         "manifest_sha256": current["sha256"], "engineering_followup": {"source": helper["path"],
                         "sha256": helper["sha256"]}})

    def test_known_lesson_verified_identity_zero_launches_and_no_writes(self):
        receipt = self.saved_fixture()
        before = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch("research.control.rsi_contracts._C001_RECEIPT", receipt):
            result = preflight_known_c001(self.root)
            self.assertEqual(result, preflight_known_c001(self.root))
        self.assertTrue(result["passed"])
        self.assertEqual(result["financial_launches"], 0)
        self.assertEqual(result["original_financial_attempts"], 1)
        self.assertFalse(result["frozen_gate_overridden"])
        self.assertEqual(result["check"]["mismatch_sessions"], 1)
        self.assertTrue(result["check_id"].startswith("c001-ema-diagnostic-"))
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_authenticated_cash_trade_schema_semantic_and_timing_drift_fail(self):
        for drift in ("cash", "trade", "field", "semantic", "eligibility", "date"):
            receipt = self.saved_fixture(drift=drift)
            with self.subTest(drift=drift), patch("research.control.rsi_contracts._C001_RECEIPT", receipt):
                with self.assertRaises(ContractError):
                    preflight_known_c001(self.root)

    def test_tampered_missing_and_changed_source_fail_before_helper(self):
        for changed in ("parent/5_ema/ledger.csv", "saved/c001/5bp_ema/ledger.csv", "source.json",
                        "fixture.py", "research/legacy_control_contract.py", "saved/c001/state.json"):
            receipt = self.saved_fixture()
            (self.root / changed).write_bytes(b"tampered")
            with self.subTest(changed=changed), patch("research.control.rsi_contracts._C001_RECEIPT", receipt):
                with patch("research.control.legacy_control_contract.compare_ema_diagnostic") as compare:
                    with self.assertRaises(ContractError):
                        preflight_known_c001(self.root)
                    compare.assert_not_called()
        receipt = self.saved_fixture()
        (self.root / "source.json").unlink()
        with patch("research.control.rsi_contracts._C001_RECEIPT", receipt), self.assertRaises(ContractError):
            preflight_known_c001(self.root)

    def test_default_anchor_rejects_unrecorded_receipt(self):
        self.saved_fixture()
        with self.assertRaises(ContractError):
            preflight_known_c001(self.root)


if __name__ == "__main__":
    unittest.main()
