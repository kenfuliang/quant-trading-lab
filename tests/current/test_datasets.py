import json
import shutil
import tempfile
import unittest
from pathlib import Path

from research.data.manifest import ManifestError, sha256_file, write_manifest
from research.evaluation import data_quality as q
from research.evaluation.datasets import DatasetBlocked, latest_report, load_dataset
from research.evaluation.etf_normalise import RECIPE, normalise

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "data"
ID = "fixture-n1"


def make_root(tmp: Path, report: str | None = "pass") -> Path:
    """A data root holding the fixture dataset, a manifest and (optionally) a quality report."""
    (tmp / "normalized").mkdir()
    bars, actions = tmp / "normalized" / "bars.json", tmp / "normalized" / "actions.json"
    shutil.copy(FIXTURES / "etf-bars.json", bars)
    shutil.copy(FIXTURES / "etf-actions.json", actions)
    write_manifest(tmp, {
        "schema": "dataset-manifest/v1", "dataset_id": ID, "kind": "normalised",
        "created_utc": "2026-01-01T00:00:00Z", "source": "fixture",
        "inputs": [{"path": "normalized/bars.json", "sha256": sha256_file(bars)},
                   {"path": "normalized/actions.json", "sha256": sha256_file(actions)}],
        "recipe": RECIPE, "rights": {}, "files": [], "notes": "",
    })
    if report is not None:
        rows, acts = json.loads(bars.read_text()), json.loads(actions.read_text())
        norm = normalise(rows, acts, ("AAA", "KID", "PAR"))
        built = q.build_report(ID, rows, norm, None, norm.data.splits, created_utc="2026-01-01T00:00:00Z")
        built["status"] = report
        q.write_report(tmp, built)
    return tmp


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_load_refuses_missing_or_failed_report(self):
        root = make_root(self.tmp, report=None)
        self.assertIsNone(latest_report(root, ID))
        with self.assertRaises(DatasetBlocked):
            load_dataset(ID, ("AAA",), root)
        failed = Path(tempfile.mkdtemp(dir=self.tmp))
        make_root(failed, report="fail")
        with self.assertRaises(DatasetBlocked):
            load_dataset(ID, ("AAA",), failed)

    def test_load_refuses_changed_input(self):
        root = make_root(self.tmp)
        path = root / "normalized" / "bars.json"
        path.write_text(path.read_text() + " ", encoding="utf-8")
        with self.assertRaises(ManifestError):
            load_dataset(ID, ("AAA",), root)

    def test_load_returns_validated_market_data_and_provenance(self):
        root = make_root(self.tmp, report="pass-with-exceptions")
        data, provenance = load_dataset(ID, ("AAA", "PAR"), root)
        self.assertEqual(sorted(data.bars), ["AAA", "PAR"])
        self.assertEqual(provenance["manifest_sha256"], sha256_file(root / "manifests" / f"{ID}.json"))
        self.assertEqual(provenance["quality_status"], "pass-with-exceptions")
        self.assertEqual(provenance["quality_report"], f"quality/{ID}/20260101T000000Z/report.json")
        self.assertEqual(len(provenance["inputs"]), 2)

    def test_latest_report_picks_newest(self):
        root = make_root(self.tmp)
        newer = root / "quality" / ID / "20270101T000000Z"
        newer.mkdir()
        (newer / "report.json").write_text(json.dumps({"status": "fail"}), encoding="utf-8")
        self.assertEqual(latest_report(root, ID), {"status": "fail"})

    def test_in_kind_value_survives_instrument_restriction(self):
        root = make_root(self.tmp)
        data, _ = load_dataset(ID, ("PAR",), root)  # child KID is not requested
        self.assertEqual(list(data.bars), ["PAR"])
        in_kind = [d for d in data.dividends if d.instrument == "PAR"]
        self.assertEqual(len(in_kind), 1)
        full, _ = load_dataset(ID, ("PAR", "KID"), root)
        self.assertEqual(in_kind, [d for d in full.dividends if d.instrument == "PAR"])
        self.assertGreater(in_kind[0].per_share, 0)


if __name__ == "__main__":
    unittest.main()
