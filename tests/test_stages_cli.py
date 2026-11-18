import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from research.control import experiment_registry as reg
from scripts import stages as cli


def rec(rid, tags=(), disp="inconclusive", cagr=0.2, dd=0.1):
    return {"schema": reg.SCHEMA, "record_id": rid, "logged_at": "2026-11-09T00:00:00+00:00", "name": rid,
            "context": {"code": "C1", "period": "2020–2025"}, "evidence_class": "development",
            "disposition": disp, "lesson": "A lesson.", "metrics": {"net_cagr": cagr, "max_drawdown": dd},
            "tags": list(tags)}


class StagesCliTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.registry = self.dir / "experiments.jsonl"
        for record in (rec("c-1", ["control", "risk gate"], "control", 0.5, 0.3),
                       rec("x-1", ["challenger", "risk gate"], "retire", 0.4, 0.2),
                       rec("n-1", ["sizing"])):
            reg.append(self.registry, record)
        self.stage_map = self.dir / "stage-map.json"
        self.incumbents = self.dir / "incumbents.json"
        self.status = self.dir / "pipeline-status.md"
        self.incumbents.write_text(json.dumps({"schema": "incumbents/v1", "incumbents": [
            {"stage": "risk gate", "algorithm": "EMA/vol traffic light", "identity": "ema 50/200",
             "justified_by": "c-1", "availability": "unverified", "last_changed": None, "scope": "SPY"}]}))

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        # build reads analyses from the data root: keep it in the temp dir, never the real one
        with mock.patch.dict(os.environ, {"QTL_DATA_ROOT": str(self.dir / "data")}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--registry", str(self.registry), "--stage-map", str(self.stage_map),
                             "--incumbents", str(self.incumbents), "--status-doc", str(self.status), *args])
        return code, out.getvalue(), err.getvalue()

    def prepare(self):
        self.assertEqual(self.run_cli("draft-map")[0], 0)
        self.assertEqual(self.run_cli("render")[0], 0)

    def test_draft_map_writes_unreviewed_entries_and_refuses_overwrite(self):
        self.assertEqual(self.run_cli("draft-map")[0], 0)
        doc = json.loads(self.stage_map.read_text())
        self.assertEqual(doc["schema"], "stage-map/v1")
        self.assertEqual(len(doc["entries"]), 3)
        self.assertTrue(all(e["reviewed"] is False for e in doc["entries"]))
        before = self.stage_map.read_text()
        code, _, err = self.run_cli("draft-map")
        self.assertEqual(code, 1)
        self.assertIn("exists", err)
        self.assertEqual(self.stage_map.read_text(), before)

    def test_render_then_check_passes(self):
        self.prepare()
        self.assertIn("# Pipeline status", self.status.read_text())
        code, out, err = self.run_cli("check")
        self.assertEqual((code, err), (0, ""))
        self.assertIn("passed", out)

    def test_check_fails_when_status_doc_edited_by_hand(self):
        self.prepare()
        self.status.write_text(self.status.read_text() + "hand edit\n")
        code, _, err = self.run_cli("check")
        self.assertEqual(code, 1)
        self.assertIn("stale", err)

    def test_check_fails_when_stage_map_names_missing_record(self):
        self.prepare()
        doc = json.loads(self.stage_map.read_text())
        doc["entries"].append({"record_id": "ghost", "stage_under_test": None, "control": None, "reviewed": False})
        self.stage_map.write_text(json.dumps(doc))
        code, _, err = self.run_cli("check")
        self.assertEqual(code, 1)
        self.assertIn("ghost", err)

    def test_check_fails_when_incumbent_justified_by_missing_record(self):
        self.prepare()
        doc = json.loads(self.incumbents.read_text())
        doc["incumbents"][0]["justified_by"] = "ghost"
        self.incumbents.write_text(json.dumps(doc))
        code, _, err = self.run_cli("check")
        self.assertEqual(code, 1)
        self.assertIn("ghost", err)

    def test_check_fails_when_a_file_is_missing(self):
        self.prepare()
        self.stage_map.unlink()
        code, _, err = self.run_cli("check")
        self.assertEqual(code, 1)
        self.assertIn("missing", err)

    def test_build_writes_pipeline_page_and_leaves_inputs_untouched(self):
        self.prepare()
        inputs = [self.registry, self.stage_map, self.incumbents]
        before = [p.read_bytes() for p in inputs]
        out = self.dir / "pages"
        code, stdout, err = self.run_cli("build", "--dir", str(out))
        self.assertEqual((code, err), (0, ""))
        page = (out / "stages.html").read_text()
        self.assertIn("<title>Pipeline</title>", page)
        self.assertIn("EMA/vol traffic light", page)
        self.assertEqual([p.read_bytes() for p in inputs], before)

    def test_build_fails_on_invalid_declarations_and_writes_nothing(self):
        self.prepare()
        self.stage_map.unlink()
        out = self.dir / "pages"
        code, _, err = self.run_cli("build", "--dir", str(out))
        self.assertEqual(code, 1)
        self.assertIn("missing", err)
        self.assertFalse((out / "stages.html").exists())

    def test_render_without_declarations_fails_instead_of_guessing(self):
        code, _, err = self.run_cli("render")
        self.assertEqual(code, 1)
        self.assertIn("missing", err)
        self.assertFalse(self.status.exists())


if __name__ == "__main__":
    unittest.main()
