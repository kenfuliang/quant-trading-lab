"""Fresh synthetic journal fixtures; no broker, external model or market runs."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.control.research_controller import ResearchController, ControllerError, WriterBusy


CONTEXT = {"score_version": "pilot-test-v1", "plan_hash": "frozen-fixture", "data_hash": "fixture"}
BUDGET = {"max_attempts": 4, "max_resource_units": 20, "resource_unit": "fixture_seconds", "max_active_branches": 4}


def make_action(controller, name="inspect", branch="b", question="q", *, spec=None, cost=3, cls=2):
    return {"id": name, "branch_id": branch, "question_id": question,
            "context_id": controller.context_id, "observation_key": name,
            "observation_spec": spec or {"artifact": "digest-A", "check": "expense-coverage"},
            "class": cls, "decision_value": 2, "shared_questions": [],
            "cost_upper_bound": cost, "evidence": ["input:fixture-A"],
            "witness": [{"observation": "adequate", "decision": "retain"},
                        {"observation": "omitted", "decision": "reject"}]}


def outcome(*, evidence="receipt:A", question="q", units=1, status="completed", kind="synthetic_fixture"):
    return {"status": status, "summary": "Fixture expense coverage is omitted; reject its claim",
            "evidence": [evidence], "actual_resource_units": units,
            "inspection_trace": ["Read declared cost fields", "Compared with fixture expectation"],
            "observation_kind": kind,
            "resolutions": [{"question_id": question, "decision": "reject", "finding": "Expense omitted", "evidence": [evidence]}]}


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "journal"
        self.controllers = []

    def tearDown(self):
        for controller in self.controllers:
            controller.close()
        self.temp.cleanup()

    def new(self, *, budget=None, context=None, child_limit=2):
        controller = ResearchController(self.path, context=context or CONTEXT,
                                        budget=budget or BUDGET, child_limit=child_limit)
        self.controllers.append(controller)
        return controller

    def seeded(self, **kwargs):
        controller = self.new(**kwargs)
        controller.register_question("question-q", "q", {"estimand": "Are execution expenses included?", "scope": "fixture-A"})
        controller.register_branch("branch-b", branch_id="b", question_id="q", mechanism="measurement")
        return controller

    def extra_question(self, c, q="q2", b="b2", *, parent=None):
        c.register_question("question-" + q, q, {"estimand": q, "scope": "different-decision"})
        c.register_branch("branch-" + b, branch_id=b, question_id=q, mechanism="distinct-" + b, parent_branch_id=parent)

    def test_two_step_preview_is_read_only_reservation_is_not_execution(self):
        c = self.seeded()
        original = c.log_path.read_bytes()
        selected = c.preview([make_action(c)])["selected"]
        self.assertEqual(selected["id"], "inspect")
        self.assertEqual(c.log_path.read_bytes(), original)
        reservation = c.select("reserve", selected)
        self.assertEqual(c.usage()["attempts"], 1)
        self.assertFalse(reservation["execution_verified"])
        self.assertEqual(c.state["attempts"][reservation["attempt_id"]]["status"], "reserved")
        result = c.record("record", reservation["attempt_id"], outcome())
        self.assertEqual(result["credited_questions"], ["q"])
        self.assertEqual(result["claimed_outcome"], "completed")
        self.assertFalse(result["execution_verified"])

    def test_resume_operation_idempotence_and_changed_payload_rejection(self):
        c = self.seeded()
        action = make_action(c)
        selected = c.select("reserve", action)
        c.close()
        c = self.new()
        before = c.log_path.read_bytes()
        self.assertEqual(c.select("reserve", action), selected)
        self.assertEqual(c.log_path.read_bytes(), before)
        altered = copy.deepcopy(action); altered["cost_upper_bound"] = 2
        with self.assertRaisesRegex(ControllerError, "changed payload"):
            c.select("reserve", altered)
        result = c.record("record", selected["attempt_id"], outcome(status="failed"))
        self.assertEqual(result["credited_questions"], [])
        self.assertEqual(c.record("record", selected["attempt_id"], outcome(status="failed")), result)
        self.assertEqual(c.usage()["attempts"], 1)

    def test_failed_attempt_consumes_budget_and_is_preserved(self):
        c = self.seeded(budget={**BUDGET, "max_attempts": 1})
        attempt = c.select("reserve", make_action(c))
        c.record("record", attempt["attempt_id"], outcome(status="failed"))
        next_action = make_action(c, "repair", spec={"artifact": "digest-A", "check": "corrected-parser"})
        self.assertIsNone(c.preview([next_action])["selected"])
        self.assertIn("failures included", c.preview([next_action])["stop_reason"])
        self.assertEqual(c.preview([next_action])["state"], "stopped")
        self.assertEqual(c.state["attempts"][attempt["attempt_id"]]["status"], "failed")

    def test_resource_reservations_prevent_concurrent_overspend(self):
        c = self.seeded(budget={**BUDGET, "max_resource_units": 5})
        self.extra_question(c)
        c.select("reserve", make_action(c, cost=3))
        a = make_action(c, "other", "b2", "q2", spec={"check": "independent"}, cost=3)
        self.assertIsNone(c.preview([a])["selected"])
        self.assertEqual(c.usage()["resource_units_committed"], 3)
        failed = outcome(status="failed", units=1)
        c.record("record", "attempt-0001", failed)
        self.assertEqual(c.preview([a])["selected"]["id"], "other")

    def test_resource_overrun_is_recorded_then_stops_future_work(self):
        c = self.seeded()
        c.select("reserve", make_action(c, cost=2))
        result = c.record("record", "attempt-0001", outcome(units=4, status="failed"))
        self.assertTrue(result["resource_bound_breached"])
        self.extra_question(c)
        trace = c.preview([make_action(c, "other", "b2", "q2", spec={"new": "check"})])
        self.assertIsNone(trace["selected"])
        self.assertIn("exceeded", trace["stop_reason"])
        self.assertEqual(trace["state"], "stopped")
        self.assertEqual(c.usage()["resource_units_committed"], 4)

    def test_action_rename_or_observation_key_change_cannot_duplicate(self):
        c = self.seeded()
        a, b = make_action(c), make_action(c, "renamed")
        trace = c.preview([a, b])
        self.assertEqual(len(trace["ranked"]), 1)
        c.select("reserve", a)
        self.assertIsNone(c.preview([b])["selected"])
        with self.assertRaises(ControllerError):
            c.select("duplicate", b)

    def test_question_aliases_and_shared_evidence_have_single_progress_credit(self):
        c = self.seeded()
        alias = c.register_question("alias", "renamed-q", {"scope": "fixture-A", "estimand": "Are execution expenses included?"})
        self.assertEqual(alias["canonical_id"], "q")
        self.assertFalse(alias["new_question"])
        self.extra_question(c)
        c.select("reserve", make_action(c))
        c.record("record", "attempt-0001", outcome())
        second = make_action(c, "different", "b2", "q2", spec={"check": "alternative-question"})
        c.select("reserve-2", second)
        result = c.record("record-2", "attempt-0002", outcome(question="q2"))
        self.assertEqual(result["credited_questions"], [])
        self.assertEqual(c.state["resolved_questions"], ["q"])

    def test_negative_finding_and_shared_question_resolution_count_once(self):
        c = self.seeded()
        self.extra_question(c)
        a = make_action(c); a["shared_questions"] = ["q2", "q2"]
        c.select("reserve", a)
        observed = outcome()
        observed["resolutions"].append({"question_id": "q2", "decision": "reject", "finding": "Same check settles second distinct question", "evidence": ["receipt:A"]})
        observed["resolutions"].append(copy.deepcopy(observed["resolutions"][0]))
        result = c.record("record", "attempt-0001", observed)
        self.assertEqual(result["credited_questions"], ["q", "q2"])
        self.assertEqual(c.state["credited_evidence"], ["receipt:A"])
        self.assertEqual(c.state["resolved_questions"], ["q", "q2"])

    def test_shared_question_cannot_have_two_measurements_pending(self):
        c = self.seeded()
        self.extra_question(c)
        a = make_action(c); a["shared_questions"] = ["q2"]
        c.select("reserve", a)
        other = make_action(c, "other", "b2", "q2", spec={"new": "differentcheck"})
        self.assertIsNone(c.preview([other])["selected"])

    def test_cached_result_has_no_fresh_progress_credit(self):
        c = self.seeded()
        c.select("reserve", make_action(c))
        result = c.record("record", "attempt-0001", outcome(kind="cache_reuse"))
        self.assertEqual(result["credited_questions"], [])
        self.assertEqual(c.state["resolved_questions"], [])

    def test_branch_stop_and_reopening_require_new_evidence_and_reason(self):
        c = self.seeded()
        c.set_branch("retire", branch_id="b", status="retired", reason="specified falsifier met", evidence=["finding:A"])
        self.assertIsNone(c.preview([make_action(c)])["selected"])
        with self.assertRaisesRegex(ControllerError, "Reopening"):
            c.set_branch("bad-reopen", branch_id="b", status="active", reason="new words", evidence=["finding:A"])
        c.set_branch("pause", branch_id="b", status="paused", reason="awaiting review", evidence=[])
        with self.assertRaisesRegex(ControllerError, "Reopening"):
            c.set_branch("bad-reset", branch_id="b", status="active", reason="specified falsifier met", evidence=["finding:A"])
        c.set_branch("reopen", branch_id="b", status="active", reason="new input corrects assumption", evidence=["finding:B"])
        self.assertIsNotNone(c.preview([make_action(c)])["selected"])
        self.assertEqual(len(c.state["branches"]["b"]["status_history"]), 4)

    def test_child_and_active_branch_limits(self):
        c = self.seeded(child_limit=1)
        self.extra_question(c, parent="b")
        with self.assertRaisesRegex(ControllerError, "child limit"):
            self.extra_question(c, "q3", "b3", parent="b")
        c.close()
        other_path = self.path / "other"
        with ResearchController(other_path, context=CONTEXT, budget={**BUDGET, "max_active_branches": 1}) as d:
            d.register_question("q", "q", {"check": "one"})
            d.register_branch("b", branch_id="b", question_id="q", mechanism="a")
            with self.assertRaisesRegex(ControllerError, "Active branch"):
                d.register_branch("b2", branch_id="b2", question_id="q", mechanism="b")

    def test_breadth_first_baseline_uses_same_feasibility_gates(self):
        c = self.seeded()
        self.extra_question(c, parent="b")
        shallow = make_action(c, "z-shallow", cls=1)
        deep = make_action(c, "a-deep", "b2", "q2", spec={"new": "deeper"}, cls=3)
        blocked = make_action(c, "0-blocked", cost=200)
        self.assertEqual(c.preview([shallow, deep, blocked])["selected"]["id"], "a-deep")
        baseline = c.preview([shallow, deep, blocked], policy="breadth_first")
        self.assertEqual(baseline["selected"]["id"], "z-shallow")
        self.assertEqual({a["id"] for a in baseline["ranked"]}, {"z-shallow", "a-deep"})
        self.assertIn("0-blocked", {x["id"] for x in baseline["excluded"]})

    def test_score_context_and_budget_cannot_change_on_resume(self):
        c = self.seeded(); c.close()
        with self.assertRaises(ControllerError):
            self.new(context={**CONTEXT, "score_version": "post-result-policy"})
        with self.assertRaises(ControllerError):
            self.new(budget={**BUDGET, "max_attempts": 99})

    def test_second_writer_refused_and_read_copy_cannot_mutate_state(self):
        c = self.seeded()
        with self.assertRaises(WriterBusy):
            self.new()
        detached = c.state
        detached["branches"]["b"]["status"] = "retired"
        self.assertEqual(c.state["branches"]["b"]["status"], "active")
        c.close()
        d = self.new()
        self.assertEqual(d.state["branches"]["b"]["status"], "active")

    def test_snapshot_crash_window_recovers_without_reexecuting(self):
        c = self.seeded()
        before = c.snapshot_path.read_bytes()
        a = make_action(c)
        with patch.object(c, "_snapshot", side_effect=OSError("simulated replace interruption")):
            with self.assertRaises(OSError):
                c.select("reserve", a)
        self.assertEqual(c.snapshot_path.read_bytes(), before)
        d = self.new()
        self.assertEqual(d.usage()["attempts"], 1)
        self.assertEqual(d.select("reserve", a)["attempt_id"], "attempt-0001")
        self.assertEqual(json.loads(d.snapshot_path.read_text())["sequence"], 4)

    def test_tampered_snapshot_and_partial_log_fail_closed(self):
        c = self.seeded(); c.close()
        saved = self.path / "snapshot.json"
        s = json.loads(saved.read_text()); s["state"]["resolved_questions"] = ["invented"]
        saved.write_text(json.dumps(s))
        with self.assertRaisesRegex(ControllerError, "Snapshot differs"):
            self.new()
        saved.unlink()
        d = self.new(); d.close()
        with (self.path / "events.jsonl").open("ab") as f:
            f.write(b'{"unfinished":')
        with self.assertRaisesRegex(ControllerError, "Partial"):
            self.new()

    def test_modified_log_record_breaks_chain(self):
        c = self.seeded(); c.close()
        p = self.path / "events.jsonl"
        lines = p.read_text().splitlines()
        record = json.loads(lines[1]); record["event"]["payload"]["definition"] = {"changed": "question"}
        lines[1] = json.dumps(record); p.write_text("\n".join(lines) + "\n")
        with self.assertRaisesRegex(ControllerError, "hash chain"):
            self.new()

    def test_missing_witness_or_unknown_cost_cannot_be_reserved(self):
        c = self.seeded()
        unknown = make_action(c); unknown["cost_upper_bound"] = None
        self.assertIsNone(c.preview([unknown])["selected"])
        invalid = make_action(c); invalid["witness"] = []
        with self.assertRaises(ValueError):
            c.preview([invalid])
        self.assertEqual(c.usage()["attempts"], 0)

    def test_unlinked_resolution_and_nonfinite_resource_rejected_without_log_write(self):
        c = self.seeded(); c.select("reserve", make_action(c))
        before = c.log_path.read_bytes()
        bad = outcome(); bad["resolutions"][0]["evidence"] = ["not-in-artifact-list"]
        with self.assertRaises(ControllerError):
            c.record("record-bad", "attempt-0001", bad)
        bad = outcome(units=float("nan"))
        with self.assertRaises(ControllerError):
            c.record("record-nan", "attempt-0001", bad)
        self.assertEqual(c.log_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
