import json
import tempfile
import unittest
from pathlib import Path

from datetime import datetime, timezone

from research.data import github_snapshot as g
from research.data import manifest as m
from research.data import membership as ms

SAMPLE = (Path(__file__).resolve().parents[1] / "fixtures" / "data" / "sp500-components-sample.csv").read_text()


class MembershipTests(unittest.TestCase):
    def test_intervals_from_sample_csv(self):
        iv = ms.parse_components(SAMPLE)
        self.assertEqual(iv["AAA"], [{"start": "2016-01-04", "end": None}])
        self.assertEqual(iv["BBB"], [{"start": "2016-01-04", "end": "2019-01-31"}])
        # removed 2017-03-01 (last member day 2017-02-28), re-added 2018-06-11
        self.assertEqual(iv["CCC"], [{"start": "2016-01-04", "end": "2017-02-28"},
                                     {"start": "2018-06-11", "end": None}])
        self.assertEqual(iv["DDD"], [{"start": "2017-03-01", "end": None}])
        self.assertEqual(iv["FB"], [{"start": "2016-01-04", "end": "2022-06-08"}])
        self.assertEqual(iv["META"], [{"start": "2022-06-09", "end": None}])

    def test_membership_on_is_point_in_time(self):
        iv = ms.parse_components(SAMPLE)
        self.assertEqual(ms.membership_on(iv, "2016-01-04"), {"AAA", "BBB", "CCC", "FB"})
        self.assertEqual(ms.membership_on(iv, "2017-02-28"), {"AAA", "BBB", "CCC", "FB"})
        self.assertEqual(ms.membership_on(iv, "2017-03-01"), {"AAA", "BBB", "DDD", "FB"})
        self.assertEqual(ms.membership_on(iv, "2019-01-31"), {"AAA", "BBB", "CCC", "DDD", "FB"})
        self.assertEqual(ms.membership_on(iv, "2019-02-01"), {"AAA", "CCC", "DDD", "FB"})
        self.assertEqual(ms.membership_on(iv, "2015-12-31"), set())  # before the first row: nobody
        self.assertEqual(ms.membership_on(iv, "2022-06-08"), {"AAA", "CCC", "DDD", "FB"})
        self.assertEqual(ms.membership_on(iv, "2022-06-09"), {"AAA", "CCC", "DDD", "META"})

    def test_cross_check_lists_disagreements(self):
        iv = ms.parse_components(SAMPLE)
        other = {"2016-01-04": {"AAA", "BBB", "CCC", "FB"},
                 "2017-03-01": {"AAA", "BBB", "ZZZ"}}
        result = ms.cross_check(iv, other, cap=1)
        self.assertEqual(result["2016-01-04"]["only_primary"], [])
        self.assertEqual(result["2016-01-04"]["only_other"], [])
        row = result["2017-03-01"]
        self.assertEqual((row["n_primary"], row["n_other"]), (4, 3))
        self.assertEqual(row["only_primary"], ["DDD"])  # capped at 1
        self.assertEqual(row["only_primary_count"], 2)
        self.assertEqual(row["only_other"], ["ZZZ"])

    def test_spot_checks_report_findings_without_tuning(self):
        iv = ms.parse_components(SAMPLE)
        checks = {c["name"]: c for c in ms.spot_checks(iv)}
        self.assertEqual(checks["TSLA member from 2020-12-21"]["result"], "mismatch")  # absent in sample
        self.assertEqual(checks["AAPL member throughout 2016-01-04..2025-12-31"]["result"], "mismatch")
        fb = checks["FB/META ticker change 2022-06-09"]
        self.assertEqual(fb["observed"], {"FB_on_2022-06-08": True, "META_on_2022-06-09": True,
                                          "FB_on_2022-06-09": False, "META_on_2022-06-08": False})
        self.assertEqual(fb["result"], "pass")
        self.assertEqual(checks["members on 2016-01-04"]["observed"], 4)
        self.assertEqual(checks["members on 2025-12-31"]["observed"], 4)

    def test_write_membership_exclusive_with_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = {"schema": ms.SCHEMA, "membership_id": "mem1", "created_utc": "2026-11-18T12:00:00Z",
                   "source": {"repo": "a/b", "commit_or_file_sha": "x", "file": "f.csv", "sha256": "0" * 64},
                   "intervals": ms.parse_components(SAMPLE), "cross_checks": [], "spot_checks": [], "notes": "n"}
            path = ms.write_membership(root, doc)
            self.assertEqual(path, root / "membership" / "mem1.json")
            self.assertEqual(json.loads(path.read_text())["intervals"]["AAA"], [{"start": "2016-01-04", "end": None}])
            with self.assertRaises(FileExistsError):
                ms.write_membership(root, doc)
            with self.assertRaises(m.ManifestError):
                ms.write_membership(root, dict(doc, membership_id="../x"))
            with self.assertRaises(m.ManifestError):
                ms.write_membership(root, dict(doc, membership_id="m2", schema="other/v1"))

    def test_load_membership_roundtrip_and_malformed_csv(self):
        with self.assertRaises(ValueError):
            ms.parse_components("date,tickers\n2016-01-04,A\n2016-01-04,B\n")  # duplicate date
        with self.assertRaises(ValueError):
            ms.parse_components("when,what\n2016-01-04,A\n")

    def test_build_from_snapshot_blocks_missing_sources_and_writes_manifest(self):
        class Resp:
            status = 200

            def __init__(self, body):
                self.body = body

            def read(self):
                return self.body

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        routes = {"https://raw.githubusercontent.com/f/s/master/c.csv": SAMPLE.encode(),
                  "https://raw.githubusercontent.com/f/s/master/LICENSE": b"MIT License\n\nx\n"}
        now = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            g.fetch_urls({"fja05680-components.csv": "https://raw.githubusercontent.com/f/s/master/c.csv",
                          "fja05680-LICENSE": "https://raw.githubusercontent.com/f/s/master/LICENSE"},
                         "snap", root, opener=lambda req, timeout=None: Resp(routes[req.full_url]), now=now)
            doc, inputs, rights = ms.build_from_snapshot(root, ["snap"], "mem1", now=now)
            self.assertEqual([c["status"] for c in doc["cross_checks"]], ["blocked", "blocked"])
            self.assertEqual(doc["source"]["sha256"], inputs[0]["sha256"])
            self.assertEqual(len(doc["source"]["commit_or_file_sha"]), 40)
            self.assertEqual(rights["licences"]["fja05680-LICENSE"]["first_line"], "MIT License")
            path = ms.write_membership(root, doc)
            m.write_manifest(root, ms.membership_manifest(root, doc, path, inputs, rights))
            manifest = m.read_manifest(root, "mem1")
            self.assertEqual(manifest["files"][0]["path"], "membership/mem1.json")
            self.assertEqual(len(manifest["inputs"]), 2)
            self.assertIn("fja05680-components.csv from snapshot snap", manifest["notes"])
            self.assertIn("fja05680-LICENSE from snapshot snap", manifest["notes"])

    def test_other_source_parsers_and_first_trading_days(self):
        as_of, added = ms.parse_current_list("symbol,date added,date\nAAA,2000-01-01,2025-08-23\nZZZ,,2025-08-23\n")
        self.assertEqual((as_of, added), ("2025-08-23", {"AAA": "2000-01-01", "ZZZ": None}))
        iv = ms.parse_opt_in_out("\ufeffsymbol,name,opt-in,opt-out\nAAA,a,2000-01-01,\nBBB,b,2000-01-01,2017-03-01\n")
        self.assertEqual(iv["BBB"], [{"start": "2000-01-01", "end": "2017-02-28"}])
        self.assertEqual(ms.first_trading_days(2016, 2017), ["2016-01-04", "2017-01-03"])
        self.assertEqual(ms.norm("BRK-B"), ms.norm("brk.b"))
        self.assertEqual(ms.norm("AAL-199702"), "AAL")


if __name__ == "__main__":
    unittest.main()
