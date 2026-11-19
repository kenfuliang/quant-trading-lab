import unittest

from research.control import experiment_registry as reg
from research.control.stage_map import STAGES
from research.control.stage_view import build_model, classify, effect


def rec(rid, cagr=0.2, dd=0.1, tags=(), disp="inconclusive", code="C1", period="2020–2025", **metrics):
    base = {"net_cagr": cagr, "max_drawdown": dd}
    base.update(metrics)
    return {"schema": reg.SCHEMA, "record_id": rid, "logged_at": "2026-11-09T00:00:00+00:00",
            "name": rid, "context": {"code": code, "period": period}, "evidence_class": "development",
            "disposition": disp, "lesson": "A lesson.", "metrics": {k: v for k, v in base.items() if v is not None},
            "tags": list(tags)}


def entry(rid, stage="risk gate", control=None, reviewed=True):
    return {"record_id": rid, "stage_under_test": stage, "control": control, "reviewed": reviewed}


class ClassifyTests(unittest.TestCase):
    def test_classify_rules(self):
        r = rec("a-1")
        self.assertEqual(classify(r, None), "unclassified")
        self.assertEqual(classify(r, entry("a-1", "sizing", reviewed=False)), "unclassified")
        self.assertEqual(classify(r, entry("a-1", "multiple")), "unattributable")
        self.assertEqual(classify(r, entry("a-1", "sizing")), "sizing")
        self.assertEqual(classify(r, entry("a-1", None)), "unclassified")


class EffectTests(unittest.TestCase):
    def test_effect_cases(self):
        control = {"net_cagr": 0.25, "max_drawdown": 0.30}
        self.assertEqual(effect({"net_cagr": 0.30, "max_drawdown": 0.20}, {"net_cagr": 0.25, "max_drawdown": 0.30}), "improved")
        self.assertEqual(effect({"net_cagr": 0.20, "max_drawdown": 0.30}, {"net_cagr": 0.25, "max_drawdown": 0.20}), "worse")
        self.assertEqual(effect({"net_cagr": 0.30, "max_drawdown": 0.30}, {"net_cagr": 0.25, "max_drawdown": 0.20}), "tradeoff")
        self.assertEqual(effect(dict(control), dict(control)), "tie")
        self.assertEqual(effect({"net_cagr": 0.3}, control), "unmeasured")
        self.assertEqual(effect(control, {"net_cagr": None, "max_drawdown": 0.2}), "unmeasured")


class BuildModelTests(unittest.TestCase):
    def pair_fixture(self, control_period="2020–2025", control_named=True, **control_metrics):
        control = rec("t11-ctl", 1.1967, 0.5126, ["control"], "control", **control_metrics)
        control["context"]["period"] = control_period
        challenger = rec("t11-gate", 0.9203, 0.3690, ["challenger", "risk gate"], "retire")
        records = [control, challenger]
        stage_map = {"t11-gate": entry("t11-gate", "risk gate", "t11-ctl" if control_named else None),
                     "t11-ctl": entry("t11-ctl", "risk gate")}
        return records, stage_map

    def test_gated_t11_pair_is_a_tradeoff_with_both_deltas(self):
        records, stage_map = self.pair_fixture()
        cell = build_model(records, stage_map)["stages"]["risk gate"]
        (pair,) = cell["pairs"]
        self.assertEqual((pair["status"], pair["effect"], pair["disposition"]), ("matched", "tradeoff", "retire"))
        self.assertAlmostEqual(pair["delta"]["net_cagr"], -0.2764, places=4)
        self.assertAlmostEqual(pair["delta"]["max_drawdown"], -0.1436, places=4)
        self.assertEqual(cell["effects"], {"tradeoff": 1})
        self.assertEqual(cell["dispositions"], {"retire": 1})
        self.assertEqual(sorted(cell["records"]), ["t11-ctl", "t11-gate"])

    def test_control_in_other_period_is_ambiguous(self):
        records, stage_map = self.pair_fixture(control_period="2005–2025")
        cell = build_model(records, stage_map)["stages"]["risk gate"]
        (pair,) = cell["pairs"]
        self.assertEqual(pair["status"], "ambiguous control")
        self.assertEqual(pair["delta"], {})
        self.assertIsNone(pair["effect"])
        self.assertEqual(cell["effects"], {"ambiguous control": 1})

    def test_reviewed_control_makes_an_untagged_record_a_challenger(self):
        control = rec("ctl", 1.1967, 0.5126, ["control"], "control")
        gated = rec("gated", 0.9203, 0.3690, [], "inconclusive")
        stage_map = {"ctl": entry("ctl"), "gated": entry("gated", control="ctl")}
        (pair,) = build_model([control, gated], stage_map)["stages"]["risk gate"]["pairs"]
        self.assertEqual((pair["challenger"], pair["control"], pair["status"], pair["effect"]),
                         ("gated", "ctl", "matched", "tradeoff"))

    def test_records_without_a_named_control_and_tag_form_no_pair(self):
        records = [rec("ctl", tags=["control"], disp="control"), rec("plain")]
        stage_map = {"ctl": entry("ctl"), "plain": entry("plain")}
        self.assertEqual(build_model(records, stage_map)["stages"]["risk gate"]["pairs"], [])

    def test_challenger_without_named_control_is_ambiguous(self):
        records, stage_map = self.pair_fixture(control_named=False)
        (pair,) = build_model(records, stage_map)["stages"]["risk gate"]["pairs"]
        self.assertEqual((pair["status"], pair["control"], pair["delta"]), ("ambiguous control", None, {}))

    def test_missing_metric_gives_none_delta_not_zero(self):
        records, stage_map = self.pair_fixture(calmar=2.0)
        (pair,) = build_model(records, stage_map)["stages"]["risk gate"]["pairs"]
        self.assertIsNone(pair["delta"]["calmar"])
        self.assertIsNone(pair["delta"]["sharpe"])

    def test_unattributable_and_unclassified_stay_out_of_stage_cells(self):
        records = [rec("a-1"), rec("a-2"), rec("a-3", tags=["challenger"])]
        stage_map = {"a-1": entry("a-1", "multiple"), "a-3": entry("a-3", "sizing", reviewed=False)}
        model = build_model(records, stage_map)
        self.assertEqual(model["unattributable"], ["a-1"])
        self.assertEqual(model["unclassified"], ["a-2", "a-3"])
        self.assertTrue(all(not cell["records"] and not cell["pairs"] for cell in model["stages"].values()))

    def test_empty_registry_has_every_stage_with_zero_counts(self):
        model = build_model([], {})
        self.assertEqual(tuple(model["stages"]), STAGES)
        for cell in model["stages"].values():
            self.assertEqual(cell, {"records": [], "pairs": [], "effects": {}, "dispositions": {}})
        self.assertEqual((model["unclassified"], model["unattributable"], model["contexts"]), ([], [], {}))

    def test_contexts_group_record_ids_in_input_order(self):
        records = [rec("a-1"), rec("a-2", code="C2"), rec("a-3")]
        self.assertEqual(build_model(records, {})["contexts"], {"C1 · 2020–2025": ["a-1", "a-3"], "C2 · 2020–2025": ["a-2"]})


if __name__ == "__main__":
    unittest.main()
