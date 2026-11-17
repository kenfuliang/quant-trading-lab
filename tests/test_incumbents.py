import json
import tempfile
import unittest
from pathlib import Path

from research.control import experiment_registry as reg
from research.control.incumbents import AVAILABILITY, IncumbentsError, load_incumbents, render_status
from research.control.stage_map import STAGES
from research.control.stage_view import build_model


def rec(rid, cagr=0.2, dd=0.1, tags=(), disp="inconclusive", at="2026-11-09T00:00:00+00:00"):
    return {"schema": reg.SCHEMA, "record_id": rid, "logged_at": at, "name": rid,
            "context": {"code": "C1", "period": "2020–2025"}, "evidence_class": "development",
            "disposition": disp, "lesson": "A lesson.", "metrics": {"net_cagr": cagr, "max_drawdown": dd},
            "tags": list(tags)}


def inc(stage="risk gate", algorithm="EMA/vol traffic light", justified_by="a-1", availability="unverified",
        last_changed=None, scope="SPY, 2020–2025"):
    return {"stage": stage, "algorithm": algorithm, "identity": "ema 50/200", "justified_by": justified_by,
            "availability": availability, "last_changed": last_changed, "scope": scope}


def entry(rid, stage="risk gate", control=None):
    return {"record_id": rid, "stage_under_test": stage, "control": control, "reviewed": True}


def data_rows(text):
    return [line for line in text.splitlines()
            if line.startswith("| ") and not line.startswith(("| Stage", "| ---"))]


class LoadTests(unittest.TestCase):
    def write(self, items, schema="incumbents/v1"):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "incumbents.json"
        path.write_text(json.dumps({"schema": schema, "incumbents": items}))
        return path

    def test_availability_vocabulary(self):
        self.assertEqual(AVAILABILITY, ("implemented", "unverified", "blocked", "planned"))

    def test_load_rejects_missing_justification_and_bad_values(self):
        for bad in (inc(justified_by="ghost"), inc(availability="live"), inc(stage="alpha"),
                    inc(last_changed={"cycle_id": "C1"}), inc(justified_by=None)):
            with self.subTest(bad=bad), self.assertRaises(IncumbentsError):
                load_incumbents(self.write([bad]), {"a-1"})
        with self.assertRaises(IncumbentsError):
            load_incumbents(self.write([inc(), inc()]), {"a-1"})
        with self.assertRaises(IncumbentsError):
            load_incumbents(self.write([inc()], schema="x"), {"a-1"})

    def test_none_algorithm_may_have_no_justification(self):
        loaded = load_incumbents(self.write([inc(algorithm="none", justified_by=None)]), {"a-1"})
        self.assertEqual(loaded["risk gate"]["algorithm"], "none")

    def test_load_returns_entries_by_stage_and_accepts_last_changed(self):
        changed = {"cycle_id": "C05", "date": "2026-10-28"}
        loaded = load_incumbents(self.write([inc(last_changed=changed), inc(stage="sizing")]), {"a-1"})
        self.assertEqual(set(loaded), {"risk gate", "sizing"})
        self.assertEqual(loaded["risk gate"]["last_changed"], changed)


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.records = [rec("ctl", 1.1967, 0.5126, ["control"], "control"),
                        rec("gate", 0.9203, 0.3690, ["challenger"], "retire"),
                        rec("other", 0.3, 0.2)]
        self.stage_map = {"ctl": entry("ctl"), "gate": entry("gate", control="ctl"), "other": entry("other", "sizing")}
        self.model = build_model(self.records, self.stage_map)

    def render(self, incumbents=None, records=None, model=None):
        return render_status(records or self.records, incumbents or {}, model or self.model)

    def test_render_has_one_row_per_stage_in_order(self):
        rows = data_rows(self.render())
        self.assertEqual(len(rows), 7)
        self.assertEqual([r.split(" | ")[0].removeprefix("| ") for r in rows], list(STAGES))

    def test_undeclared_stage_reads_undeclared(self):
        rows = data_rows(self.render({"sizing": inc("sizing", "Fixed size")}))
        by_stage = {r.split(" | ")[0].removeprefix("| "): r for r in rows}
        self.assertIn("undeclared", by_stage["execution"])
        self.assertIn("Fixed size", by_stage["sizing"])
        self.assertNotIn("undeclared", by_stage["sizing"])

    def test_latest_paired_result_text(self):
        row = [r for r in data_rows(self.render()) if r.startswith("| risk gate")][0]
        self.assertIn("tradeoff, retire: net CAGR -27.64 pt, max DD -14.36 pt", row)

    def test_latest_pair_is_the_newest_challenger(self):
        records = [rec("ctl", 0.5, 0.3, ["control"], "control"),
                   rec("old", 0.6, 0.2, ["challenger"], "retire", at="2026-11-01T00:00:00+00:00"),
                   rec("new", 0.4, 0.4, ["challenger"], "retire", at="2026-11-05T00:00:00+00:00")]
        stage_map = {"ctl": entry("ctl"), "old": entry("old", control="ctl"), "new": entry("new", control="ctl")}
        row = [r for r in data_rows(render_status(records, {}, build_model(records, stage_map))) if r.startswith("| risk gate")][0]
        self.assertIn("worse, retire: net CAGR -10.00 pt, max DD +10.00 pt", row)

    def test_no_matched_control_and_no_evidence_texts(self):
        by_stage = {r.split(" | ")[0].removeprefix("| "): r for r in data_rows(self.render())}
        self.assertIn("no matched control", by_stage["sizing"])
        self.assertIn("no evidence", by_stage["execution"])
        empty = render_status([], {}, build_model([], {}))
        self.assertTrue(all("no evidence" in r for r in data_rows(empty)))

    def test_missing_delta_renders_n_a(self):
        records = [rec("ctl", 0.5, 0.3, ["control"], "control"), rec("x", 0.6, 0.2, ["challenger"], "retire")]
        records[1]["metrics"].pop("max_drawdown")
        stage_map = {"ctl": entry("ctl"), "x": entry("x", control="ctl")}
        row = [r for r in data_rows(render_status(records, {}, build_model(records, stage_map))) if r.startswith("| risk gate")][0]
        self.assertIn("unmeasured, retire: net CAGR +10.00 pt, max DD n/a", row)

    def test_pipes_in_cells_are_escaped(self):
        row = [r for r in data_rows(self.render({"sizing": inc("sizing", "A|B")})) if r.startswith("| sizing")][0]
        self.assertIn("A/B", row)
        self.assertEqual(len(row.split(" | ")), 6)

    def test_render_is_deterministic_and_has_frontmatter(self):
        first = self.render({"sizing": inc("sizing", "Fixed size")})
        self.assertEqual(first, self.render({"sizing": inc("sizing", "Fixed size")}))
        self.assertTrue(first.startswith("---\nstatus: active\nupdated: 2026-11-09\nowner: project-maintainers\n---\n"))
        self.assertIn("# Pipeline status", first)
        self.assertIn("<!-- Generated by scripts/stages.py render. Do not edit by hand. -->", first)


if __name__ == "__main__":
    unittest.main()
