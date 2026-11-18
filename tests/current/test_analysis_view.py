import copy
import json
import tempfile
import unittest
from pathlib import Path

from research.control.analysis_view import load_analyses, render_analysis_page, trust_rows
from research.control.stage_page import render_page

FIXTURE = json.loads((Path(__file__).resolve().parents[1] / "fixtures/analysis-fixture-ladder.json").read_text())


def write(root, doc, name):
    folder = Path(root) / "analysis" / name
    folder.mkdir(parents=True)
    (folder / "analysis.json").write_text(json.dumps(doc), encoding="utf-8")
    return folder


class AnalysisViewTest(unittest.TestCase):
    def test_loads_newest_per_spec_and_skips_invalid(self):
        with tempfile.TemporaryDirectory() as t:
            old, new, other = (copy.deepcopy(FIXTURE) for _ in range(3))
            old.update(analysis_id="a-old", created_utc="2026-01-01T00:00:00+00:00")
            new.update(analysis_id="a-new", created_utc="2026-02-01T00:00:00+00:00")
            other.update(analysis_id="b-1", spec_id="other", created_utc="2026-01-15T00:00:00+00:00")
            for doc in (old, new, other):
                write(t, doc, doc["analysis_id"])
            write(t, {**FIXTURE, "schema": "analysis-output/v0", "analysis_id": "bad1"}, "bad1")
            folder = Path(t) / "analysis" / "bad2"
            folder.mkdir()
            (folder / "analysis.json").write_text("{not json")
            analyses, warnings = load_analyses(t)
            self.assertEqual([a["analysis_id"] for a in analyses], ["a-new", "b-1"])
            self.assertEqual(len(warnings), 2)

    def test_absent_root_is_empty(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(load_analyses(t), ([], []))
            self.assertIn("No analyses yet", render_analysis_page([], "now"))

    def test_page_shows_waterfall_trust_lookahead_and_escapes(self):
        evil = "<script>alert(1)</script>"
        doc = copy.deepcopy(FIXTURE)
        doc.update(spec_id=evil, title=evil, notes=[evil])
        doc["runs"][0]["rung"] = evil
        doc["waterfall"][0]["to"] = evil
        doc["trust"]["dsr"]["reason"] = evil
        doc["tearsheet"] = {"status": "failed", "error": evil}
        doc["lookahead"]["differences"] = [evil]
        page = render_analysis_page([doc], evil)
        self.assertNotIn(evil, page)
        self.assertIn("&lt;script&gt;", page)
        for word in ("buy_hold", "Waterfall", "PSR", "DSR", "PBO", "Lookahead", "failed", "0.2492"):
            self.assertIn(word, page)
        self.assertIn('class="failed"', page)
        self.assertIn("n/a", page)

    def test_tearsheet_link_only_when_file_exists(self):
        with tempfile.TemporaryDirectory() as t:
            folder = write(t, FIXTURE, "a1")
            self.assertNotIn("open tearsheet", render_analysis_page(load_analyses(t)[0], "now"))
            (folder / "tearsheet.html").write_text("x")
            self.assertIn("open tearsheet", render_analysis_page(load_analyses(t)[0], "now"))

    def test_stage_page_trust_panel_uses_analyses_when_present(self):
        rows = trust_rows([FIXTURE])
        self.assertEqual(rows[0]["dsr"], "n/a")
        self.assertEqual(rows[0]["dsr_reason"], "no comparison record; trial count undefined")
        self.assertEqual(rows[0]["lookahead"], "pass")
        empty = {"stages": {}, "contexts": {}, "unclassified": [], "unattributable": []}
        from research.control.stage_map import STAGES
        empty["stages"] = {s: {"records": [], "pairs": [], "effects": {}, "dispositions": {}} for s in STAGES}
        plain = render_page(empty, [], {}, "now")
        shown = render_page(empty, [], {}, "now", [FIXTURE])
        self.assertNotIn("Analysis trust statistics", plain)
        self.assertIn("Analysis trust statistics", shown)
        self.assertIn("no comparison record", shown)
        evil = copy.deepcopy(FIXTURE)
        evil["spec_id"] = "<b>x</b>"
        self.assertNotIn("<b>x</b>", render_page(empty, [], {}, "now", [evil]))


if __name__ == "__main__":
    unittest.main()
