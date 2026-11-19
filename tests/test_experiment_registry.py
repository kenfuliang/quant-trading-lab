import contextlib
import copy
import hashlib
import io
import shutil
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from research.control import experiment_registry as reg
from research.control.leaderboard_import import COLUMNS, parse_leaderboard
from research.control.registry_views import frontier_ids, learning_curve, render_dead_ends, render_leaderboard, render_learning_curve
from scripts import experiments as cli

ROOT = Path(__file__).resolve().parents[1]


def rec(rid="a-1", cagr=0.2, dd=0.1, cls="development", disp="inconclusive", name="Variant", ctx="C1", at="2026-11-09T00:00:00+00:00", **extra):
    base = {"imported": True, "schema": reg.SCHEMA, "record_id": rid, "logged_at": at, "name": name,
            "context": {"code": ctx, "period": "2020-2025"}, "evidence_class": cls, "disposition": disp,
            "lesson": "A lesson.", "metrics": {"net_cagr": cagr, "max_drawdown": dd}}
    base.update(extra)
    return base


class RegistryCoreTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "experiments.jsonl"

    def test_append_and_load_round_trip_in_order(self):
        reg.append(self.path, rec("a-1"))
        reg.append(self.path, rec("a-2"))
        self.assertEqual([r["record_id"] for r in reg.load(self.path)], ["a-1", "a-2"])

    def test_tampered_metric_breaks_the_chain(self):
        reg.append(self.path, rec("a-1"))
        reg.append(self.path, rec("a-2"))
        self.path.write_text(self.path.read_text().replace('"net_cagr": 0.2', '"net_cagr": 0.9', 1))
        with self.assertRaisesRegex(reg.RegistryError, "chain"):
            reg.load(self.path)

    def test_deleting_the_first_record_breaks_the_chain(self):
        reg.append(self.path, rec("a-1"))
        reg.append(self.path, rec("a-2"))
        self.path.write_text(self.path.read_text().splitlines()[1] + "\n")
        with self.assertRaises(reg.RegistryError):
            reg.load(self.path)

    def test_duplicate_id_is_refused(self):
        reg.append(self.path, rec("a-1"))
        with self.assertRaisesRegex(reg.RegistryError, "already exists"):
            reg.append(self.path, rec("a-1"))

    def test_invalid_records_are_rejected(self):
        bad = [
            rec(dd=-0.1), rec(cagr="12%"), rec(cagr=math.nan), rec(cls="hindsight"), rec(disp="win"),
            rec(at="2026-11-09T00:00:00"), rec(at="2026-11-09T00:00:00+02:00"), rec(rid="x"),
            {**rec(), "lesson": " "}, {**rec(), "metrics": {"profit": 1}},
            {**rec(), "metrics": {"longest_underwater_days": -3}}, {**rec(), "tags": "a"},
        ]
        for record in bad:
            with self.subTest(record=record):
                with self.assertRaises(reg.RegistryError):
                    reg.validate(copy.deepcopy(record))

    def test_null_metrics_are_allowed_for_blocked_runs(self):
        record = rec(disp="blocked")
        record["metrics"] = {}
        reg.append(self.path, record)
        self.assertEqual(len(reg.load(self.path)), 1)

    def test_new_completed_record_without_run_refs_is_rejected(self):
        for refs in ({}, {"run_id": "R1"}, {"run_manifest_sha256": "a" * 64},
                     {"run_id": "R1", "run_manifest_sha256": "short"}):
            with self.subTest(refs=refs), self.assertRaisesRegex(reg.RegistryError, "run_id|run_manifest_sha256"):
                reg.validate(rec(imported=False, refs=refs))
        reg.validate(rec(imported=False, refs={"run_id": "R1", "run_manifest_sha256": "a" * 64}))
        with self.assertRaisesRegex(reg.RegistryError, "run_id.*run_manifest_sha256"):
            reg.validate(rec(imported=False))  # no refs at all names both keys

    def test_blocked_failed_and_abandoned_need_no_run_output(self):
        reg.validate(rec(imported=False, disp="blocked"))
        for attempt in ("failed", "abandoned"):
            reg.validate(rec(imported=False, attempt=attempt))
        with self.assertRaisesRegex(reg.RegistryError, "attempt"):
            reg.validate(rec(imported=False, attempt="done"))
        with self.assertRaisesRegex(reg.RegistryError, "run_id"):
            reg.validate(rec(imported=False, attempt="completed"))

    def test_imported_records_are_exempt(self):
        reg.validate(rec(imported=True))
        reg.validate(rec(imported=True, disp="keep"))
        reg.validate(rec())  # rec() defaults to imported

    def test_existing_registry_still_validates(self):
        records = reg.load(ROOT / "research/registry/experiments.jsonl")
        self.assertEqual(len(records), 110)

    def test_keep_without_each_rule3_ref_names_it(self):
        full = {"run_id": "R1", "run_manifest_sha256": "a" * 64,
                "nautilus_run_id": "N1", "nautilus_run_manifest_sha256": "b" * 64,
                "parity_receipt_id": "P1", "parity_receipt_sha256": "c" * 64,
                "validation_receipt": "VR1", "validation_receipt_sha256": "d" * 64}
        reg.validate(rec(imported=False, disp="keep", refs=dict(full)))
        for group in (("nautilus_run_id", "nautilus_run_manifest_sha256"),
                      ("parity_receipt_id", "parity_receipt_sha256"),
                      ("validation_receipt", "validation_receipt_sha256")):
            for key in group:
                with self.subTest(missing=key):
                    refs = {k: v for k, v in full.items() if k != key}
                    with self.assertRaisesRegex(reg.RegistryError, key):
                        reg.validate(rec(imported=False, disp="keep", refs=refs))
        with self.assertRaisesRegex(reg.RegistryError, "parity_receipt_sha256"):
            reg.validate(rec(imported=False, disp="keep", refs={**full, "parity_receipt_sha256": "zz"}))


