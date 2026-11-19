import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from research.data.manifest import sha256_file, write_manifest
from research.evaluation import data_quality as q
from research.evaluation.etf_normalise import RECIPE, normalise

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "data"
DAYS = ("2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05")
NO_ACTIONS = {"cash_and_in_kind": [], "splits": []}


def clean_rows():
    return [{"symbol": "AAA", "session": d, "o": "10.00", "h": "10.50", "l": "9.90",
             "c": "10.20", "v": "1000"} for d in DAYS]


def yahoo_for(rows):
    frame = pd.DataFrame({"close": [float(r["c"]) for r in rows]},
                         index=pd.Index([r["session"] for r in rows], name="date"))
    return {"AAA": frame}


def report_for(rows, actions=NO_ACTIONS, yahoo="same", names=("AAA",), yahoo_splits=None, **extra):
    norm = normalise(rows, actions, names)
    if isinstance(yahoo, str):
        yahoo = yahoo_for([r for r in rows if r["symbol"] == "AAA"])
    return q.build_report("ds", rows, norm, yahoo, norm.data.splits, created_utc="2026-01-01T00:00:00Z",
                          yahoo_splits=yahoo_splits, **extra)


def ysplit(date, num, den=1):
    # Yahoo's JSON carries the numerator and denominator as floats
    return {"date": date, "numerator": float(num), "denominator": float(den), "ratio": f"{num}:{den}"}


def check(report, name):
    return next(c for c in report["checks"] if c["name"] == name)


def fixture_rows_actions():
    return (json.loads((FIXTURES / "etf-bars.json").read_text()),
            json.loads((FIXTURES / "etf-actions.json").read_text()))


def fixture_report():
    rows = json.loads((FIXTURES / "etf-bars.json").read_text())
    actions = json.loads((FIXTURES / "etf-actions.json").read_text())
    norm = normalise(rows, actions, ("AAA", "PAR", "KID"))
    return q.build_report("ds", rows, norm, None, norm.data.splits)


