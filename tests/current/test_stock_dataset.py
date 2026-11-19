import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from research.data.manifest import ManifestError, read_manifest, sha256_file, write_manifest
from research.evaluation import data_quality as q
from research.evaluation import datasets
from research.evaluation.datasets import load_dataset
from research.evaluation.etf_normalise import RECIPE, normalise
from scripts import data as data_cli

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "data"
ID = "stock-fixture-n1"
NAMES = ("AAA", "KID", "PAR")


def make_root(tmp: Path, universe_kind: str | None = "current-holdings-proxy") -> Path:
    """A data root with three per-symbol bar files, an actions file, a manifest and a pass report."""
    bars_dir = tmp / "normalized" / "stocks-v1"
    bars_dir.mkdir(parents=True)
    rows = json.loads((FIXTURES / "etf-bars.json").read_text())
    inputs = []
    for name in NAMES:
        path = bars_dir / f"{name}.json"
        path.write_text(json.dumps([r for r in rows if r["symbol"] == name]), encoding="utf-8")
        inputs.append({"path": f"normalized/stocks-v1/{name}.json", "sha256": sha256_file(path)})
    actions = tmp / "normalized" / "stocks-actions.json"
    shutil.copy(FIXTURES / "etf-actions.json", actions)
    inputs.append({"path": "normalized/stocks-actions.json", "sha256": sha256_file(actions)})
    manifest = {"schema": "dataset-manifest/v1", "dataset_id": ID, "kind": "normalised",
                "created_utc": "2026-01-01T00:00:00Z", "source": "fixture", "inputs": inputs,
                "recipe": RECIPE, "rights": {}, "files": [], "notes": "excluded ZZZ: reverse split"}
    if universe_kind:
        manifest["universe_kind"] = universe_kind
    write_manifest(tmp, manifest)
    all_rows = [r for r in rows if r["symbol"] in NAMES]
    acts = json.loads(actions.read_text())
    norm = normalise(all_rows, acts, NAMES)
    report = q.build_report(ID, all_rows, norm, None, norm.data.splits, created_utc="2026-01-01T00:00:00Z",
                            inputs={"manifest_sha256": sha256_file(tmp / "manifests" / f"{ID}.json")},
                            code_commit="test")
    report["status"] = "pass"
    q.write_report(tmp, report)
    return tmp


class StockDatasetTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_multi_file_manifest_round_trip(self):
        root = make_root(self.tmp)
        manifest = read_manifest(root, ID)
        self.assertEqual(len(manifest["inputs"]), 4)
        self.assertEqual(manifest["universe_kind"], "current-holdings-proxy")
        data, provenance = load_dataset(ID, NAMES, root)
        rows = json.loads((FIXTURES / "etf-bars.json").read_text())
        expected = normalise(rows, json.loads((FIXTURES / "etf-actions.json").read_text()), NAMES).data
        self.assertEqual(data.sessions, expected.sessions)
        self.assertEqual(data.dividends, expected.dividends)
        self.assertEqual(data.splits, expected.splits)
        for name in NAMES:
            pd.testing.assert_frame_equal(data.bars[name], expected.bars[name])
        self.assertEqual(len(provenance["inputs"]), 4)
        subset, _ = load_dataset(ID, ("AAA", "PAR"), root)
        self.assertEqual(sorted(subset.bars), ["AAA", "PAR"])
        self.assertTrue(all(d.instrument in ("AAA", "PAR") for d in subset.dividends))
        with self.assertRaises(ValueError):
            load_dataset(ID, ("AAA", "NOPE"), root)

    def test_changed_bar_file_is_refused(self):
        root = make_root(self.tmp)
        path = root / "normalized" / "stocks-v1" / "PAR.json"
        path.write_text(path.read_text() + " ", encoding="utf-8")
        with self.assertRaisesRegex(ManifestError, "PAR.json"):
            load_dataset(ID, NAMES, root)

    def test_cache_is_used_and_verified(self):
        root = make_root(self.tmp)
        _data, first = load_dataset(ID, NAMES, root)
        self.assertEqual(first["cache"], "rebuilt")
        cache = root / "cache" / first["manifest_sha256"]
        self.assertTrue((cache / "cache-manifest.json").is_file())
        self.assertEqual(len(list(cache.glob("*.parquet"))), 3)
        with mock.patch.object(datasets, "normalise", side_effect=AssertionError("cache not used")):
            cached, second = load_dataset(ID, NAMES, root)
        self.assertEqual(second["cache"], "hit")
        fresh = normalise(json.loads((FIXTURES / "etf-bars.json").read_text()),
                          json.loads((FIXTURES / "etf-actions.json").read_text()), NAMES).data
        for name in NAMES:
            pd.testing.assert_frame_equal(cached.bars[name], fresh.bars[name])
        self.assertEqual(cached.dividends, fresh.dividends)
        # a tampered cache file is rebuilt, never trusted
        target = cache / "bars-AAA.parquet"
        frame = pd.read_parquet(target)
        frame["close"] = frame["close"] * 2
        frame.to_parquet(target)
        rebuilt, third = load_dataset(ID, NAMES, root)
        self.assertEqual(third["cache"], "rebuilt")
        pd.testing.assert_frame_equal(rebuilt.bars["AAA"], fresh.bars["AAA"])
        _data, fourth = load_dataset(ID, NAMES, root)
        self.assertEqual(fourth["cache"], "hit")
        # a missing cache file is rebuilt too
        target.unlink()
        _data, fifth = load_dataset(ID, NAMES, root)
        self.assertEqual(fifth["cache"], "rebuilt")
        self.assertTrue(target.is_file())

    def test_cache_of_another_manifest_is_never_used(self):
        root = make_root(self.tmp)
        _data, first = load_dataset(ID, NAMES, root)
        cache = root / "cache" / first["manifest_sha256"]
        info = json.loads((cache / "cache-manifest.json").read_text())
        info["manifest_sha256"] = "0" * 64
        (cache / "cache-manifest.json").write_text(json.dumps(info), encoding="utf-8")
        _data, again = load_dataset(ID, NAMES, root)
        self.assertEqual(again["cache"], "rebuilt")

    def test_universe_kind_in_provenance(self):
        root = make_root(self.tmp)
        self.assertEqual(load_dataset(ID, NAMES, root)[1]["universe_kind"], "current-holdings-proxy")
        plain = make_root(Path(tempfile.mkdtemp(dir=self.tmp)), universe_kind=None)
        self.assertIsNone(load_dataset(ID, NAMES, plain)[1]["universe_kind"])

    def test_excluded_symbols_listed_in_report(self):
        rows = [r for r in json.loads((FIXTURES / "etf-bars.json").read_text()) if r["symbol"] in NAMES]
        actions = json.loads((FIXTURES / "etf-actions.json").read_text())
        norm = normalise(rows, actions, NAMES)
        excluded = [{"symbol": "ZZZ", "reason": "reverse split 1:10 on 2020-01-02"},
                    {"symbol": "YYY", "reason": "fetch failed"}]
        report = q.build_report(ID, rows, norm, None, norm.data.splits, created_utc="2026-01-01T00:00:00Z",
                                excluded_symbols=excluded, actions=actions, code_commit="test")
        universe = next(c for c in report["checks"] if c["name"] == "universe")
        self.assertEqual(universe["status"], "exception")
        self.assertEqual(universe["count"], 2)
        self.assertEqual({i["symbol"] for i in universe["items"]}, {"ZZZ", "YYY"})
        # an ETF-style report has neither new check
        plain = q.build_report(ID, rows, norm, None, norm.data.splits, created_utc="2026-01-01T00:00:00Z",
                               code_commit="test")
        self.assertNotIn("universe", [c["name"] for c in plain["checks"]])
        self.assertNotIn("pay_date_assumed", [c["name"] for c in plain["checks"]])

    def test_pay_date_assumed_is_an_exception(self):
        rows = [r for r in json.loads((FIXTURES / "etf-bars.json").read_text()) if r["symbol"] in NAMES]
        actions = json.loads((FIXTURES / "etf-actions.json").read_text())
        actions["cash_and_in_kind"] = [dict(e, pay_date_label="pay_date_unknown_credited_on_ex_date")
                                       if e["kind"] == "cash" else e for e in actions["cash_and_in_kind"]]
        norm = normalise(rows, actions, NAMES)
        report = q.build_report(ID, rows, norm, None, norm.data.splits, actions=actions, code_commit="test")
        check = next(c for c in report["checks"] if c["name"] == "pay_date_assumed")
        self.assertEqual(check["status"], "exception")
        self.assertEqual(check["count"], sum(1 for e in actions["cash_and_in_kind"]
                                                 if e["kind"] == "cash" and e["symbol"] in NAMES))

    def test_cross_source_caps_breaches_per_symbol(self):
        rows = [r for r in json.loads((FIXTURES / "etf-bars.json").read_text()) if r["symbol"] in NAMES]
        actions = json.loads((FIXTURES / "etf-actions.json").read_text())
        norm = normalise(rows, actions, NAMES)
        yahoo = {name: frame.copy() for name, frame in norm.data.bars.items() if name != "KID"}
        for frame in yahoo.values():
            frame["close"] = frame["close"] + 1.0
        report = q.build_report(ID, rows, norm, yahoo, norm.data.splits, code_commit="test")
        check = next(c for c in report["checks"] if c["name"] == "cross_source")
        self.assertEqual(check["status"], "exception")
        top = check["stats"]["top_breaches_by_symbol"]
        self.assertTrue(all(len(items) <= 10 for items in top.values()))
        self.assertNotIn("KID", top)
        self.assertGreater(check["stats"]["not_compared_count"], 0)

    def test_cli_normalise_builds_stock_manifest(self):
        root = make_root(self.tmp)
        (root / "manifests" / f"{ID}.json").unlink()
        shutil.rmtree(root / "quality")
        (root / "manifests" / "stocks-v1.json").write_text(json.dumps(
            {"schema": "x", "source": "alpaca", "feed": "sip"}), encoding="utf-8")
        coverage = root / "normalized" / "stocks-v1-coverage.csv"
        coverage.write_text("symbol,status\nAAA,structural_full_window\nKID,structural_full_window\n"
                            "PAR,structural_full_window\nZZZ,structural_full_window\nLATE,partial\n",
                            encoding="utf-8")
        actions = json.loads((root / "normalized" / "stocks-actions.json").read_text())
        actions["excluded_symbols"] = [{"symbol": "ZZZ", "reason": "reverse split"}]
        (root / "normalized" / "stocks-actions.json").write_text(json.dumps(actions), encoding="utf-8")
        argv = ["normalise", "--root", str(root), "--bars-dir", "normalized/stocks-v1",
                "--symbols-from", "normalized/stocks-v1-coverage.csv", "--status", "structural_full_window",
                "--actions", "normalized/stocks-actions.json", "--exclude-from-actions",
                "--universe-kind", "current-holdings-proxy", "--dataset-id", ID]
        self.assertEqual(data_cli.main(argv), 0)
        manifest = read_manifest(root, ID)
        self.assertEqual([e["path"] for e in manifest["inputs"]],
                         [f"normalized/stocks-v1/{n}.json" for n in NAMES] + ["normalized/stocks-actions.json"])
        self.assertEqual(manifest["universe_kind"], "current-holdings-proxy")
        self.assertIn("ZZZ", manifest["notes"])
        self.assertIn("reverse split", manifest["notes"])

    def test_bars_dir_without_universe_kind_fails_loudly(self):
        root = make_root(Path(self.tmp))
        argv = ["normalise", "--root", str(root), "--bars-dir", "normalized/stocks-v1",
                "--symbols-from", "normalized/stocks-v1-coverage.csv", "--status", "structural_full_window",
                "--actions", "normalized/stocks-actions.json", "--dataset-id", "no-kind"]
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(data_cli.main(argv), 1)
        self.assertIn("--universe-kind", err.getvalue())


if __name__ == "__main__":
    unittest.main()