class ViewTests(unittest.TestCase):
    def test_frontier_keeps_ties_and_drops_dominated(self):
        a, b, c = rec("a-1", .2, .1), rec("a-2", .3, .2), rec("a-3", .15, .2)
        tie = rec("a-4", .2, .1)
        self.assertEqual(frontier_ids([a, b, c]), {"a-1", "a-2"})
        self.assertEqual(frontier_ids([a, tie]), {"a-1", "a-4"})

    def test_records_without_metrics_are_unranked_not_hidden(self):
        blocked = rec("a-9", disp="blocked", name="Blocked idea")
        blocked["metrics"] = {}
        text = render_leaderboard([rec("a-1"), blocked])
        self.assertIn("Blocked idea", text)
        self.assertIn("unranked", text)

    def test_drawdown_beyond_tolerance_is_flagged_not_hidden(self):
        text = render_leaderboard([rec("a-1", .9, .37, name="Aggressive")])
        self.assertIn("Aggressive", text)
        self.assertIn("DD>30%", text)

    def test_evidence_classes_are_separate_sections(self):
        text = render_leaderboard([rec("a-1", name="Hindsight"), rec("a-2", cls="paper", name="Real paper")])
        paper = text.index("## Paper")
        development = text.index("## Development")
        self.assertLess(paper, development)
        self.assertIn("Real paper", text[paper:development])
        self.assertNotIn("Hindsight", text[paper:development])

    def test_pipes_and_newlines_in_text_cannot_break_tables(self):
        text = render_leaderboard([rec("a-1", name="A | B\nC")])
        self.assertIn("A / B C", text)

    def test_dead_ends_list_retired_and_blocked_with_lessons(self):
        records = [rec("a-1", disp="retire", name="Dud", lesson="Costs killed it."),
                   rec("a-2", disp="keep", name="Fine"), rec("a-3", disp="blocked", name="Stuck")]
        text = render_dead_ends(records)
        self.assertIn("Costs killed it.", text)
        self.assertIn("Stuck", text)
        self.assertNotIn("Fine", text)

    def test_learning_curve_only_counts_improvements_within_tolerance(self):
        records = [rec("a-1", .10, .10, at="2026-01-01T00:00:00+00:00"),
                   rec("a-2", .50, .45, at="2026-01-02T00:00:00+00:00"),
                   rec("a-3", .20, .20, at="2026-01-03T00:00:00+00:00"),
                   rec("a-4", .15, .10, at="2026-01-04T00:00:00+00:00")]
        count, steps = learning_curve(records, "development")
        self.assertEqual(count, 4)
        self.assertEqual([s[0] for s in steps], [1, 3])

    def test_rendering_is_deterministic(self):
        records = [rec("a-1"), rec("a-2", .3, .2)]
        self.assertEqual(render_leaderboard(records), render_leaderboard(list(records)))
        self.assertEqual(render_learning_curve(records), render_learning_curve(list(records)))


