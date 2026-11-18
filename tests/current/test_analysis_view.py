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

    def test_tearsheet_link_is_relative_and_only_for_available_safe_ids(self):
        doc = copy.deepcopy(FIXTURE)
        aid = doc["analysis_id"]
        self.assertNotIn("open tearsheet", render_analysis_page([doc], "now"))
        page = render_analysis_page([doc], "now", available={aid})
        self.assertIn(f'href="analysis/{aid}/tearsheet.html"', page)
        self.assertNotIn("file://", page)
        bad = copy.deepcopy(FIXTURE)
        bad["analysis_id"] = "../x"
        self.assertNotIn("open tearsheet", render_analysis_page([bad], "now", available={"../x"}))

    def test_build_copies_tearsheet_where_the_page_links(self):
        from scripts import analysis as shim
        with tempfile.TemporaryDirectory() as t, tempfile.TemporaryDirectory() as out:
            folder = write(t, FIXTURE, FIXTURE["analysis_id"])
            (folder / "tearsheet.html").write_text("sheet")
            self.assertEqual(shim.main(["build", "--root", t, "--dir", out]), 0)
            aid = FIXTURE["analysis_id"]
            self.assertEqual((Path(out) / "analysis" / aid / "tearsheet.html").read_text(), "sheet")
            self.assertIn(f'href="analysis/{aid}/tearsheet.html"', (Path(out) / "analysis.html").read_text())

    def test_malformed_sections_are_skipped_and_do_not_crash(self):
        with tempfile.TemporaryDirectory() as t:
            for n, patch in enumerate(({"runs": "x"}, {"trust": []}, {"waterfall": [1]}, {"notes": "n"},
                                       {"lookahead": {"differences": "d"}}, {"tearsheet": "s"})):
                write(t, {**FIXTURE, **patch, "analysis_id": f"m{n}", "spec_id": f"s{n}"}, f"m{n}")
            analyses, warnings = load_analyses(t)
            self.assertEqual((analyses, len(warnings)), ([], 6))
            self.assertIn("No analyses", render_analysis_page(analyses, "now"))

    def test_ordering_parses_timestamps(self):
        with tempfile.TemporaryDirectory() as t:
            a, b = copy.deepcopy(FIXTURE), copy.deepcopy(FIXTURE)
            a.update(analysis_id="a", created_utc="2026-01-01T10:00:00+02:00")  # 08:00 UTC
            b.update(analysis_id="b", created_utc="2026-01-01T09:00:00+00:00")
            for d in (a, b):
                write(t, d, d["analysis_id"])
            self.assertEqual(load_analyses(t)[0][0]["analysis_id"], "b")

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
