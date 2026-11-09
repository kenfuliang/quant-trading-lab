import contextlib
import copy
import io
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
    base = {"schema": reg.SCHEMA, "record_id": rid, "logged_at": at, "name": name,
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
                            "--metrics", json.dumps({"net_cagr": 0.1, "max_drawdown": 0.2}), *extra)

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


if __name__ == "__main__":
    unittest.main()
