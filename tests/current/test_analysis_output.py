"""Offline tests of the analysis-output document, its writer and the tearsheet wrapper."""
import copy
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from reporting.run_tearsheet import tearsheet_html
from research.evaluation.analysis_output import SCHEMA, build_analysis, render_report, write_analysis
from research.evaluation.metrics import METRIC_KEYS

SUMMARY = {k: 0.5 for k in METRIC_KEYS}
STEPS = [{"rung": "hold", "run_id": "r1", "summary": dict(SUMMARY)},
         {"rung": "trend", "run_id": "r2", "summary": {**SUMMARY, "sharpe": 0.9}}]
WATERFALL = [{"from": "hold", "to": "trend", "delta": {k: (0.4 if k == "sharpe" else 0.0) for k in METRIC_KEYS}}]
TRUST = {"psr": {"value": 0.8, "n": 100}, "dsr": {"value": None, "reason": "n_trials < 2"},
         "pbo": {"value": None, "reason": "no grid"}}
LOOKAHEAD = {"status": "pass", "cutoffs": ["2024-02-01"], "compared": [{"cutoff": "2024-02-01", "compared_signals": 7}],
             "differences": []}
SPEC = {"spec_id": "demo<spec>", "title": "Demo", "notes": ["a note"]}
PROVENANCE = {"code_commit": "abc", "datasets": {"dataset_id": "synthetic-fixture"}}
NOW = "2026-11-18T12:00:00+00:00"


def make_doc():
    return build_analysis(SPEC, STEPS, TRUST, LOOKAHEAD, None, PROVENANCE, NOW)


class AnalysisOutputTests(unittest.TestCase):
    def test_analysis_doc_has_schema_and_keys(self):
        doc = make_doc()
        self.assertEqual(doc["schema"], SCHEMA)
        self.assertEqual(SCHEMA, "analysis-output/v1")
        for key in ("analysis_id", "spec_id", "created_utc", "code_commit", "datasets", "runs", "waterfall",
                    "trust", "lookahead", "comparison", "notes"):
            self.assertIn(key, doc)
        self.assertEqual(doc["runs"], STEPS)
        self.assertEqual(doc["code_commit"], "abc")
        self.assertEqual(set(doc["trust"]), {"psr", "dsr", "pbo"})
        self.assertEqual([w["to"] for w in doc["waterfall"]], ["trend"])
        self.assertNotIn("/", doc["analysis_id"])  # safe as a folder name despite the spec id

    def test_write_is_exclusive(self):
        doc = make_doc()
        with tempfile.TemporaryDirectory() as tmp:
            first = write_analysis(Path(tmp), doc, "<html>t</html>", "# r")
            self.assertEqual(first, Path(tmp) / "analysis" / doc["analysis_id"])
            self.assertEqual(sorted(p.name for p in first.iterdir()), ["analysis.json", "report.md", "tearsheet.html"])
            before = (first / "analysis.json").read_text()
            with self.assertRaises(FileExistsError):
                write_analysis(Path(tmp), copy.deepcopy(doc), "<html>other</html>", "# other")
            self.assertEqual((first / "analysis.json").read_text(), before)
            self.assertEqual((first / "tearsheet.html").read_text(), "<html>t</html>")

    def test_write_without_tearsheet_omits_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = write_analysis(Path(tmp), make_doc(), None, "# r")
            self.assertEqual(sorted(p.name for p in folder.iterdir()), ["analysis.json", "report.md"])

    def test_report_markdown_lists_waterfall_and_trust(self):
        report = render_report(make_doc())
        self.assertIn("## Waterfall", report)
        self.assertIn("hold -> trend", report)
        self.assertIn("## Trust", report)
        self.assertIn("PSR", report)
        self.assertIn("n_trials < 2", report)  # null values carry their reason
        self.assertIn("## Lookahead", report)
        self.assertIn("compared_signals", report)
        self.assertIn("a note", report)

    def test_tearsheet_html_contains_title(self):
        returns = pd.Series(np.random.default_rng(1).normal(0, 0.01, 120),
                            index=pd.bdate_range("2024-01-02", periods=120))
        page = tearsheet_html(returns, {"Sharpe (0% risk-free)": 0.5}, "Demo tearsheet")
        self.assertIn("Demo tearsheet", page)
        self.assertIn("<html", page.lower())


if __name__ == "__main__":
    unittest.main()
