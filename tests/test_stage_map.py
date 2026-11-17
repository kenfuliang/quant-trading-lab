import json
import tempfile
import unittest
from pathlib import Path

from research.control import experiment_registry as reg
from research.control.registry_views import dominates
from research.control.stage_map import STAGES, StageMapError, draft_stage_map, load_stage_map, tag_stages


def rec(rid, tags=(), disp="inconclusive", code="C1", period="2020–2025"):
    return {"schema": reg.SCHEMA, "record_id": rid, "logged_at": "2026-11-09T00:00:00+00:00",
            "name": rid, "context": {"code": code, "period": period}, "evidence_class": "development",
            "disposition": disp, "lesson": "A lesson.", "metrics": {"net_cagr": 0.2, "max_drawdown": 0.1},
            "tags": list(tags)}


def entry(rid, stage="sizing", control=None, reviewed=True):
    return {"record_id": rid, "stage_under_test": stage, "control": control, "reviewed": reviewed}


class StageMapTests(unittest.TestCase):
    def write(self, doc):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "stage-map.json"
        path.write_text(json.dumps(doc))
        return path

    def test_stages_are_the_seven_pipeline_stages(self):
        self.assertEqual(STAGES, ("features", "market conditions", "position proposal",
                                  "target selection", "risk gate", "sizing", "execution"))

    def test_tag_stages_normalises_spellings(self):
        self.assertEqual(tag_stages(["selection", "traffic gate", "CAPM"]),
                         frozenset({"target selection", "risk gate"}))
        self.assertEqual(tag_stages(["feature representation"]), frozenset({"features"}))

    def test_draft_marks_every_entry_unreviewed(self):
        doc = draft_stage_map([rec("a-1"), rec("a-2"), rec("a-3")])
        self.assertEqual(doc["schema"], "stage-map/v1")
        self.assertEqual(len(doc["entries"]), 3)
        self.assertTrue(all(e["reviewed"] is False for e in doc["entries"]))

    def test_draft_stage_under_test_rules(self):
        doc = draft_stage_map([rec("a-1", ["sizing"]), rec("a-2", ["target selection", "traffic gate"]), rec("a-3")])
        stages = {e["record_id"]: e["stage_under_test"] for e in doc["entries"]}
        self.assertEqual(stages, {"a-1": "sizing", "a-2": "multiple", "a-3": None})

    def test_draft_control_only_when_context_has_exactly_one_control(self):
        one = draft_stage_map([rec("c-1", disp="control"), rec("x-1", ["challenger"]), rec("n-1")])
        by_id = {e["record_id"]: e["control"] for e in one["entries"]}
        self.assertEqual(by_id, {"c-1": None, "x-1": "c-1", "n-1": None})
        two = draft_stage_map([rec("c-1", disp="control"), rec("c-2", disp="control"), rec("x-1", ["challenger"])])
        self.assertIsNone({e["record_id"]: e["control"] for e in two["entries"]}["x-1"])

    def test_draft_control_must_share_context(self):
        doc = draft_stage_map([rec("c-1", disp="control", period="2005–2025"), rec("x-1", ["challenger"])])
        self.assertIsNone({e["record_id"]: e["control"] for e in doc["entries"]}["x-1"])

    def test_load_rejects_unknown_record_id(self):
        path = self.write({"schema": "stage-map/v1", "entries": [entry("ghost")]})
        with self.assertRaises(StageMapError) as caught:
            load_stage_map(path, {"a-1"})
        self.assertIn("ghost", str(caught.exception))

    def test_load_rejects_unknown_control(self):
        path = self.write({"schema": "stage-map/v1", "entries": [entry("a-1", control="ghost")]})
        with self.assertRaises(StageMapError):
            load_stage_map(path, {"a-1"})

    def test_load_rejects_a_record_that_is_its_own_control(self):
        path = self.write({"schema": "stage-map/v1", "entries": [entry("a-1", control="a-1")]})
        with self.assertRaises(StageMapError) as caught:
            load_stage_map(path, {"a-1"})
        self.assertIn("own control", str(caught.exception))

    def test_load_rejects_bad_stage_and_bad_schema(self):
        bad_stage = self.write({"schema": "stage-map/v1", "entries": [entry("a-1", stage="foo")]})
        with self.assertRaises(StageMapError):
            load_stage_map(bad_stage, {"a-1"})
        bad_schema = self.write({"schema": "x", "entries": []})
        with self.assertRaises(StageMapError):
            load_stage_map(bad_schema, {"a-1"})

    def test_load_returns_entries_by_record_id(self):
        path = self.write({"schema": "stage-map/v1", "entries": [
            entry("a-1"), entry("a-2", stage="multiple"), entry("a-3", stage=None, reviewed=False)]})
        loaded = load_stage_map(path, {"a-1", "a-2", "a-3"})
        self.assertEqual(set(loaded), {"a-1", "a-2", "a-3"})
        self.assertEqual(loaded["a-2"]["stage_under_test"], "multiple")


class DominatesTests(unittest.TestCase):
    def test_tie_is_false_both_ways(self):
        a = {"net_cagr": 0.2, "max_drawdown": 0.1}
        b = dict(a)
        self.assertFalse(dominates(a, b))
        self.assertFalse(dominates(b, a))

    def test_better_on_one_and_equal_on_other_dominates(self):
        better = {"net_cagr": 0.3, "max_drawdown": 0.1}
        base = {"net_cagr": 0.2, "max_drawdown": 0.1}
        self.assertTrue(dominates(better, base))
        self.assertFalse(dominates(base, better))

    def test_tradeoff_dominates_neither_way(self):
        a = {"net_cagr": 0.3, "max_drawdown": 0.3}
        b = {"net_cagr": 0.2, "max_drawdown": 0.1}
        self.assertFalse(dominates(a, b))
        self.assertFalse(dominates(b, a))


if __name__ == "__main__":
    unittest.main()
