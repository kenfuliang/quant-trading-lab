import json
import tempfile
import unittest
from pathlib import Path

from scripts import t11_target_view as tv


def make_run(root, name, asof, status=tv.GOOD, weights=None, cap=1.0, state="green", with_plan=True):
    folder = Path(root) / name
    folder.mkdir(parents=True)
    weights = weights if weights is not None else {"TECL": 1 / 3, "SOXL": 1 / 3, "TQQQ": 1 / 3}
    summary = {"status": status, "asof_session": asof,
               "gate": {"state": state, "cap": cap, "vol": 0.1, "original2004_seed_parity": False},
               "policy": {"base_weights": weights, "gated_weights": weights, "reason": "bull_risk"},
               "limitations": ["unqualified"]}
    (folder / "summary.json").write_text(json.dumps(summary))
    if with_plan:
        (folder / "plan.json").write_text(json.dumps({"created_utc": f"{asof}T22:00:00+00:00"}))


class TargetViewTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_only_completed_runs_are_loaded_in_session_order(self):
        make_run(self.root, "r2", "2026-11-03")
        make_run(self.root, "r1", "2026-11-02")
        make_run(self.root, "bad", "2026-11-04", status="failed_preserved")
        (self.root / "broken").mkdir()
        (self.root / "broken/summary.json").write_text("not json")
        runs, skipped = tv.load_runs(self.root)
        self.assertEqual([r["asof"] for r in runs], ["2026-11-02", "2026-11-03"])
        self.assertEqual(skipped, 2)

    def test_zero_weights_are_dropped_and_cap_is_kept(self):
        make_run(self.root, "r1", "2026-11-02", weights={"TQQQ": 1.0, "SQQQ": 0.0}, cap=0.5, state="yellow")
        runs, _ = tv.load_runs(self.root)
        self.assertEqual(runs[0]["weights"], {"TQQQ": 1.0})
        self.assertEqual(runs[0]["gate"]["cap"], 0.5)

    def test_page_states_the_limits_and_escapes_embedded_data(self):
        make_run(self.root, "r1", "2026-11-02")
        out = self.root / "t.html"
        self.assertEqual(tv.main(["--root", str(self.root), "--out", str(out), "--built", "2026-11-09"]), 0)
        page = out.read_text()
        for text in ("unqualified and not for orders", "Nothing here is advice", "Sizing helper", "Per-day log"):
            self.assertIn(text, page)
        self.assertEqual(page.count("</script>"), 1)

    def test_empty_root_still_renders(self):
        out = self.root / "t.html"
        self.assertEqual(tv.main(["--root", str(self.root / "none"), "--out", str(out)]), 0)
        self.assertIn("No completed preview runs", out.read_text())

    def test_built_date_drives_the_staleness_banner_input(self):
        make_run(self.root, "r1", "2026-10-29")
        out = self.root / "t.html"
        tv.main(["--root", str(self.root), "--out", str(out), "--built", "2026-11-08"])
        self.assertIn('BUILT="2026-11-08"', out.read_text())


if __name__ == "__main__":
    unittest.main()
