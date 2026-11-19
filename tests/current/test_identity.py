"""Instrument identity: ids, dated symbols, ticker changes, coverage and the resolved cross-check."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from research.data import identity
from research.data.identity import (build_identity, coverage, cross_check_resolved, current_id, intervals_for_dataset,
                                    resolve, write_coverage, write_identity, derive_renames)

ARCHIVE = {"dataset_id": "arch", "universe": {"equities": [
    {"symbol": "META", "name": "META PLATFORMS", "issuer_identifier": "30303M102", "currency": "USD"},
    {"symbol": "AAPL", "name": "APPLE INC", "issuer_identifier": "037833100", "currency": "USD"},
    {"symbol": "BRK.B", "name": "BERKSHIRE", "issuer_identifier": "084670702", "currency": "USD"},
    {"symbol": "NEWCO", "name": "NEW CO", "issuer_identifier": "111111111", "currency": "USD"}]}}

MEMBERSHIP = {"schema": "membership/v1", "membership_id": "m1", "intervals": {
    "FB": [{"start": "2013-12-23", "end": "2022-06-08"}],
    "META": [{"start": "2022-06-09", "end": None}],
    "AAPL": [{"start": "2000-01-03", "end": None}],
    "BRK.B": [{"start": "2010-02-16", "end": None}],
    "OLDCO-201905": [{"start": "2016-01-04", "end": "2019-04-30"}],
    "GONE": [{"start": "2016-01-04", "end": "2018-03-14"}],
    "NEWCO": [{"start": "2018-03-15", "end": None}]}}

CHANGES = [{"old": "FB", "new": "META", "date": "2022-06-09", "source_url": "https://example.test/meta",
            "verified": False}]


def built(changes=CHANGES):
    return build_identity(ARCHIVE, MEMBERSHIP, copy.deepcopy(changes))


class IdentityTests(unittest.TestCase):
    def test_fb_meta_one_identity(self):
        ident = built()
        self.assertEqual(resolve(ident, "FB", "2020-01-02"), "30303M102")
        self.assertEqual(resolve(ident, "META", "2023-01-03"), "30303M102")
        self.assertEqual(ident["instruments"]["30303M102"]["symbols"], ["FB", "META"])
        self.assertNotIn("sym:FB", ident["instruments"])
        self.assertEqual(ident["ticker_changes"]["applied"][0]["old"], "FB")
        self.assertEqual(ident["unresolved_candidates"] and [c["old"] for c in ident["unresolved_candidates"]], ["GONE"])

    def test_without_the_change_fb_is_its_own_instrument(self):
        ident = built([])
        self.assertEqual(resolve(ident, "FB", "2020-01-02"), "sym:FB")
        self.assertNotEqual(resolve(ident, "FB", "2020-01-02"), resolve(ident, "META", "2023-01-03"))

    def test_resolve_by_date(self):
        ident = built()
        self.assertIsNone(resolve(ident, "META", "2022-06-08"))
        self.assertIsNone(resolve(ident, "FB", "2022-06-09"))
        self.assertEqual(resolve(ident, "FB", "2022-06-08"), "30303M102")
        self.assertEqual(resolve(ident, "META", "2022-06-09"), "30303M102")
        self.assertIsNone(resolve(ident, "NOSUCH", "2020-01-02"))
        self.assertEqual(resolve(ident, "aapl", "1999-01-01"), "037833100")

    def test_ids_historical_current_and_alias(self):
        ident = built()
        counts = ident["counts"]
        self.assertEqual((counts["current_ids"], counts["historical_only_ids"]), (4, 2))
        self.assertEqual(resolve(ident, "GONE", "2017-01-03"), "sym:GONE")
        self.assertEqual(resolve(ident, "NEWCO", "2018-03-15"), "111111111")
        self.assertEqual(resolve(ident, "OLDCO-201905", "2017-01-03"), "sym:OLDCO")
        self.assertEqual(ident["instruments"]["sym:OLDCO"]["aliases"], ["OLDCO-201905"])
        self.assertEqual(resolve(ident, "OLDCO", "2017-01-03"), "sym:OLDCO")  # normalised fallback
        self.assertEqual(resolve(ident, "BRK-B", "2017-01-03"), "084670702")  # class-share separator
        self.assertEqual(counts["aliases"], 2)  # the suffixed raw string and the renamed FB

    def test_unresolved_candidates_are_listed_not_applied(self):
        ident = built()
        pair = ident["unresolved_candidates"][0]
        self.assertEqual((pair["old"], pair["new"]), ("GONE", "NEWCO"))
        self.assertNotEqual(resolve(ident, "GONE", "2017-01-03"), resolve(ident, "NEWCO", "2018-03-15"))

    def test_every_ticker_change_needs_a_cited_source(self):
        for bad in ({"old": "A", "new": "B", "date": "2020-01-01"},
                    {"old": "A", "new": "B", "date": "2020-01-01", "source_url": None},
                    {"old": "A", "new": "B", "date": "2020-01-01", "source_url": None, "verified": False},
                    {"old": "A", "new": "B", "date": "2020-01-01", "source_url": "not a url"}):
            with self.assertRaises(ValueError):
                build_identity(ARCHIVE, MEMBERSHIP, [bad])
        ok = {"old": "FB", "new": "META", "date": "2022-06-09", "source_url": None, "verified": False,
              "source_note": "plain statement"}
        self.assertEqual(len(built([ok])["ticker_changes"]["applied"]), 1)

    def test_unknown_symbols_in_a_change_are_unapplied(self):
        ident = built([{"old": "NOPE", "new": "META", "date": "2022-06-09", "source_url": "https://example.test/x"}])
        self.assertEqual(len(ident["ticker_changes"]["unapplied"]), 1)
        self.assertEqual(resolve(ident, "FB", "2022-06-09"), "sym:FB")  # unchanged: still its own instrument
        self.assertEqual(resolve(ident, "FB", "2020-01-02"), "sym:FB")

    def test_committed_ticker_changes_are_valid_and_start_with_fb_meta(self):
        changes = identity.load_ticker_changes(Path(identity.__file__).resolve().parents[1] / "registry/ticker-changes.json")
        self.assertEqual((changes[0]["old"], changes[0]["new"], changes[0]["date"]), ("FB", "META", "2022-06-09"))

    def test_derived_rename_records_are_unverified_and_cite_the_membership(self):
        ident = built()
        records = derive_renames(ident, MEMBERSHIP, ["META", "AAPL", "NEWCO", "BRK.B"])
        self.assertEqual(records, [{
            "old": "GONE", "new": "NEWCO", "date": "2018-03-15", "source_url": None, "verified": False,
            "source_note": "derived from adjacent membership intervals in m1 (fja05680 file); "
                           "not independently verified"}])
        identity.check_ticker_changes(records)  # the loader accepts exactly this form
        applied = build_identity(ARCHIVE, MEMBERSHIP, copy.deepcopy(CHANGES) + records)
        self.assertEqual(resolve(applied, "GONE", "2017-01-03"), resolve(applied, "NEWCO", "2018-03-15"))
        self.assertEqual(applied["unresolved_candidates"], [])
        self.assertEqual(derive_renames(ident, MEMBERSHIP, ["META", "AAPL", "BRK.B"]), [])  # new not in dataset

    def test_derived_renames_skip_unsafe_candidates(self):
        base = {"inputs": {"membership_id": "m1"},
                "symbol_map": {"OLD": [{"id": "sym:OLD", "start": None, "end": None}],
                               "NEW": [{"id": "n", "start": None, "end": None}]}}

        def cand(last, first):
            return [{"old": "OLD", "new": "NEW", "old_last_member_day": last, "new_first_member_day": first}]
        ok = dict(base, unresolved_candidates=cand("2018-01-02", "2018-01-03"))
        member = {"intervals": {"OLD": [{"start": "2016-01-04", "end": "2018-01-02"}],
                                "NEW": [{"start": "2018-01-03", "end": None}]}}
        self.assertEqual(len(derive_renames(ok, member, ["NEW"])), 1)
        # gap longer than 7 days
        far = dict(base, unresolved_candidates=cand("2018-01-02", "2018-01-10"))
        late = {"intervals": {"OLD": [{"start": "2016-01-04", "end": "2018-01-02"}],
                              "NEW": [{"start": "2018-01-10", "end": None}]}}
        self.assertEqual(derive_renames(far, late, ["NEW"]), [])
        self.assertEqual(len(derive_renames(far, late, ["NEW"], max_gap_days=8)), 1)
        # old symbol is itself a current archive instrument: two companies, not merged
        both = dict(ok, symbol_map=dict(ok["symbol_map"], OLD=[{"id": "cur-id2", "start": None, "end": None}]))
        self.assertEqual(derive_renames(both, member, ["NEW"]), [])
        # the new symbol was a member before: its first start is not the candidate's
        earlier = {"intervals": {"OLD": [{"start": "2016-01-04", "end": "2018-01-02"}],
                                 "NEW": [{"start": "2010-01-04", "end": "2012-01-02"},
                                         {"start": "2018-01-03", "end": None}]}}
        self.assertEqual(derive_renames(ok, earlier, ["NEW"]), [])
        # the old symbol returns later: not a clean rename
        back = {"intervals": {"OLD": [{"start": "2016-01-04", "end": "2018-01-02"},
                                      {"start": "2020-01-02", "end": None}],
                              "NEW": [{"start": "2018-01-03", "end": None}]}}
        self.assertEqual(derive_renames(ok, back, ["NEW"]), [])

    def test_derived_renames_need_a_second_source_and_unambiguous_symbols(self):
        symbol_map = {s: [{"id": f"sym:{s}", "start": None, "end": None}] for s in ("OLD", "X")}
        symbol_map["NEW"] = [{"id": "n", "start": None, "end": None}]

        def cand(old, new, last, first):
            return {"old": old, "new": new, "old_last_member_day": last, "new_first_member_day": first}
        ident = {"inputs": {"membership_id": "m1"}, "symbol_map": symbol_map,
                 "unresolved_candidates": [cand("OLD", "NEW", "2018-01-02", "2018-01-03")]}
        member = {"intervals": {"OLD": [{"start": "2016-01-04", "end": "2018-01-02"}],
                                "NEW": [{"start": "2018-01-03", "end": None}]}}
        # a genuine addition (second source dates it on the same day) is not a rename
        self.assertEqual(derive_renames(ident, member, ["NEW"], added_dates={"NEW": "2018-01-03"}), [])
        self.assertEqual(derive_renames(ident, member, ["NEW"], added_dates={}), [])
        found = derive_renames(ident, member, ["NEW"], added_dates={"NEW": "1999-05-01"})
        self.assertEqual([(r["old"], r["new"]) for r in found], [("OLD", "NEW")])
        self.assertIn("1999-05-01", found[0]["corroboration"])
        self.assertEqual(found[0]["source_note"], "derived from adjacent membership intervals in m1 (fja05680 "
                         "file); not independently verified")
        # window filter
        self.assertEqual(derive_renames(ident, member, ["NEW"], since="2019-01-01"), [])
        self.assertEqual(len(derive_renames(ident, member, ["NEW"], since="2018-01-01")), 1)
        # already in the registry on the same side
        self.assertEqual(derive_renames(ident, member, ["NEW"], existing=[{"old": "Z", "new": "NEW"}]), [])
        # two candidates share the new symbol: ambiguous, none is applied
        both = dict(ident, unresolved_candidates=ident["unresolved_candidates"]
                    + [cand("X", "NEW", "2018-01-02", "2018-01-03")])
        self.assertEqual(derive_renames(both, member, ["NEW"]), [])
        # a chain (X -> OLD earlier, OLD -> NEW later) is not ambiguous
        chain = dict(ident, unresolved_candidates=[cand("X", "OLD", "2015-12-30", "2015-12-31")]
                     + ident["unresolved_candidates"])
        self.assertEqual([r["old"] for r in derive_renames(chain, member, ["NEW"])], ["OLD"])

    def test_coverage_lists_late_or_never_member_dataset_symbols(self):
        ident = built()
        sessions = ["2016-01-04", "2018-03-15"]
        cov = coverage(MEMBERSHIP, ident, ["META", "AAPL", "NEWCO", "BRK.B"], sessions)
        self.assertEqual(cov["late_or_never_member_dataset_symbols"],
                         [{"symbol": "NEWCO", "first_member_day": "2018-03-15", "candidate_old": "GONE"}])
        renamed = build_identity(ARCHIVE, MEMBERSHIP, copy.deepcopy(CHANGES) + derive_renames(
            ident, MEMBERSHIP, ["NEWCO"]))
        self.assertEqual(coverage(MEMBERSHIP, renamed, ["META", "NEWCO"], sessions)[
                             "late_or_never_member_dataset_symbols"], [])

    def test_coverage_per_date(self):
        ident = built()
        sessions = ["2016-01-04", "2018-03-14", "2018-03-15", "2022-06-08", "2022-06-09"]
        cov = coverage(MEMBERSHIP, ident, ["META", "AAPL", "NEWCO", "BRK.B"], sessions)
        per = cov["per_date"]
        # 2016-01-04: FB (=META id), AAPL, BRK.B, OLDCO, GONE; data for FB/META, AAPL, BRK.B
        self.assertEqual(per["2016-01-04"], {"in_index": 5, "with_data": 3, "share": 3 / 5})
        self.assertEqual(per["2018-03-14"]["in_index"], 5)
        self.assertEqual(per["2018-03-15"]["in_index"], 5)  # NEWCO in, GONE out
        self.assertEqual(per["2018-03-15"]["with_data"], 4)
        # the rename does not double count nor lose the instrument on either side of the change
        self.assertEqual(per["2022-06-08"]["with_data"], per["2022-06-09"]["with_data"] + 0)
        self.assertEqual(per["2022-06-09"], {"in_index": 4, "with_data": 4, "share": 1.0})
        summary = cov["summary"]
        self.assertAlmostEqual(summary["min_share"], 3 / 5)
        self.assertEqual(summary["worst_dates"][0]["date"], "2016-01-04")
        self.assertAlmostEqual(summary["median_share"], sorted(p["share"] for p in per.values())[2])

    def test_intervals_for_dataset_fold_aliases_into_the_dataset_symbol(self):
        ident = built()
        spans = intervals_for_dataset(MEMBERSHIP, ident, ["META", "AAPL"])
        self.assertEqual(spans["META"], [{"start": "2013-12-23", "end": None}])
        self.assertNotIn("FB", spans)
        self.assertEqual(set(spans), {"META", "AAPL"})

    def test_intervals_for_dataset_fails_loudly_on_an_unresolvable_span(self):
        broken = copy.deepcopy(MEMBERSHIP)
        broken["intervals"]["META"] = [{"start": "2021-01-04", "end": None}]  # before the META symbol exists
        with self.assertRaises(ValueError) as caught:
            intervals_for_dataset(broken, built(), ["META"])
        self.assertIn("META", str(caught.exception))
        self.assertIn("2021-01-04", str(caught.exception))
        # consistent data does not raise
        intervals_for_dataset(MEMBERSHIP, built(), ["AAPL"])

    def test_coverage_notes_state_the_full_window_assumption(self):
        self.assertIn("full-window", coverage(MEMBERSHIP, built(), ["AAPL"], ["2020-01-02"])["notes"])

    def test_cross_check_resolved_removes_a_rename_difference(self):
        ident = built()
        # the other source calls the company META throughout; this table lists FB until 2022-06-08
        other = {"2020-01-02": {"META", "AAPL", "BRK.B", "NEWCO"},"2023-01-03": {"META", "AAPL", "BRK.B", "NEWCO"}}
        plain = cross_check_resolved(MEMBERSHIP, built([]), other)
        resolved = cross_check_resolved(MEMBERSHIP, ident, other)
        self.assertEqual((plain["2020-01-02"]["only_primary_count"], plain["2020-01-02"]["only_other_count"]), (1, 1))
        self.assertEqual((resolved["2020-01-02"]["only_primary_count"], resolved["2020-01-02"]["only_other_count"]),
                         (0, 0))
        self.assertEqual(resolved["2023-01-03"]["only_other_count"], 0)
        # real differences stay: a member the other source lacks, and a name this table lacks
        diff = cross_check_resolved(MEMBERSHIP, ident, {"2023-01-03": {"META", "AAPL", "BRK.B", "ZZZ"}})
        self.assertEqual((diff["2023-01-03"]["only_primary"], diff["2023-01-03"]["only_other"]),
                         (["111111111"], ["ZZZ"]))

    def test_cross_check_resolved_one_sided(self):
        ident = built()
        result = cross_check_resolved(MEMBERSHIP, ident, {}, one_sided={"2020-01-02": ["META", "AAPL", "MISSING"]})
        self.assertEqual(result["2020-01-02"]["only_other"], ["MISSING"])
        self.assertTrue(result["2020-01-02"]["one_sided"])

    def test_writers_use_exclusive_create(self):
        ident = built()
        ident.update(identity_id="id1", created_utc="2026-11-18T00:00:00Z")
        with tempfile.TemporaryDirectory() as tmp:
            path = write_identity(tmp, ident)
            self.assertEqual(path, Path(tmp) / "identity/id1.json")
            self.assertEqual(json.loads(path.read_text())["schema"], "instrument-identity/v1")
            with self.assertRaises(FileExistsError):
                write_identity(tmp, ident)
            self.assertEqual(identity.read_identity(tmp, "id1")["identity_id"], "id1")
            cov = coverage(MEMBERSHIP, ident, ["META"], ["2020-01-02"])
            write_coverage(tmp, cov, "cov1")
            with self.assertRaises(FileExistsError):
                write_coverage(tmp, cov, "cov1")

    def test_current_id_of_a_dataset_symbol_ignores_the_date(self):
        self.assertEqual(current_id(built(), "META"), "30303M102")
        self.assertIsNone(current_id(built(), "NOSUCH"))


class IdentityCommandTests(unittest.TestCase):
    def test_identity_command_writes_once_and_reports_blocked_cross_checks(self):
        from scripts import data as data_cli
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "manifests").mkdir()
            (root / "manifests/arch.json").write_text(json.dumps(ARCHIVE))
            (root / "membership").mkdir()
            membership = {**MEMBERSHIP, "cross_checks": []}
            (root / "membership/m1.json").write_text(json.dumps(membership))
            changes = root / "changes.json"
            changes.write_text(json.dumps(CHANGES))
            argv = ["identity", "--root", str(root), "--archive", "arch", "--membership-id", "m1",
                    "--identity-id", "id1", "--ticker-changes", str(changes)]
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(data_cli.main(argv), 0)
            doc = json.loads((root / "identity/id1.json").read_text())
            self.assertEqual(doc["counts"]["current_ids"], 4)
            self.assertEqual(doc["cross_checks"][0]["status"], "blocked")
            self.assertIn("4 current ids, 2 historical-only ids, 2 aliases", out.getvalue())
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(data_cli.main(argv), 1)
            self.assertIn("refusing to overwrite", err.getvalue())

    def test_derive_renames_command_lists_and_appends_only_new_records(self):
        from scripts import data as data_cli
        from tests.current.test_stock_dataset import ID, NAMES, make_root
        archive = {"dataset_id": "arch", "universe": {"equities": [
            {"symbol": s, "name": s, "issuer_identifier": f"id-{s}", "currency": "USD"} for s in NAMES]}}
        membership = {"schema": "membership/v1", "membership_id": "m9", "intervals": {
            "AAA": [{"start": "2016-01-04", "end": None}], "PAR": [{"start": "2016-01-04", "end": None}],
            "OLDKID": [{"start": "2016-01-04", "end": "2019-01-31"}], "KID": [{"start": "2019-02-01", "end": None}]}}
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            ident = build_identity(archive, membership, [])
            ident.update(identity_id="id9", created_utc="2026-11-18T00:00:00Z")
            write_identity(root, ident)
            (root / "membership").mkdir()
            (root / "membership/m9.json").write_text(json.dumps(membership))
            changes = root / "changes.json"
            changes.write_text(json.dumps(CHANGES))
            argv = ["derive-renames", "--root", str(root), "--identity-id", "id9", "--dataset-id", ID,
                    "--ticker-changes", str(changes)]
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(data_cli.main(argv), 0)
            self.assertIn("OLDKID -> KID on 2019-02-01", out.getvalue())
            self.assertEqual(len(json.loads(changes.read_text())), 1)  # dry run writes nothing
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(data_cli.main(argv + ["--write"]), 0)
                self.assertEqual(data_cli.main(argv + ["--write"]), 0)  # idempotent
            written = json.loads(changes.read_text())
            self.assertEqual([(c["old"], c["new"], c["verified"], c["source_url"]) for c in written],
                             [("FB", "META", False, "https://example.test/meta"),
                              ("OLDKID", "KID", False, None)])
            identity.check_ticker_changes(written)


if __name__ == "__main__":
    unittest.main()
