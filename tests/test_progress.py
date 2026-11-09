import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from research.control.progress import build_model, forward_clock, render_html, validate_gates
from scripts import progress as cli

ROOT = Path(__file__).resolve().parents[1]


def gates():
    def item(i, status, owner="agent", evidence=("a.md",), **kw):
        return {"id": i, "text": f"Item {i}", "status": status, "owner": owner, "evidence": list(evidence), **kw}
    return {"schema": "gates/v1", "gates": [
        {"id": "G1", "name": "First", "items": [item("G1.1", "met"), item("G1.2", "open", "user")]},
        {"id": "G2", "name": "Second <b>", "items": [item("G2.1", "blocked", "user", note="needs <script>"), item("G2.2", "partial")]}]}


def exists(path):
    return path == "a.md"


def records():
    base = {"schema": "experiment-record/v1", "logged_at": "2026-11-09T00:00:00+00:00", "lesson": "l",
            "context": {"code": "C", "period": "P"}, "evidence_class": "development", "disposition": "retire"}
    return [{**base, "record_id": "r-1", "name": "A", "metrics": {"net_cagr": 0.1, "max_drawdown": 0.2}},
            {**base, "record_id": "r-2", "name": "B", "disposition": "blocked", "metrics": {}}]


def model(today=date(2026, 11, 9), forward=None, health=None):
    return build_model(gates(), records(), forward, {"runs": 0, "decisions": 0, "last_run": None}, health,
                       {"trials": 0, "events": 2}, today)


class ValidateTests(unittest.TestCase):
    def test_valid_file_has_no_errors(self):
        self.assertEqual(validate_gates(gates(), exists), [])

    def test_problems_are_reported(self):
        for mutate, text in [
            (lambda g: g["gates"][0]["items"][0].update(status="done"), "status"),
            (lambda g: g["gates"][0]["items"][0].update(owner="bot"), "owner"),
            (lambda g: g["gates"][0]["items"][0].update(evidence=[]), "needs evidence"),
            (lambda g: g["gates"][0]["items"][0].update(evidence=["missing.md"]), "does not exist"),
            (lambda g: g["gates"][0]["items"][1].update(id="G1.1"), "unique"),
            (lambda g: g["gates"][0]["items"][1].update(id="G9.1"), "start with G1."),
            (lambda g: g["gates"][0]["items"][0].update(text=" "), "text is empty"),
        ]:
            with self.subTest(text=text):
                g = copy.deepcopy(gates())
                mutate(g)
                self.assertTrue(any(text in e for e in validate_gates(g, exists)), validate_gates(g, exists))

    def test_wrong_schema_is_rejected(self):
        self.assertTrue(validate_gates({"schema": "x"}, exists))

    def test_open_item_may_have_no_evidence(self):
        g = gates()
        g["gates"][0]["items"][1]["evidence"] = []
        self.assertEqual(validate_gates(g, exists), [])


class ModelTests(unittest.TestCase):
    def test_counts_and_waiting_list(self):
        m = model()
        self.assertEqual(m["totals"], {"met": 1, "partial": 1, "blocked": 1, "open": 1, "all": 4})
        self.assertEqual([w["id"] for w in m["waiting"]], ["G1.2", "G2.1"])
        self.assertEqual(m["records"], 2)
        self.assertEqual(m["dispositions"], {"retire": 1, "blocked": 1})

    def test_forward_clock_states(self):
        window = {"start": "2026-11-10", "end": "2027-11-09", "holdout_id": "H"}
        self.assertEqual(forward_clock(window, date(2026, 11, 9))["days_until_start"], 1)
        running = forward_clock(window, date(2026, 11, 10))
        self.assertEqual((running["state"], running["day"], running["total_days"]), ("running", 1, 365))
        self.assertEqual(forward_clock(window, date(2027, 11, 10))["state"], "complete")
        self.assertEqual(forward_clock(window, date(2027, 11, 10))["day"], 365)
        self.assertEqual(forward_clock(None, date(2026, 1, 1))["state"], "none")


class RenderTests(unittest.TestCase):
    def test_page_shows_each_gate_and_escapes_text(self):
        page = render_html(model())
        self.assertIn("G1", page)
        self.assertIn("Second &lt;b&gt;", page)
        self.assertIn("needs &lt;script&gt;", page)
        self.assertNotIn("<script>", page)

    def test_health_and_clock_appear(self):
        window = {"start": "2026-11-10", "end": "2027-11-09", "holdout_id": "SPY-FWD-1"}
        page = render_html(model(forward=window, health={"healthy": False, "checks": [{"name": "shadow", "state": "stale"}]}))
        self.assertIn("Starts in 1 day<", page)
        self.assertIn("Needs attention", page)
        self.assertIn("shadow stale", page)

    def test_evidence_becomes_a_link_only_when_resolvable(self):
        page = render_html(model(), lambda p: "../../" + p if p == "a.md" else None)
        self.assertIn('href="../../a.md"', page)


class RepoFileTests(unittest.TestCase):
    def test_committed_gates_file_is_valid_and_evidence_exists(self):
        data = json.loads((ROOT / "research/registry/gates.json").read_text())
        self.assertEqual(validate_gates(data, lambda p: (ROOT / p).exists()), [])

    def test_cli_check_and_build(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(cli.main(["check"]), 0)
            out = Path(t) / "index.html"
            self.assertEqual(cli.main(["build", "--local", str(Path(t) / "local"), "--out", str(out)]), 0)
            self.assertIn("Path to real money", out.read_text())


if __name__ == "__main__":
    unittest.main()
