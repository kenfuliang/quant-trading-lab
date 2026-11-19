"""Artifact catalog: loader validation, schema-id scan, deterministic markdown and the check CLI."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from research.control import artifacts
from research.control.artifacts import ArtifactsError, STAGES, load_artifacts, render_markdown, scan_schema_ids
from scripts import artifacts as cli

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "research/registry/artifacts.json"
SCAN_ROOTS = [ROOT / name for name in ("research", "scripts", "paper_trading", "reporting")]


def entry(**over):
    base = {"schema_id": "demo-output/v1", "name": "Demo output", "stage": "run", "location": "local",
            "authority": "authoritative", "producer": "scripts/artifacts.py", "consumers": ["scripts/readiness.py"],
            "retention": "local, per worktree", "status": "implemented"}
    base.update(over)
    return base


def document(*entries, updated="2026-11-18"):
    return {"schema": "artifacts/v1", "updated": updated, "entries": list(entries)}


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class ArtifactsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def load(self, doc):
        path = self.root / "artifacts.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        return load_artifacts(path)

    def test_rejects_bad_stage_location_authority_status_and_duplicates(self):
        cases = {
            "stage": entry(stage="elsewhere"),
            "location": entry(location="cloud"),
            "authority": entry(authority="boss"),
            "status": entry(status="done"),
            "bad id": entry(schema_id="Demo"),
            "null id on implemented": entry(schema_id=None),
            "id on template-only": entry(status="template-only"),
            "empty producer": entry(producer=" "),
            "consumers not a list": entry(consumers="scripts/readiness.py"),
            "extra field": entry(extra=1),
        }
        for name, bad in cases.items():
            with self.subTest(name):
                with self.assertRaises(ArtifactsError):
                    self.load(document(bad))
        with self.subTest("duplicate schema id"):
            with self.assertRaises(ArtifactsError):
                self.load(document(entry(), entry(name="Other")))
        with self.subTest("duplicate name"):
            with self.assertRaises(ArtifactsError):
                self.load(document(entry(), entry(schema_id="other/v1")))
        with self.subTest("bad date"):
            with self.assertRaises(ArtifactsError):
                self.load(document(entry(), updated="yesterday"))
        with self.subTest("valid with template"):
            ok = self.load(document(entry(), entry(schema_id=None, name="T", status="template-only")))
            self.assertEqual(len(ok), 2)

    def test_scan_finds_ids_in_both_quote_styles_and_schema_literals(self):
        pkg = self.root / "research"
        pkg.mkdir()
        (pkg / "a.py").write_text('SCHEMA = "alpha/v1"\nOTHER = "not-a-schema/v9"\n', encoding="utf-8")
        (pkg / "b.py").write_text("SCHEMA = 'beta/v2'\nRECEIPT_SCHEMA = \"gamma/v3\"\n", encoding="utf-8")
        (pkg / "c.py").write_text('doc = {"schema": "delta/v1"}\nx = dict(schema=\'eps/v1\')\n'
                                  'ok = d.get("schema") == "zeta/v1"\nurl = "https://x.test/api/v1"\n',
                                  encoding="utf-8")
        (pkg / "d.txt").write_text('SCHEMA = "ignored/v1"\n', encoding="utf-8")
        (pkg / "e.py").write_text('SCHEMA: str = "eta/v1"\nOTHER_SCHEMA : Final = \'theta/v2\'\n'
                                  'doc = {"schema": "Iota/v1"}\n', encoding="utf-8")
        found = scan_schema_ids([pkg, self.root / "missing"])
        self.assertEqual(set(found), {"alpha/v1", "beta/v2", "gamma/v3", "delta/v1", "eps/v1", "zeta/v1",
                                      "eta/v1", "theta/v2", "Iota/v1"})
        self.assertEqual(found["alpha/v1"], ["research/a.py"])

    def test_missing_producer_or_consumer_path_fails_naming_entry(self):
        cases = (("producer", "scripts/nope.py log", "nope.py"),
                 ("consumers", ["research/gone/thing.json"], "thing.json"))
        for field, bad, token in cases:
            with self.subTest(field):
                with self.assertRaisesRegex(ArtifactsError, rf"Demo output: .*{token} does not exist"):
                    self.load(document(entry(**{field: bad})))
        with self.subTest("cli check"):
            registry = self.root / "artifacts.json"
            registry.write_text(json.dumps(document(entry(producer="scripts/nope.py"))), encoding="utf-8")
            code, _, err = run("--registry", str(registry), "--doc", str(self.root / "d.md"), "--scan", str(self.root), "check")
            self.assertEqual(code, 1)
            self.assertIn("Demo output: scripts/nope.py does not exist", err)

    def test_unregistered_schema_id_fails_naming_file(self):
        pkg = self.root / "scripts"
        pkg.mkdir()
        (pkg / "maker.py").write_text('SCHEMA = "ghost/v1"\n', encoding="utf-8")
        registry = self.root / "artifacts.json"
        registry.write_text(json.dumps(document(entry())), encoding="utf-8")
        doc = self.root / "artifacts.md"
        code, _, _ = run("--registry", str(registry), "--doc", str(doc), "render")
        self.assertEqual(code, 0)
        code, _, err = run("--registry", str(registry), "--doc", str(doc), "--scan", str(pkg), "check")
        self.assertEqual(code, 1)
        self.assertIn("scripts/maker.py", err)
        self.assertIn("ghost/v1", err)

    def test_real_code_ids_are_all_catalogued(self):
        known = {e["schema_id"] for e in load_artifacts(REGISTRY)}
        found = scan_schema_ids([r for r in SCAN_ROOTS if r.exists()])
        self.assertTrue(found)
        self.assertEqual({i: f for i, f in found.items() if i not in known}, {})
        self.assertIn("artifacts/v1", known)
        self.assertEqual(artifacts.SCHEMA, "artifacts/v1")

    def test_markdown_groups_by_stage_and_is_deterministic(self):
        entries = self.load(document(
            entry(name="Zed", schema_id="zed/v1", stage="views"),
            entry(name="Beta", schema_id="beta/v1", stage="run", consumers=["a | b <i>"]),
            entry(name="Alpha", schema_id="alpha/v1", stage="run"),
            entry(name="Dat", schema_id="dat/v1", stage="data")))
        text = render_markdown(entries, "2026-11-18")
        self.assertEqual(text, render_markdown(copy.deepcopy(entries), "2026-11-18"))
        self.assertTrue(text.startswith("---\nstatus: active\nupdated: 2026-11-18\nowner: project-maintainers\n---\n"))
        self.assertIn("<!-- Generated by scripts/artifacts.py render. Do not edit by hand. -->", text)
        self.assertLess(text.index("| Alpha |"), text.index("| Beta |"))
        self.assertLess(text.index("| Dat |"), text.index("| Alpha |"))
        self.assertLess(text.index("| Beta |"), text.index("| Zed |"))
        self.assertNotIn("<i>", text)
        self.assertEqual(STAGES[0], "intake")
        self.assertEqual(STAGES[-1], "views")

    def test_check_fails_on_stale_or_hand_edited_doc(self):
        doc = self.root / "artifacts.md"
        self.assertEqual(run("--doc", str(doc), "render")[0], 0)
        self.assertEqual(run("--doc", str(doc), "check")[0], 0)
        doc.write_text(doc.read_text(encoding="utf-8") + "\nhand edit\n", encoding="utf-8")
        code, _, err = run("--doc", str(doc), "check")
        self.assertEqual(code, 1)
        self.assertIn(f"error: {doc} is stale; run scripts/artifacts.py render", err)
        doc.unlink()
        self.assertEqual(run("--doc", str(doc), "check")[0], 1)

    def test_committed_doc_is_current(self):
        self.assertEqual(run("check")[0], 0)


if __name__ == "__main__":
    unittest.main()