class ImporterTests(unittest.TestCase):
    def table(self, *rows):
        return "\n".join(["| " + " | ".join(COLUMNS) + " |", "|" + " --- |" * len(COLUMNS), *rows])

    def test_row_parsing(self):
        row = ("| Test gate · 5bp | 1.50 | Audited | 12.5% | 17.5% | 199 /292 | 0.9 | SPY · risk gate · 5bp | C1 | 2020–2025 | "
               "Rejected fixed target | [Study](tasks/a.md) · [Receipt](tasks/evidence/a.json) | Lesson text. |")
        r = parse_leaderboard(self.table(row), "2026-10-31T00:00:00+00:00")[0]
        reg.validate(r)
        self.assertAlmostEqual(r["metrics"]["net_cagr"], 0.125)
        self.assertAlmostEqual(r["metrics"]["max_drawdown"], 0.175)
        self.assertEqual((r["metrics"]["longest_underwater_sessions"], r["metrics"]["longest_underwater_days"]), (199, 292))
        self.assertEqual(r["disposition"], "retire")
        self.assertEqual(r["context"]["costs_bp"], 5.0)
        self.assertEqual(r["refs"], {"receipt": "tasks/evidence/a.json", "study": "tasks/a.md"})
        self.assertTrue(r["imported"] and r["legacy_row"].startswith("| Test gate"))

    def test_missing_values_become_null_not_guesses(self):
        row = "| X | n/a | Missing | Missing | - | Missing in fresh capture | - | tag | C | P | Out | none | |"
        r = parse_leaderboard(self.table(row), "2026-10-31T00:00:00+00:00")[0]
        reg.validate(r)
        self.assertIsNone(r["metrics"]["net_cagr"])
        self.assertIsNone(r["metrics"]["longest_underwater_days"])

    def test_changed_columns_fail_loudly(self):
        with self.assertRaises(ValueError):
            parse_leaderboard("| a | b |\n| --- | --- |\n| 1 | 2 |", "2026-10-31T00:00:00+00:00")

    def test_archived_table_imports_completely(self):
        text = (ROOT / "docs/history/2026-11-09-hand-edited-leaderboard.md").read_text()
        records = parse_leaderboard(text, "2026-10-31T00:00:00+00:00")
        self.assertEqual(len(records), 109)
        self.assertEqual(len({r["record_id"] for r in records}), 109)
        for r in records:
            reg.validate(r)

    def test_committed_registry_matches_the_archive_row_count(self):
        records = reg.load(ROOT / "research/registry/experiments.jsonl")
        self.assertEqual(sum(1 for r in records if r.get("imported")), 109)


class CliTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.docs = self.root / "docs"
        (self.docs / "tasks/evidence").mkdir(parents=True)
        self.registry = self.root / "experiments.jsonl"
        self.runs, self.parity, self.receipts = self.root / "runs", self.root / "parity", self.root / "vr"
        self.make_run("R1")
        for target, value in [("DOCS", self.docs), ("RECEIPTS", self.docs / "tasks/evidence"),
                              ("EXEMPTIONS", self.root / "exempt.json")]:
            patcher = mock.patch.object(cli, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--registry", str(self.registry), *argv])
        return code, out.getvalue(), err.getvalue()

    def log(self, rid="t-1", *extra):
        return self.run_cli("log", "--id", rid, "--name", "Gate", "--context", "C1", "--period", "2020-2025",
                            "--disposition", "retire", "--lesson", "Did not help.",
                            "--metrics", json.dumps({"net_cagr": 0.1, "max_drawdown": 0.2}),
                            "--runs-root", str(self.runs), "--run-id", "R1", *extra)

    def write_json(self, path, doc):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, sort_keys=True))
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def make_run(self, run_id, **fields):
        doc = {"run_id": run_id, "engine": "screen", "code_commit": "aaa111", "use": "financial",
               "datasets": {"quality_status": "pass"}, **fields}
        return self.write_json(self.runs / run_id / "manifest.json", doc)

    def make_parity(self, parity_id="P1", **fields):
        doc = {"parity_id": parity_id, "status": "passed", "passed": True, "mismatch_count": 0,
               "code_commit": "bbb222", "runs": {"nautilus": {"run_id": "N1"}}, **fields}
        return self.write_json(self.parity / parity_id / "receipt.json", doc)

    def make_validation(self, receipt_id="VR1", **fields):
        doc = json.loads((ROOT / "tests/fixtures/validation-receipt-pass.json").read_text())
        doc.update(receipt_id=receipt_id, run_ids=["R1", "N1"], **fields)
        return self.write_json(self.receipts / f"{receipt_id}.json", doc)

    def keep_args(self, rid="k-1", *extra):
        return ("log", "--id", rid, "--name", "Promote", "--context", "C1", "--period", "2020-2025",
                "--disposition", "keep", "--lesson", "Held up.",
                "--metrics", json.dumps({"net_cagr": 0.2, "max_drawdown": 0.1}),
                "--runs-root", str(self.runs), "--parity-root", str(self.parity), "--receipts-dir", str(self.receipts),
                "--run-id", "R1", "--nautilus-run-id", "N1", "--parity-receipt", "P1",
                "--validation-receipt", "VR1", *extra)

    def setup_keep(self):
        self.make_run("N1", engine="nautilus", use="engineering", code_commit="ccc333")
        self.make_parity()
        self.make_validation()
        patcher = mock.patch.object(cli, "run_git", lambda args: (0, ""))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_log_render_check_cycle(self):
        self.assertEqual(self.log()[0], 0)
        self.assertEqual(self.run_cli("check")[0], 1)  # views not rendered yet
        self.assertEqual(self.run_cli("render")[0], 0)
        self.assertEqual(self.run_cli("check")[0], 0)
        self.assertIn("Did not help.", (self.docs / "dead-ends.md").read_text())

    def test_stale_view_is_detected_after_a_new_record(self):
        self.log()
        self.run_cli("render")
        self.log("t-2")
        code, _, err = self.run_cli("check")
        self.assertEqual(code, 1)
        self.assertIn("stale", err)

    def test_duplicate_id_and_bad_metrics_fail(self):
        self.log()
        self.assertEqual(self.log()[0], 1)
        code, _, _ = self.run_cli("log", "--id", "t-9", "--name", "X", "--context", "C", "--period", "P",
                                  "--disposition", "keep", "--lesson", "l", "--metrics", '{"max_drawdown": -1}')
        self.assertEqual(code, 1)

    def test_dry_run_writes_nothing(self):
        code, out, _ = self.log("t-3", "--dry-run")
        self.assertEqual(code, 0)
        self.assertFalse(self.registry.exists())
        self.assertIn('"record_id": "t-3"', out)

    def test_uncovered_v1_receipt_fails_check_unless_exempt(self):
        (self.docs / "tasks/evidence/r.json").write_text(json.dumps({"schema": "experiment-receipt/v1"}))
        self.run_cli("render")
        code, _, err = self.run_cli("check")
        self.assertEqual(code, 1)
        self.assertIn("tasks/evidence/r.json", err)
        (self.root / "exempt.json").write_text(json.dumps({"tasks/evidence/r.json": "engineering only"}))
        self.assertEqual(self.run_cli("check")[0], 0)

    def test_logging_with_a_ledger_counts_trials_and_links_them(self):
        ledger = str(self.root / "ledger")
        self.log("t-1", "--ledger", ledger, "--cycle-id", "CY-1")
        self.log("t-2", "--ledger", ledger, "--cycle-id", "CY-1")
        trials = [r["refs"]["ledger_trial"]["trial_number"] for r in reg.load(self.registry)]
        self.assertEqual(trials, [1, 2])

    def test_log_rejects_hash_mismatch_missing_file_and_non_financial_run(self):
        code, _, err = self.log("t-1", "--run-id", "NOPE")
        self.assertEqual(code, 1)
        self.assertIn("not found", err)
        self.make_run("R2", use="engineering")
        self.assertEqual(self.log("t-2", "--run-id", "R2")[0], 1)
        self.make_run("R3", datasets={"quality_status": "pass-with-exceptions"})
        code, _, err = self.log("t-3", "--run-id", "R3")
        self.assertEqual(code, 1)
        self.assertIn("acceptance", err)
        self.make_run("R4", datasets={"quality_status": "fail"})
        self.assertEqual(self.log("t-4", "--run-id", "R4")[0], 1)
        self.assertFalse(self.registry.exists())
        # the sha is computed by the CLI from the file (not typed); a mismatch is covered in test_run_refs
        self.assertEqual(self.log("t-5")[0], 0)
        record = reg.load(self.registry)[0]
        self.assertEqual(record["refs"]["run_id"], "R1")
        self.assertEqual(record["refs"]["run_manifest_sha256"],
                         hashlib.sha256((self.runs / "R1" / "manifest.json").read_bytes()).hexdigest())

    def test_log_without_run_id_for_a_completed_record_names_the_missing_refs(self):
        code, _, err = self.run_cli("log", "--id", "t-1", "--name", "X", "--context", "C", "--period", "P",
                                    "--disposition", "retire", "--lesson", "l")
        self.assertEqual(code, 1)
        self.assertIn("run_id", err)
        self.assertIn("run_manifest_sha256", err)

    def test_log_accepts_pass_with_exceptions_when_accepted(self):
        accepted = {"quality_status": "pass-with-exceptions",
                    "acceptance": {"status": "accepted", "acceptance_sha256": "a" * 64}}
        self.make_run("R2", datasets=accepted)
        self.assertEqual(self.log("t-1", "--run-id", "R2")[0], 0)

    def test_failed_and_blocked_records_log_without_a_run(self):
        base = ("--name", "X", "--context", "C", "--period", "P", "--lesson", "l")
        self.assertEqual(self.run_cli("log", "--id", "t-1", *base, "--disposition", "retire", "--attempt", "failed")[0], 0)
        self.assertEqual(self.run_cli("log", "--id", "t-2", *base, "--disposition", "blocked")[0], 0)
        self.assertEqual(reg.load(self.registry)[0]["attempt"], "failed")

    def test_log_rejects_screen_engine_run_for_keep(self):
        self.setup_keep()
        self.make_run("N1", engine="screen")
        code, _, err = self.run_cli(*self.keep_args())
        self.assertEqual(code, 1)
        self.assertIn("nautilus", err)

    def test_log_rejects_dirty_or_mismatched_parity_receipt(self):
        self.setup_keep()
        for fields in ({"code_commit": "bbb222+dirty"}, {"status": "failed", "passed": False},
                       {"mismatch_count": 3}):
            with self.subTest(fields=fields):
                self.make_parity(**fields)
                code, _, err = self.run_cli(*self.keep_args())
                self.assertEqual(code, 1, err)
                self.assertIn("parity receipt P1", err)
        self.assertFalse(self.registry.exists())

    def test_log_accepts_candidate_run_that_differs_from_the_parity_run(self):
        self.setup_keep()
        self.make_parity(runs={"nautilus": {"run_id": "SOME-OTHER-RUN"}})
        code, _, err = self.run_cli(*self.keep_args())
        self.assertEqual(code, 0, err)

    def test_log_rejects_when_engine_files_changed_between_commits(self):
        self.setup_keep()
        calls = []

        def fake_git(args):
            calls.append(args)
            return 0, "research/evaluation/native_engine.py\n"
        with mock.patch.object(cli, "run_git", fake_git):
            code, _, err = self.run_cli(*self.keep_args())
        self.assertEqual(code, 1)
        self.assertIn("native_engine.py", err)
        self.assertIn("bbb222", calls[0])
        self.assertIn("ccc333", calls[0])
        self.assertFalse(self.registry.exists())

    def test_log_rejects_dirty_run_commit_for_keep(self):
        self.setup_keep()
        self.make_run("N1", engine="nautilus", code_commit="ccc333+dirty")
        self.assertEqual(self.run_cli(*self.keep_args())[0], 1)

    def test_log_rejects_bad_validation_receipt(self):
        self.setup_keep()
        for fields in ({"result": "fail"}, {"run_ids": ["R1"]}, {"schema": "other/v1"}):
            with self.subTest(fields=fields):
                doc = json.loads((ROOT / "tests/fixtures/validation-receipt-pass.json").read_text())
                doc.update({"receipt_id": "VR1", "run_ids": ["R1", "N1"], **fields})
                self.write_json(self.receipts / "VR1.json", doc)
                self.assertEqual(self.run_cli(*self.keep_args())[0], 1)
        (self.receipts / "VR1.json").unlink()
        code, _, err = self.run_cli(*self.keep_args())
        self.assertEqual(code, 1)
        self.assertIn("not found", err)

    def test_log_rejects_keep_with_research_skill_validator(self):
        self.setup_keep()
        self.make_validation(validator={"skill": "trade-experiment"})
        code, _, err = self.run_cli(*self.keep_args())
        self.assertEqual(code, 1)
        self.assertIn("Validation skill", err)
        self.assertFalse(self.registry.exists())

    def test_check_verifies_the_tracked_validation_receipt_of_a_keep_record(self):
        self.setup_keep()
        patcher = mock.patch.object(cli, "VALIDATION_RECEIPTS", self.receipts)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.assertEqual(self.run_cli(*self.keep_args())[0], 0)
        self.run_cli("render")
        self.assertEqual(self.run_cli("check")[0], 0)  # no runs or parity files are read
        original = (self.receipts / "VR1.json").read_bytes()
        (self.receipts / "VR1.json").write_bytes(original + b" ")  # tampered: sha mismatch
        code, _, err = self.run_cli("check")
        self.assertEqual(code, 1)
        self.assertIn("sha256 mismatch", err)
        doc = json.loads(original)
        for fields, text in (({"run_ids": ["OTHER"]}, "does not cover"),
                             ({"validator": {"skill": "trade-experiment"}}, "Validation skill")):
            sha = self.write_json(self.receipts / "VR1.json", {**doc, **fields})
            records = reg.load(self.registry)
            records[0]["refs"]["validation_receipt_sha256"] = sha  # sha now matches; content must still fail
            errors = cli.check_validation_refs(records)
            self.assertEqual(len(errors), 1)
            self.assertIn(text, errors[0])
        (self.receipts / "VR1.json").unlink()
        code, _, err = self.run_cli("check")
        self.assertEqual(code, 1)
        self.assertIn("not found", err)

    def test_keep_needs_every_rule3_flag(self):
        self.setup_keep()
        args = list(self.keep_args())
        names = {"--nautilus-run-id": "nautilus_run_id", "--parity-receipt": "parity_receipt_id",
                 "--validation-receipt": "validation_receipt"}
        for flag, key in names.items():
            with self.subTest(flag=flag):
                i = args.index(flag)
                code, _, err = self.run_cli(*args[:i], *args[i + 2:])
                self.assertEqual(code, 1)
                self.assertIn(key, err)

    def test_full_valid_keep_record_logs(self):
        self.setup_keep()
        code, _, err = self.run_cli(*self.keep_args())
        self.assertEqual(code, 0, err)
        refs = reg.load(self.registry)[0]["refs"]
        self.assertEqual({k: refs[k] for k in ("run_id", "nautilus_run_id", "parity_receipt_id", "validation_receipt")},
                         {"run_id": "R1", "nautilus_run_id": "N1", "parity_receipt_id": "P1", "validation_receipt": "VR1"})
        for key, path in (("run_manifest_sha256", self.runs / "R1/manifest.json"),
                          ("nautilus_run_manifest_sha256", self.runs / "N1/manifest.json"),
                          ("parity_receipt_sha256", self.parity / "P1/receipt.json"),
                          ("validation_receipt_sha256", self.receipts / "VR1.json")):
            self.assertEqual(refs[key], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_dry_run_also_verifies_files(self):
        self.assertEqual(self.log("t-1", "--run-id", "NOPE", "--dry-run")[0], 1)

    def test_check_structure_passes_without_local_files(self):
        self.setup_keep()
        self.assertEqual(self.run_cli(*self.keep_args())[0], 0)
        self.run_cli("render")
        patcher = mock.patch.object(cli, "VALIDATION_RECEIPTS", self.receipts)  # tracked, so it stays
        patcher.start()
        self.addCleanup(patcher.stop)
        for root in (self.runs, self.parity):  # local data is absent
            shutil.rmtree(root)
        code, _, err = self.run_cli("check")
        self.assertEqual(code, 0, err)

    def test_check_rejects_a_stored_new_record_that_skips_run_refs(self):
        entry = {"prev": reg.GENESIS, "record": rec("x-1", imported=False)}
        entry["hash"] = reg.canonical_hash({"prev": entry["prev"], "record": entry["record"]})
        self.registry.write_text(json.dumps(entry, sort_keys=True) + "\n")
        code, _, err = self.run_cli("check")
        self.assertEqual(code, 1)
        self.assertIn("run_id", err)


if __name__ == "__main__":
    unittest.main()
