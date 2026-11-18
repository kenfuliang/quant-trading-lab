import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from research.evaluation import data_quality as q
from research.evaluation.etf_normalise import normalise

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


def report_for(rows, actions=NO_ACTIONS, yahoo="same", names=("AAA",)):
    norm = normalise(rows, actions, names)
    if isinstance(yahoo, str):
        yahoo = yahoo_for([r for r in rows if r["symbol"] == "AAA"])
    return q.build_report("ds", rows, norm, yahoo, norm.data.splits, created_utc="2026-01-01T00:00:00Z")


def check(report, name):
    return next(c for c in report["checks"] if c["name"] == name)


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
        cross = check(report_for(rows, actions, yahoo), "cross_source")
        self.assertEqual(cross["status"], "pass", cross)
        self.assertEqual(cross["stats"]["compared"], 4)
        self.assertEqual(cross["stats"]["breaches"], 0)

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


if __name__ == "__main__":
    unittest.main()
