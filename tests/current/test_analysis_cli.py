"""Offline tests of scripts/analysis.py: run, DSR trial counts and the golden summary."""
import contextlib
import io
import json
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from research.control import experiment_registry as registry
from research.data.root import DataAbsent
from research.evaluation.datasets import DatasetBlocked
from research.evaluation.parity_fixture import synthetic_fixture
from scripts import analysis

SPEC = Path(analysis.ROOT) / "research/registry/analysis-specs/fixture-ladder.json"


def record(record_id, code, sharpe):
    return {"schema": registry.SCHEMA, "record_id": record_id, "logged_at": "2026-11-18T00:00:00+00:00",
            "name": record_id, "context": {"code": code, "period": "2005-2025", "costs_bp": 5.0},
            "evidence_class": "development", "disposition": "control", "lesson": "test", "imported": True,
            "metrics": {"sharpe": sharpe, "net_cagr": 0.1}}


class AnalysisCliTests(unittest.TestCase):
    def test_cli_run_on_fixture_spec_writes_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with mock.patch.dict(os.environ, {"QTL_DATA_ROOT": tmp}), contextlib.redirect_stdout(out):
                self.assertEqual(analysis.main(["run", "--spec", str(SPEC)]), 0)
            folder = Path(out.getvalue().strip())
            self.assertEqual(folder.parent, Path(tmp) / "analysis")
            doc = json.loads((folder / "analysis.json").read_text())
            self.assertEqual(doc["schema"], "analysis-output/v1")
            self.assertEqual([r["rung"] for r in doc["runs"]], ["buy_hold", "sma_trend", "sma_trend_costs"])
            self.assertEqual(doc["lookahead"]["status"], "pass")
            self.assertTrue(all(c["compared_signals"] > 0 for c in doc["lookahead"]["compared"]))
            self.assertIsNotNone(doc["trust"]["psr"]["value"])
            self.assertIsNone(doc["trust"]["dsr"]["value"])  # no comparison record: trial count undefined
            self.assertIsNone(doc["trust"]["pbo"]["value"])
            self.assertTrue((folder / "report.md").is_file())
            self.assertTrue((folder / "tearsheet.html").is_file())
            self.assertEqual(len(list((Path(tmp) / "runs").iterdir())), 3)

    def test_run_with_comparison_and_grid(self):
        spec = json.loads(SPEC.read_text())
        spec["comparison"] = {"record_ids": ["c-1", "missing-id"]}
        spec["pbo_grid"] = [{"name": "sma_trend", "window": w, "gross": 0.95} for w in (5, 10, 20, 40)]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reg.jsonl"
            for rec in (record("c-1", "C01-5bp", 1.0), record("c-2", "C01-5bp", 0.5), record("c-3", "C01-5bp", 0.8),
                        record("o-1", "OTHER", 9.0)):
                registry.append(path, rec)
            doc = analysis.run_spec(spec, Path(tmp), path)["doc"]
        self.assertEqual(doc["trust"]["dsr"]["n_trials"], 3)
        self.assertEqual(doc["comparison"]["missing"], ["missing-id"])
        self.assertEqual([r["record_id"] for r in doc["comparison"]["records"]], ["c-1"])
        self.assertIn("illustrative grid", " ".join(doc["notes"]))
        self.assertIn("value", doc["trust"]["pbo"])

    def _registry(self, tmp, records):
        path = Path(tmp) / "reg.jsonl"
        for rec in records:
            registry.append(path, rec)
        return path

    def test_dsr_records_its_inputs_and_period_note(self):
        spec = json.loads(SPEC.read_text())
        spec["comparison"] = {"record_ids": ["c-1"], "trial_code": "C01-5bp"}
        with tempfile.TemporaryDirectory() as tmp:
            path = self._registry(tmp, (record("c-1", "C01-5bp", 1.0), record("c-2", "C01-5bp", 0.5),
                                        record("c-3", "C01-5bp", 0.8), record("o-1", "OTHER", 9.0)))
            result = analysis.run_spec(spec, Path(tmp), path)
            report = (result["folder"] / "report.md").read_text()
        dsr = result["doc"]["trust"]["dsr"]
        self.assertEqual(dsr["code"], "C01-5bp")
        self.assertEqual(dsr["trial_record_ids"], ["c-1", "c-2", "c-3"])
        self.assertEqual(dsr["trial_sharpes"], [1.0, 0.5, 0.8])
        per = [s / math.sqrt(252) for s in (1.0, 0.5, 0.8)]
        mean = sum(per) / 3
        self.assertAlmostEqual(dsr["sr_variance"], sum((x - mean) ** 2 for x in per) / 2)
        sessions = synthetic_fixture().sessions
        self.assertEqual(dsr["period_note"], f"trial Sharpes are 2005-2025 registry results applied to a "
                                             f"{sessions[0]}–{sessions[-1]} series")
        for text in ("sr_variance", "c-1, c-2, c-3", "2005-2025 registry results", "warm-up"):
            self.assertIn(text, report)

    def test_trial_code_fixes_dsr_regardless_of_record_order(self):
        spec = json.loads(SPEC.read_text())
        regs = (record("c-1", "C01-5bp", 1.0), record("c-2", "C01-5bp", 0.5), record("o-1", "OTHER", 9.0),
                record("o-2", "OTHER", 2.0))
        with tempfile.TemporaryDirectory() as tmp:
            path = self._registry(tmp, regs)
            spec["comparison"] = {"record_ids": ["o-1", "c-1"], "trial_code": "C01-5bp"}
            explicit = analysis.run_spec(spec, Path(tmp) / "a", path)["doc"]
            spec["comparison"] = {"record_ids": ["o-1", "c-1"]}
            fallback = analysis.run_spec(spec, Path(tmp) / "b", path)["doc"]
        self.assertEqual(explicit["trust"]["dsr"]["code"], "C01-5bp")
        self.assertEqual(fallback["trust"]["dsr"]["code"], "OTHER")
        self.assertTrue(any("trial_code" in note and "OTHER" in note for note in fallback["notes"]))
        self.assertFalse(any("trial_code" in note for note in explicit["notes"]))

    def test_warmup_sessions_are_counted_and_noted(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = analysis.run_spec(json.loads(SPEC.read_text()), Path(tmp))["doc"]
            run_dir = Path(tmp) / "runs" / doc["runs"][-1]["run_id"]
            from research.evaluation.run_output import read_run
            _, tables = read_run(run_dir)
        held = set(tables["positions"]["date"])
        expected = 0
        for day, net in zip(tables["returns"]["date"], tables["returns"]["net_return"]):
            if net != 0 or day in held:
                break
            expected += 1
        self.assertGreater(expected, 0)
        for name in ("psr", "dsr"):
            self.assertEqual(doc["trust"][name]["warmup_sessions"], expected)
            self.assertIn("inflates n", doc["trust"][name]["warmup_note"])

    def test_dsr_counts_registry_records_by_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reg.jsonl"
            for rec in (record("a-1", "C01-5bp", 1.0), record("a-2", "C01-5bp", 0.5), record("a-3", "C01-5bp", 0.8),
                        record("b-1", "U1-25bp", 3.0)):
                registry.append(path, rec)
            n, variance = analysis.trial_stats(registry.load(path), "C01-5bp")
        self.assertEqual(n, 3)
        per = [s / math.sqrt(252) for s in (1.0, 0.5, 0.8)]
        mean = sum(per) / 3
        self.assertAlmostEqual(variance, sum((x - mean) ** 2 for x in per) / 2)
        self.assertEqual(analysis.trial_stats([], "C01-5bp"), (0, None))
        one = [record("a-1", "C01-5bp", 1.0)]
        self.assertEqual(analysis.trial_stats(one, "C01-5bp"), (1, None))

    def test_golden_detects_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "golden.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(analysis.main(["golden", "--update", "--file", str(target)]), 0)
                self.assertEqual(analysis.main(["golden", "--file", str(target)]), 0)
            data = json.loads(target.read_text())
            data["sma_trend"]["sharpe"] += 1e-11  # within abs_tol 1e-9: still passes
            target.write_text(json.dumps(data))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(analysis.main(["golden", "--file", str(target)]), 0)
            data["sma_trend"]["sharpe"] += 0.5
            target.write_text(json.dumps(data))
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(analysis.main(["golden", "--file", str(target)]), 1)
            self.assertIn(str(target), err.getvalue())

    def test_tearsheet_failure_is_visible(self):
        def boom(*args, **kwargs):
            raise RuntimeError("no chart")

        err = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(err):
            result = analysis.run_spec(json.loads(SPEC.read_text()), Path(tmp), tearsheet=boom)
            on_disk = json.loads((result["folder"] / "analysis.json").read_text())
            self.assertFalse((result["folder"] / "tearsheet.html").exists())
            self.assertIn("failed", (result["folder"] / "report.md").read_text())
        self.assertEqual(on_disk["tearsheet"], {"status": "failed", "error": "RuntimeError: no chart"})
        self.assertIn("tearsheet failed", err.getvalue())

    def test_tearsheet_status_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = analysis.run_spec(json.loads(SPEC.read_text()), Path(tmp))["doc"]
        self.assertEqual(doc["tearsheet"]["status"], "written")

    def test_dsr_reason_when_too_few_registry_sharpes(self):
        spec = json.loads(SPEC.read_text())
        spec["comparison"] = {"record_ids": ["c-1"]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reg.jsonl"
            registry.append(path, record("c-1", "C01-5bp", 1.0))
            doc = analysis.run_spec(spec, Path(tmp), path)["doc"]
        self.assertIsNone(doc["trust"]["dsr"]["value"])
        self.assertEqual(doc["trust"]["dsr"]["reason"], "fewer than 2 registry Sharpe values for context C01-5bp")
        self.assertEqual(doc["trust"]["dsr"]["n_trials"], 1)

    def test_real_dataset_path_records_provenance(self):
        spec = {**json.loads(SPEC.read_text()), "fixture": False, "dataset_id": "fake-ds"}
        calls = []

        def loader(dataset_id, instruments, root):
            calls.append((dataset_id, instruments))
            return synthetic_fixture(), {"manifest_sha256": "abc123", "quality_status": "pass"}

        with tempfile.TemporaryDirectory() as tmp:
            doc = analysis.run_spec(spec, Path(tmp), loader=loader)["doc"]
        self.assertEqual(calls, [("fake-ds", ("AAA", "BBB", "CCC"))])
        self.assertEqual(doc["datasets"]["dataset_id"], "fake-ds")
        self.assertEqual(doc["datasets"]["manifest_sha256"], "abc123")
        self.assertEqual(doc["datasets"]["quality_status"], "pass")

    def _stock_spec(self, **extra):
        return {**json.loads(SPEC.read_text()), "fixture": False, "dataset_id": "stock-ds", **extra}

    @staticmethod
    def _loader(kind):
        def loader(dataset_id, instruments, root):
            return synthetic_fixture(), {"universe_kind": kind, "quality_status": "pass"}
        return loader

    def test_stock_analysis_carries_labels_in_json_report_and_page(self):
        from research.control.analysis_view import load_analyses, render_analysis_page, trust_rows
        from research.control.stage_page import render_page
        from research.control.stage_map import STAGES
        with tempfile.TemporaryDirectory() as tmp:
            titles = []

            def capture(series, stats, title):
                titles.append(title)
                return "<html></html>"
            result = analysis.run_spec(self._stock_spec(), Path(tmp), loader=self._loader("current-holdings-proxy"),
                                       tearsheet=capture)
            self.assertTrue(titles[0].endswith("[survivor-biased, discovery-only]"), titles)
            on_disk = json.loads((result["folder"] / "analysis.json").read_text())
            report = (result["folder"] / "report.md").read_text()
            analyses, _ = load_analyses(tmp)
        self.assertEqual(on_disk["labels"], ["survivor-biased", "discovery-only"])
        self.assertIsNone(on_disk["membership_id"])
        self.assertIn("survivor-biased", report)
        self.assertIn("discovery-only", report)
        page = render_analysis_page(analyses, "now")
        self.assertIn('data-label="survivor-biased"', page)
        self.assertIn('data-label="discovery-only"', page)
        self.assertEqual(trust_rows(analyses)[0]["labels"], ["survivor-biased", "discovery-only"])
        empty = {"stages": {s: {"records": [], "pairs": [], "effects": {}, "dispositions": {}} for s in STAGES},
                 "contexts": {}, "unclassified": [], "unattributable": []}
        pipeline = render_page(empty, [], {}, "now", analyses)
        self.assertIn('data-label="survivor-biased"', pipeline)

    def test_stock_class_dataset_without_universe_kind_is_refused(self):
        def loader(dataset_id, instruments, root):  # many per-symbol bar files + actions: a stock archive
            return synthetic_fixture(), {"universe_kind": None, "inputs": [{"path": f"b{i}"} for i in range(4)]}

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as caught:
                analysis.run_spec(self._stock_spec(), Path(tmp), loader=loader)
            self.assertFalse((Path(tmp) / "analysis").exists())
        self.assertIn("universe_kind", str(caught.exception))

    def test_masked_spec_is_labelled_even_without_universe_kind(self):
        doc = self._masked(universe_kind=None)["doc"]
        self.assertEqual(doc["labels"], ["survivor-biased", "discovery-only"])

    def _masked(self, universe_kind="current-holdings-proxy", identity_membership="mem1"):
        from research.data.identity import build_identity
        archive = {"dataset_id": "arch", "universe": {"equities": [
            {"symbol": s, "name": s, "issuer_identifier": f"id-{s}", "currency": "USD"} for s in ("AAA", "BBB", "CCC")]}}
        sessions = synthetic_fixture().sessions
        membership = {"schema": "membership/v1", "membership_id": "mem1", "intervals": {
            s: [{"start": sessions[0], "end": None}] for s in ("AAA", "BBB", "CCC")}}
        ident = build_identity(archive, {**membership, "membership_id": identity_membership}, [])
        ident.update(identity_id="idn1", created_utc="2026-11-18T00:00:00Z")
        spec = self._stock_spec(membership="mem1", identity="idn1")
        spec["rungs"] = spec["rungs"][:1]
        with tempfile.TemporaryDirectory() as tmp:
            for folder, name, doc in (("membership", "mem1", membership), ("identity", "idn1", ident)):
                (Path(tmp) / folder).mkdir()
                (Path(tmp) / folder / f"{name}.json").write_text(json.dumps(doc))
            return analysis.run_spec(spec, Path(tmp), loader=self._loader(universe_kind))

    def _masked_root(self, tmp, with_manifest=False):
        from research.data.identity import build_identity
        from research.data.manifest import sha256_file, write_manifest
        archive = {"dataset_id": "arch", "universe": {"equities": [
            {"symbol": s, "name": s, "issuer_identifier": f"id-{s}", "currency": "USD"} for s in ("AAA", "BBB", "CCC")]}}
        sessions = synthetic_fixture().sessions
        membership = {"schema": "membership/v1", "membership_id": "mem1", "intervals": {
            s: [{"start": sessions[0], "end": None}] for s in ("AAA", "BBB", "CCC")}}
        ident = build_identity(archive, membership, [])
        ident.update(identity_id="idn1", created_utc="2026-11-18T00:00:00Z")
        for folder, name, doc in (("membership", "mem1", membership), ("identity", "idn1", ident)):
            (Path(tmp) / folder).mkdir()
            (Path(tmp) / folder / f"{name}.json").write_text(json.dumps(doc))
        if with_manifest:
            path = Path(tmp) / "membership" / "mem1.json"
            write_manifest(Path(tmp), {
                "schema": "dataset-manifest/v1", "dataset_id": "mem1", "kind": "normalised",
                "created_utc": "2026-11-18T00:00:00Z", "source": "test", "inputs": [], "recipe": "r",
                "rights": {}, "files": [{"path": "membership/mem1.json", "sha256": sha256_file(path)}], "notes": "n"})
        spec = self._stock_spec(membership="mem1", identity="idn1")
        spec["rungs"] = spec["rungs"][:1]
        return spec

    def test_universe_block_records_hashes_and_the_report_line_states_exclusions(self):
        from research.data.manifest import sha256_file
        excluded = {"count": 52, "names": ["APD", "APTV", "BDX", "GE", "IBM", "MMM"]}

        def loader(dataset_id, instruments, root):
            return synthetic_fixture(), {"universe_kind": "current-holdings-proxy", "universe_excluded": excluded}
        for manifest, verified in ((False, False), (True, True)):
            with tempfile.TemporaryDirectory() as tmp:
                spec = self._masked_root(tmp, with_manifest=manifest)
                result = analysis.run_spec(spec, Path(tmp), loader=loader)
                block = result["doc"]["universe"]
                self.assertEqual(block["membership_sha256"], sha256_file(Path(tmp) / "membership/mem1.json"))
                self.assertEqual(block["identity_sha256"], sha256_file(Path(tmp) / "identity/idn1.json"))
                self.assertEqual(block["membership_manifest_verified"], verified)
                self.assertEqual((block["names"], block["late_or_never_count"]), (3, 0))
                report = (result["folder"] / "report.md").read_text()
        self.assertIn("3 names; 52 excluded incl. APD, APTV, BDX, GE, IBM... (see manifest notes); "
                      "dividends credited on the ex-date (pay date unknown)", report)
        self.assertIn("0 dataset names first join the index", report)

    def test_membership_that_differs_from_its_manifest_is_refused(self):
        from research.data.manifest import ManifestError
        with tempfile.TemporaryDirectory() as tmp:
            spec = self._masked_root(tmp, with_manifest=True)
            path = Path(tmp) / "membership" / "mem1.json"
            path.write_text(path.read_text() + " ")
            with self.assertRaises(ManifestError) as caught:
                analysis.run_spec(spec, Path(tmp), loader=self._loader("current-holdings-proxy"))
            self.assertFalse((Path(tmp) / "analysis").exists())
        self.assertIn("mem1", str(caught.exception))

    def test_identity_built_for_another_membership_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            self._masked(identity_membership="other-mem")
        self.assertIn("mem1", str(caught.exception))
        self.assertIn("other-mem", str(caught.exception))

    def test_etf_analysis_has_no_stock_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            titles = []
            etf = analysis.run_spec(self._stock_spec(), Path(tmp), loader=self._loader(None),
                                    tearsheet=lambda s, st, title: titles.append(title) or "<html></html>")
            self.assertNotIn("[", titles[0])
            fixture = analysis.run_spec(json.loads(SPEC.read_text()), Path(tmp) / "f")
            etf_report = (etf["folder"] / "report.md").read_text()
        self.assertEqual(etf["doc"]["labels"], [])
        self.assertEqual(fixture["doc"]["labels"], [])
        self.assertNotIn("survivor-biased", etf_report)
        self.assertNotIn("Labels:", etf_report)

    def test_membership_spec_masks_and_records_the_coverage_summary(self):
        from research.data.identity import build_identity
        archive = {"dataset_id": "arch", "universe": {"equities": [
            {"symbol": s, "name": s, "issuer_identifier": f"id-{s}", "currency": "USD"} for s in ("AAA", "BBB", "CCC")]}}
        sessions = synthetic_fixture().sessions
        membership = {"schema": "membership/v1", "membership_id": "mem1", "intervals": {
            "AAA": [{"start": sessions[0], "end": None}], "BBB": [{"start": sessions[0], "end": sessions[100]}],
            "CCC": [{"start": sessions[200], "end": None}], "ZZZ": [{"start": sessions[0], "end": None}]}}
        ident = build_identity(archive, membership, [])
        ident.update(identity_id="idn1", created_utc="2026-11-18T00:00:00Z")
        spec = self._stock_spec(membership="mem1", identity="idn1")
        spec["rungs"] = spec["rungs"][:1]
        with tempfile.TemporaryDirectory() as tmp:
            for folder, name, doc in (("membership", "mem1", membership), ("identity", "idn1", ident)):
                (Path(tmp) / folder).mkdir()
                (Path(tmp) / folder / f"{name}.json").write_text(json.dumps(doc))
            result = analysis.run_spec(spec, Path(tmp), loader=self._loader("current-holdings-proxy"))
            run = Path(tmp) / "runs" / result["doc"]["runs"][0]["run_id"]
            from research.evaluation.run_output import read_run
            manifest, tables = read_run(run)
            report = (result["folder"] / "report.md").read_text()
            with self.assertRaises(ValueError):
                analysis.run_spec(self._stock_spec(membership="mem1"), Path(tmp), loader=self._loader(None))
        doc = result["doc"]
        self.assertEqual((doc["membership_id"], doc["identity_id"]), ("mem1", "idn1"))
        summary = doc["coverage_summary"]
        self.assertEqual(summary["sessions"], len(sessions))
        self.assertAlmostEqual(summary["min_share"], 1 / 2)  # ZZZ is a member with no data; BBB left, CCC not in yet
        self.assertEqual(manifest["config"]["universe"], {"membership_id": "mem1", "identity_id": "idn1"})
        self.assertEqual(set(tables["positions"]["instrument"]), {"AAA", "BBB", "CCC"})
        self.assertEqual(doc["lookahead"]["status"], "pass")
        self.assertIn("point-in-time membership `mem1`", report)
        held_late = tables["positions"][(tables["positions"]["date"] > sessions[102])
                                        & (tables["positions"]["date"] < sessions[200])]
        self.assertEqual(set(held_late["instrument"]), {"AAA"})  # BBB left, CCC not yet in

    def test_blocked_dataset_and_absent_data_exit_cleanly(self):
        spec = {**json.loads(SPEC.read_text()), "fixture": False, "dataset_id": "fake-ds"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "spec.json"
            path.write_text(json.dumps(spec))
            for exc, code, text in ((DatasetBlocked("fake-ds: no quality report"), 1, "error: fake-ds"),
                                    (DataAbsent("blocked: data absent: x"), 2, "blocked: data absent: x")):
                err = io.StringIO()
                with mock.patch.object(analysis, "load_dataset", side_effect=exc), \
                        contextlib.redirect_stderr(err):
                    self.assertEqual(analysis.main(["run", "--spec", str(path), "--root", tmp]), code)
                self.assertIn(text, err.getvalue())

    def test_committed_golden_matches(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(analysis.main(["golden"]), 0)


if __name__ == "__main__":
    unittest.main()