class QualityTests(unittest.TestCase):
    def test_clean_fixture_passes(self):
        report = report_for(clean_rows())
        self.assertEqual(report["status"], "pass")
        self.assertEqual([c["name"] for c in report["checks"]], list(q.CHECKS))
        self.assertEqual({c["status"] for c in report["checks"]}, {"pass"})
        self.assertEqual(report["acceptance"], {"accepted_by": None, "accepted_utc": None})
        self.assertEqual(report["schema"], "quality-report/v1")

    def test_missing_session_fails(self):
        rows = [r for r in clean_rows() if r["session"] != "2024-01-03"]
        report = report_for(rows, yahoo=None)
        self.assertEqual(report["status"], "fail")
        self.assertEqual(check(report, "sessions")["status"], "fail")
        self.assertEqual(check(report, "sessions")["items"], [{"session": "2024-01-03", "problem": "missing"}])

    def test_rounding_conversion_and_exclusion_give_pass_with_exceptions(self):
        report = fixture_report()
        self.assertEqual(report["status"], "pass-with-exceptions")
        self.assertEqual(check(report, "cent_rounding")["status"], "exception")
        self.assertEqual(check(report, "cent_rounding")["count"], 2)
        self.assertEqual(check(report, "actions_converted")["count"], 1)
        self.assertEqual(check(report, "actions_excluded")["items"][0]["id"], "AAA-2024-01-09")
        self.assertEqual(check(report, "gaps")["status"], "pass")  # the 50% move is a split day

    def test_cross_source_unadjusts_yahoo_splits_before_comparing(self):
        rows = clean_rows()
        for r in rows[2:]:
            r.update(o="5.00", h="5.25", l="4.95", c="5.10")
        actions = {"cash_and_in_kind": [],
                   "splits": [{"id": "s", "symbol": "AAA", "kind": "split", "ex_date": "2024-01-04", "ratio": "2"}]}
        # pre-split closes are 10.20 raw; Yahoo shows 5.10 split-adjusted throughout
        yahoo = {"AAA": pd.DataFrame({"close": [5.10, 5.10, 5.10, 5.10]},
                                     index=pd.Index(DAYS, name="date"))}
        report = report_for(rows, actions, yahoo, yahoo_splits={"AAA": [ysplit("2024-01-04", 2)]})
        cross = check(report, "cross_source")
        self.assertEqual(cross["status"], "pass", cross)
        self.assertEqual(cross["stats"]["compared"], 4)
        self.assertEqual(cross["stats"]["breaches"], 0)
        self.assertEqual(check(report, "split_events")["status"], "pass")

    def test_split_consistency_passes_a_consistent_split_and_fails_a_bad_one(self):
        rows = clean_rows()
        for r in rows[2:]:
            r.update(o="5.00", h="5.25", l="4.95", c="5.10")
        actions = {"cash_and_in_kind": [],
                   "splits": [{"id": "s", "symbol": "AAA", "kind": "split", "ex_date": "2024-01-04", "ratio": "2"}]}
        good = check(report_for(rows, actions), "split_consistency")
        self.assertEqual((good["status"], good["count"]), ("pass", 0))
        bad_rows = clean_rows()  # a 2:1 split with no price drop: 10.20 * 2 / 10.20 = 2.0
        bad = check(report_for(bad_rows, actions), "split_consistency")
        self.assertEqual(bad["status"], "fail")
        self.assertEqual((bad["items"][0]["symbol"], bad["items"][0]["date"]), ("AAA", "2024-01-04"))

    def test_split_consistency_absent_without_splits(self):
        self.assertNotIn("split_consistency", [c["name"] for c in report_for(clean_rows())["checks"]])

    def test_post_window_adjustment_check_lists_excluded_names_and_ratios(self):
        rows = clean_rows()
        norm = normalise(rows, NO_ACTIONS, ("AAA",))

        def build(excluded):
            actions = dict(NO_ACTIONS, post_window_adjustment={
                "window_sessions": 20, "tolerance": 0.005, "checked": 5, "unchecked": [], "excluded": excluded})
            return q.build_report("ds", rows, norm, None, norm.data.splits, actions=actions, code_commit="t")
        found = check(build([{"symbol": "BKNG", "median_ratio": 25.0}]), "actions_post_window_adjustment")
        self.assertEqual(found["status"], "exception")
        self.assertEqual(found["items"], [{"symbol": "BKNG", "median_ratio": 25.0}])
        self.assertEqual(check(build([]), "actions_post_window_adjustment")["status"], "pass")
        plain = q.build_report("ds", rows, norm, None, norm.data.splits, code_commit="t")
        self.assertNotIn("actions_post_window_adjustment", [c["name"] for c in plain["checks"]])

    def test_cross_source_uses_yahoo_splits_not_ours(self):
        # Yahoo knows a 1231:1000 split we do not; its closes before it are scaled by 1000/1231.
        rows = clean_rows()
        yahoo = yahoo_for(rows)
        yahoo["AAA"].loc[["2024-01-02", "2024-01-03"], "close"] = 10.20 * 1000 / 1231
        report = report_for(rows, yahoo=yahoo, yahoo_splits={"AAA": [ysplit("2024-01-04", 1231, 1000)]})
        cross = check(report, "cross_source")
        self.assertEqual(cross["status"], "pass", cross)
        self.assertEqual(cross["stats"]["breaches"], 0)
        events = check(report, "split_events")
        self.assertEqual(events["status"], "exception")
        self.assertEqual(events["count"], 1)
        self.assertEqual(events["items"][0]["source"], "yahoo_only")
        self.assertEqual(events["items"][0]["symbol"], "AAA")
        self.assertEqual(events["items"][0]["date"], "2024-01-04")
        self.assertEqual(events["items"][0]["ratio"], "1231:1000")

    def test_split_events_yahoo_only_labels_our_in_kind_event(self):
        rows, actions = fixture_rows_actions()
        norm = normalise(rows, actions, ("AAA", "PAR", "KID"))
        yahoo = {"PAR": pd.DataFrame({"close": [1.0]}, index=pd.Index(["2024-01-02"], name="date"))}
        report = q.build_report("ds", rows, norm, yahoo, norm.data.splits, created_utc="2026-01-01T00:00:00Z",
                                yahoo_splits={"PAR": [ysplit("2024-01-04", 1231, 1000)]})
        events = check(report, "split_events")
        self.assertEqual(events["status"], "exception")
        self.assertIn("in-kind", events["items"][0]["note"])

    def test_split_events_ours_only_is_exception_and_match_is_pass(self):
        rows = clean_rows()
        for r in rows[2:]:
            r.update(o="5.00", h="5.25", l="4.95", c="5.10")
        actions = {"cash_and_in_kind": [],
                   "splits": [{"id": "s", "symbol": "AAA", "kind": "split", "ex_date": "2024-01-04", "ratio": "2"}]}
        yahoo = {"AAA": pd.DataFrame({"close": [10.2, 10.2, 5.1, 5.1]}, index=pd.Index(DAYS, name="date"))}
        events = check(report_for(rows, actions, yahoo, yahoo_splits={"AAA": []}), "split_events")
        self.assertEqual(events["status"], "exception")
        self.assertEqual(events["items"][0]["source"], "ours_only")
        ok = check(report_for(rows, actions, yahoo, yahoo_splits={"AAA": [ysplit("2024-01-04", 2)]}), "split_events")
        self.assertEqual(ok["status"], "pass")

    def test_split_events_without_snapshot_is_blocked(self):
        report = report_for(clean_rows(), yahoo=None)
        self.assertEqual(check(report, "split_events")["status"], "blocked")
        names = [c["name"] for c in report["checks"]]
        self.assertEqual(names.index("split_events"), names.index("cross_source") + 1)

    def test_cross_source_nothing_compared_is_blocked(self):
        rows = clean_rows()
        other = pd.DataFrame({"close": [1.0]}, index=pd.Index(["2020-01-02"], name="date"))
        cross = check(report_for(rows, yahoo={"AAA": other}), "cross_source")
        self.assertEqual(cross["status"], "blocked")
        self.assertEqual(cross["stats"]["compared"], 0)
        empty = check(report_for(rows, yahoo={}), "cross_source")
        self.assertEqual(empty["status"], "blocked")

    def test_cross_source_missing_sessions_or_symbols_is_exception_without_breaches(self):
        rows = clean_rows()
        yahoo = yahoo_for(rows)
        yahoo["AAA"] = yahoo["AAA"].drop(index="2024-01-03")
        cross = check(report_for(rows, yahoo=yahoo), "cross_source")
        self.assertEqual(cross["stats"]["breaches"], 0)
        self.assertEqual(cross["status"], "exception")
        self.assertEqual(cross["stats"]["not_compared_count"], 1)
        two = rows + [dict(r, symbol="BBB") for r in rows]
        report = report_for(two, yahoo=yahoo_for(rows), names=("AAA", "BBB"))
        self.assertEqual(check(report, "cross_source")["status"], "exception")

    def test_report_records_inputs_and_code_commit(self):
        inputs = {"manifest_sha256": "aa", "yahoo_snapshot_id": "snap", "yahoo_manifest_sha256": "bb"}
        report = report_for(clean_rows(), inputs=inputs, code_commit="abc123+dirty")
        self.assertEqual(report["inputs"], inputs)
        self.assertEqual(report["code_commit"], "abc123+dirty")
        bare = report_for(clean_rows(), yahoo=None)
        self.assertEqual(bare["inputs"], {"manifest_sha256": None, "yahoo_snapshot_id": None,
                                          "yahoo_manifest_sha256": None})
        self.assertIsInstance(bare["code_commit"], str)

    def test_markdown_more_line_counts_omitted_items_not_count(self):
        names = tuple(f"S{i}" for i in range(20))
        rows = [dict(r, symbol=n, v="0") for n in names for r in clean_rows()]
        norm = normalise(rows, NO_ACTIONS, names)
        zero = check(q.build_report("ds", rows, norm, None, ()), "zero_volume")
        text = q.render_report({"dataset_id": "ds", "schema": "s", "recipe": "r", "created_utc": "c",
                               "status": "x", "acceptance": {"accepted_by": None}, "checks": [zero]})
        self.assertIn("- ... 30 more in report.json", text)
        fine = [dict(r, c="10.201") for r in clean_rows()]
        rounding = check(report_for(fine, yahoo=None), "cent_rounding")
        self.assertGreater(rounding["count"], len(rounding["items"]))  # count is values changed, not items
        text = q.render_report({"dataset_id": "ds", "schema": "s", "recipe": "r", "created_utc": "c",
                               "status": "x", "acceptance": {"accepted_by": None}, "checks": [rounding]})
        self.assertNotIn("more in report.json", text)

    def test_cross_source_breach_is_exception_with_stats(self):
        rows = clean_rows()
        yahoo = yahoo_for(rows)
        yahoo["AAA"].loc["2024-01-04", "close"] = 10.50
        cross = check(report_for(rows, yahoo=yahoo), "cross_source")
        self.assertEqual(cross["status"], "exception")
        self.assertEqual(cross["count"], 1)
        self.assertAlmostEqual(cross["stats"]["max_abs_diff"], 0.30)
        self.assertEqual(cross["stats"]["by_symbol"]["AAA"]["breaches"], 1)
        self.assertIn("AAA 1/4", cross["detail"])

    def test_cross_source_without_snapshot_is_blocked(self):
        report = report_for(clean_rows(), yahoo=None)
        self.assertEqual(check(report, "cross_source")["status"], "blocked")
        self.assertEqual(report["status"], "pass-with-exceptions")

    def test_gap_without_action_is_exception(self):
        rows = clean_rows()
        rows[3].update(o="5.00", h="5.25", l="4.95", c="5.10")
        gaps = check(report_for(rows, yahoo=None), "gaps")
        self.assertEqual(gaps["status"], "exception")
        self.assertEqual(gaps["items"][0]["session"], "2024-01-05")

    def test_zero_volume_is_exception_not_failure(self):
        rows = clean_rows()
        rows[1]["v"] = "0"
        report = report_for(rows)
        self.assertEqual(check(report, "non_positive")["status"], "pass")
        self.assertEqual(check(report, "zero_volume")["status"], "exception")
        self.assertEqual(report["status"], "pass-with-exceptions")

    def test_source_row_failures(self):
        rows = clean_rows()
        norm = normalise(rows, NO_ACTIONS, ("AAA",))
        bad = rows + [dict(rows[0])]
        bad[1] = dict(bad[1], h="9.00")
        bad[2] = dict(bad[2], c="nan")
        report = q.build_report("ds", bad, norm, None, ())
        for name in ("duplicates", "ohlc", "non_finite"):
            self.assertEqual(check(report, name)["status"], "fail", name)
        self.assertEqual(report["status"], "fail")

    def test_half_days_listed_and_pass(self):
        rows = [dict(clean_rows()[0], session=d) for d in ("2023-11-24", "2023-11-27")]
        half = check(report_for(rows, yahoo=None), "half_days")
        self.assertEqual(half["status"], "pass")
        self.assertEqual([i["session"] for i in half["items"]], ["2023-11-24"])

    def test_report_folder_is_never_overwritten(self):
        report = report_for(clean_rows())
        with tempfile.TemporaryDirectory() as tmp:
            folder = q.write_report(Path(tmp), report)
            self.assertTrue((folder / "report.json").is_file())
            self.assertTrue((folder / "report.md").is_file())
            self.assertEqual(folder.name, "20260101T000000Z")
            with self.assertRaises(FileExistsError):
                q.write_report(Path(tmp), report)

    def test_markdown_lists_every_exception(self):
        report = fixture_report()
        text = q.render_report(report)
        for c in report["checks"]:
            if c["status"] != "pass":
                self.assertIn(f"## {c['name']}", text)
                for item in c["items"]:
                    self.assertIn(str(item), text)
        self.assertIn("pass-with-exceptions", text)

    def test_items_are_capped(self):
        names = tuple(f"S{i}" for i in range(20))
        many = [dict(r, symbol=n, v="0") for n in names for r in clean_rows()]
        norm = normalise(many, NO_ACTIONS, names)
        zero = check(q.build_report("ds", many, norm, None, ()), "zero_volume")
        self.assertEqual(zero["count"], 80)
        self.assertEqual(len(zero["items"]), 50)


class QualityCommandTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.root = Path(self._t.name)
        spec = importlib.util.spec_from_file_location(
            "data_cli", Path(__file__).resolve().parents[2] / "scripts" / "data.py")
        self.cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.cli)

    def make(self, rows):
        (self.root / "normalized").mkdir()
        bars, actions = self.root / "normalized" / "b.json", self.root / "normalized" / "a.json"
        bars.write_text(json.dumps(rows))
        actions.write_text(json.dumps(NO_ACTIONS))
        write_manifest(self.root, {
            "schema": "dataset-manifest/v1", "dataset_id": "ds-n1", "kind": "normalised",
            "created_utc": "2026-01-01T00:00:00Z", "source": "fixture",
            "inputs": [{"path": "normalized/b.json", "sha256": sha256_file(bars)},
                       {"path": "normalized/a.json", "sha256": sha256_file(actions)}],
            "recipe": RECIPE, "rights": {}, "files": [], "notes": ""})

    def run_cli(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = self.cli.main(["quality", "--dataset-id", "ds-n1", "--root", str(self.root)])
        return rc, out.getvalue(), err.getvalue()

    def reports(self):
        return sorted((self.root / "quality" / "ds-n1").glob("*/report.json"))

    def test_normalise_error_still_writes_a_fail_report(self):
        rows = clean_rows()
        rows[1]["c"] = "0.001"  # rounds to a non-positive cent price
        self.make(rows)
        rc, out, err = self.run_cli()
        self.assertEqual(rc, 1)
        self.assertIn("fail", out + err)
        (path,) = self.reports()
        report = json.loads(path.read_text())
        self.assertEqual(report["status"], "fail")
        norm = check(report, "normalise")
        self.assertEqual(norm["status"], "fail")
        self.assertIn("non-positive", norm["items"][0]["error"])
        self.assertEqual(report["inputs"]["manifest_sha256"],
                         sha256_file(self.root / "manifests" / "ds-n1.json"))

    def test_clean_dataset_report_records_inputs_and_commit(self):
        self.make(clean_rows())
        rc, _, err = self.run_cli()
        self.assertEqual(rc, 0, err)
        (path,) = self.reports()
        report = json.loads(path.read_text())
        self.assertEqual(report["inputs"]["manifest_sha256"],
                         sha256_file(self.root / "manifests" / "ds-n1.json"))
        self.assertIsNone(report["inputs"]["yahoo_snapshot_id"])
        self.assertTrue(report["code_commit"])


if __name__ == "__main__":
    unittest.main()
