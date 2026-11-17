import unittest

from research.control import experiment_registry as reg
from research.control.stage_map import STAGES
from research.control.stage_page import render_page
from research.control.stage_view import build_model


def rec(rid, cagr=0.2, dd=0.1, tags=(), disp="inconclusive", name=None, at="2026-11-09T00:00:00+00:00", **extra):
    metrics = {k: v for k, v in {"net_cagr": cagr, "max_drawdown": dd}.items() if v is not None}
    base = {"schema": reg.SCHEMA, "record_id": rid, "logged_at": at, "name": name or rid,
            "context": {"code": "C1", "period": "2020–2025"}, "evidence_class": "development",
            "disposition": disp, "lesson": "A lesson.", "metrics": metrics, "tags": list(tags),
            "evidence_status": "Audited ledger"}
    base.update(extra)
    return base


def entry(rid, stage="risk gate", control=None, reviewed=True):
    return {"record_id": rid, "stage_under_test": stage, "control": control, "reviewed": reviewed}


def page_for(records, stage_map, incumbents=None):
    return render_page(build_model(records, stage_map), records, incumbents or {}, "2026-11-17 09:00")


class StagePageTests(unittest.TestCase):
    def setUp(self):
        self.records = [rec("ctl", 1.1967, 0.5126, ["control"], "control"),
                        rec("gate", 0.9203, 0.3690, ["challenger"], "retire"),
                        rec("lost", tags=[]), rec("multi"), rec("sized")]
        self.stage_map = {"ctl": entry("ctl"), "gate": entry("gate", control="ctl"),
                          "multi": entry("multi", "multiple"), "sized": entry("sized", "sizing")}

    def test_every_stage_card_and_bucket_present(self):
        page = page_for(self.records, self.stage_map)
        for stage in STAGES:
            self.assertIn(f'data-stage="{stage}"', page)
        self.assertIn("1 unclassified", page)
        self.assertIn("1 unattributable", page)

    def test_no_improved_badge_when_none_exist(self):
        page = page_for(self.records, self.stage_map)
        self.assertIn('data-effect="tradeoff"', page)
        self.assertNotIn('data-effect="improved"', page)

    def test_declared_incumbent_shows_and_undeclared_is_named(self):
        incumbent = {"stage": "risk gate", "algorithm": "EMA/vol traffic light", "identity": "x",
                     "justified_by": "ctl", "availability": "unverified", "last_changed": None, "scope": "SPY"}
        page = page_for(self.records, self.stage_map, {"risk gate": incumbent})
        self.assertIn("EMA/vol traffic light", page)
        self.assertIn("undeclared", page)

    def test_every_record_is_unassessed_with_verbatim_status(self):
        page = page_for(self.records, self.stage_map)
        self.assertEqual(page.count('data-eligibility="unassessed"'), len(self.records))
        self.assertIn("Audited ledger", page)

    def test_markup_is_escaped(self):
        records = [rec("a-1", name="<script>x</script> & |")]
        records[0]["lesson"] = "<b>bold</b>"
        page = page_for(records, {})
        self.assertIn("&lt;script&gt;x&lt;/script&gt; &amp; |", page)
        self.assertNotIn("<script>x", page)
        self.assertNotIn("<b>bold</b>", page)

    def test_missing_metric_renders_n_a_not_zero(self):
        page = page_for([rec("a-1", cagr=0.5, dd=None)], {})
        self.assertIn("<td>50.00%</td><td>n/a</td>", page)
        self.assertNotIn(">0.00%<", page)

    def test_stage_card_lists_each_pair_with_deltas_and_lessons(self):
        page = page_for(self.records, self.stage_map)
        card = page.split('data-stage="risk gate"')[1].split('data-stage="sizing"')[0]
        self.assertIn("gate", card)
        self.assertIn("ctl", card)
        self.assertIn("net CAGR -27.64 pt", card)
        self.assertIn("max DD -14.36 pt", card)
        self.assertIn("<details", card)
        self.assertIn("A lesson.", card)

    def test_stage_card_pair_text_is_escaped(self):
        records = [rec("c", 0.5, 0.3, ["control"], "control", name="<i>ctl</i>"),
                   rec("x", 0.4, 0.2, ["challenger"], "retire", name="<b>x</b> & y")]
        records[1]["lesson"] = "<u>lesson</u>"
        page = page_for(records, {"c": entry("c"), "x": entry("x", control="c")})
        card = page.split('data-stage="risk gate"')[1].split('data-stage="sizing"')[0]
        self.assertIn("&lt;b&gt;x&lt;/b&gt; &amp; y", card)
        self.assertIn("&lt;u&gt;lesson&lt;/u&gt;", card)
        self.assertNotIn("<b>x</b>", page)

    def test_stage_cards_distinguish_no_evidence_from_no_matched_control(self):
        page = page_for(self.records, self.stage_map)
        card = lambda stage: page.split(f'data-stage="{stage}"')[1].split("data-stage=")[0]
        self.assertIn("no evidence", card("features"))
        self.assertIn("no matched control", card("sizing"))
        self.assertNotIn("no evidence", card("risk gate"))

    def test_empty_registry_renders_every_section(self):
        page = page_for([], {})
        for heading in ("Stage view", "Compare", "Trust", "Cycle log"):
            self.assertIn(f">{heading}<", page)

    def test_compare_offers_only_the_contexts_controls_as_incumbent(self):
        page = page_for(self.records, self.stage_map)
        self.assertIn('<option value="ctl" selected>', page)
        self.assertNotIn('<option value="gate"', page)

    def test_cycle_log_is_newest_first(self):
        records = [rec("old", at="2026-11-01T00:00:00+00:00"), rec("new", at="2026-11-05T00:00:00+00:00")]
        log = page_for(records, {}).split('id="cycle-log"')[1]
        self.assertLess(log.index(">new<"), log.index(">old<"))


if __name__ == "__main__":
    unittest.main()
