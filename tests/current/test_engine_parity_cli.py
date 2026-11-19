import contextlib
import hashlib
import io
import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from research.evaluation.market_model import MarketDataError
from research.evaluation.parity_fixture import synthetic_fixture
from research.evaluation.run_output import config_hash, read_run
from scripts.current import engine_parity
from tests.current.test_datasets import ID, make_root


class EngineParityCliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.bars = self.root / "bars.json"
        self.actions = self.root / "actions.json"
        self.bars.write_text("[]", encoding="utf-8")
        self.actions.write_text("{}", encoding="utf-8")
        self.out = self.root / "parity"
        self.runs = self.root / "runs"

    def _argv(self):
        return ["run", "--bars", str(self.bars), "--actions", str(self.actions),
                "--instruments", "AAA,BBB,CCC", "--out", str(self.out), "--runs", str(self.runs)]

    def _receipt(self):
        receipts = sorted(self.out.glob("*/receipt.json"))
        self.assertEqual(len(receipts), 1)
        return receipts[0].parent, json.loads(receipts[0].read_text(encoding="utf-8"))

    def test_cli_writes_two_runs_and_receipt(self):
        code = engine_parity.main(self._argv(), loader=lambda bars, actions, names: synthetic_fixture())
        self.assertEqual(code, 0)
        folder, receipt = self._receipt()
        self.assertEqual(receipt["schema"], "parity-receipt/v1")
        self.assertTrue(receipt["passed"])
        self.assertEqual(receipt["mismatches"], [])

        # Runs live under the runs root (.local/runs/<run_id>/), not inside the parity folder.
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ["receipt.json"])
        self.assertEqual(receipt["runs_root"], str(self.runs))
        self.assertEqual(set(receipt["runs"]), {"screen", "nautilus"})
        for engine, entry in receipt["runs"].items():
            manifest_path = self.runs / entry["run_id"] / "manifest.json"
            self.assertEqual(entry["manifest_sha256"], hashlib.sha256(manifest_path.read_bytes()).hexdigest())
        screen_manifest, screen_tables = read_run(self.runs / receipt["runs"]["screen"]["run_id"])
        native_manifest, _ = read_run(self.runs / receipt["runs"]["nautilus"]["run_id"])
        self.assertIsNone(screen_manifest["parent_run"])
        self.assertEqual(native_manifest["parent_run"], screen_manifest["run_id"])
        self.assertNotEqual(screen_manifest["run_id"], native_manifest["run_id"])
        self.assertFalse(screen_tables["fills"].empty)

        # Manifest identity: engine names match EngineResult.engine; config holds only the
        # configuration, so config_hash identifies it (code and inputs have their own keys).
        self.assertEqual((screen_manifest["engine"], native_manifest["engine"]), ("screen", "nautilus"))
        for manifest in (screen_manifest, native_manifest):
            self.assertEqual(set(manifest["config"]), {"strategy", "market", "instruments", "engine"})
            self.assertEqual(manifest["config"]["engine"], manifest["engine"])
            self.assertEqual(manifest["config_hash"], config_hash(manifest["config"]))
            self.assertEqual(manifest["datasets"], receipt["inputs"])
            self.assertEqual(manifest["code_commit"], receipt["code_commit"])
        self.assertTrue(native_manifest["engine_version"].startswith("nautilus_trader "))

        fixture = synthetic_fixture()
        self.assertEqual(receipt["calendar"], {
            "sessions": len(fixture.sessions), "first": fixture.sessions[0], "last": fixture.sessions[-1],
            "identical_across_instruments": True, "half_days": [], "half_days_note": "not marked by source",
        })
        timing = receipt["timing"]
        self.assertGreater(timing["screening_seconds"], 0)
        self.assertGreater(timing["native_seconds"], 0)
        self.assertAlmostEqual(timing["projected_seconds_500_names"], timing["native_seconds"] * 500 / 3)
        self.assertEqual(receipt["cash_interest"], "not modelled")
        for key in ("bars", "actions"):
            self.assertEqual(len(receipt["inputs"][key]["sha256"]), 64)

    def test_cli_records_rejected_input_and_exits_non_zero(self):
        def loader(bars, actions, names):
            raise MarketDataError("SPY: price not on the cent grid")

        code = engine_parity.main(self._argv(), loader=loader)
        self.assertNotEqual(code, 0)
        _, receipt = self._receipt()
        self.assertFalse(receipt["passed"])
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["stage"], "load")
        self.assertIn("cent grid", receipt["error"]["message"])
        self.assertIsNone(receipt["runs"])
        self.assertFalse(self.runs.exists())
        self.assertEqual(receipt["cash_interest"], "not modelled")

    def test_engine_parity_defaults_to_data_root(self):
        data = self.root / "dataroot"
        argv = ["run", "--bars", str(self.bars), "--actions", str(self.actions), "--instruments", "AAA,BBB,CCC"]
        with mock.patch.dict(os.environ, {"QTL_DATA_ROOT": str(data)}):
            code = engine_parity.main(argv, loader=lambda bars, actions, names: synthetic_fixture())
        self.assertEqual(code, 0)
        self.assertEqual(len(list((data / "parity").glob("*/receipt.json"))), 1)
        self.assertEqual(len(list((data / "runs").glob("*/manifest.json"))), 2)

    def test_missing_inputs_exit_2_with_blocked_message(self):
        data = self.root / "dataroot"
        missing = self.root / "nope.json"
        argv = ["run", "--bars", str(missing), "--actions", str(self.actions), "--instruments", "AAA"]
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"QTL_DATA_ROOT": str(data)}), contextlib.redirect_stderr(stderr):
            code = engine_parity.main(argv, loader=lambda *a: synthetic_fixture())
        self.assertEqual(code, 2)
        self.assertIn(f"blocked: data absent: {missing}", stderr.getvalue())
        self.assertFalse((data / "parity").exists())
        self.assertFalse((data / "runs").exists())

    def test_engine_parity_dataset_mode_records_manifest_and_quality(self):
        data = self.root / "dataroot"
        data.mkdir()
        make_root(data, report="pass-with-exceptions")
        argv = ["run", "--dataset", ID, "--instruments", "AAA,PAR"]
        with mock.patch.dict(os.environ, {"QTL_DATA_ROOT": str(data)}):
            code = engine_parity.main(argv)
        self.assertEqual(code, 0)
        receipts = list((data / "parity").glob("*/receipt.json"))
        self.assertEqual(len(receipts), 1)
        receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
        inputs = receipt["inputs"]
        self.assertEqual(inputs["dataset_id"], ID)
        self.assertEqual(inputs["manifest_sha256"], hashlib.sha256((data / "manifests" / f"{ID}.json").read_bytes()).hexdigest())
        self.assertEqual(inputs["quality_status"], "pass-with-exceptions")
        self.assertEqual(inputs["quality_report"], f"quality/{ID}/20260101T000000Z/report.json")
        self.assertEqual(len(inputs["bars"]["sha256"]), 64)
        self.assertEqual(receipt["calendar"]["half_days"], [])
        self.assertTrue(receipt["passed"])
        manifest, _ = read_run(data / "runs" / receipt["runs"]["screen"]["run_id"])
        self.assertEqual(manifest["datasets"], inputs)

    def test_dataset_mode_blocked_without_quality_report_is_recorded(self):
        data = self.root / "dataroot"
        data.mkdir()
        make_root(data, report=None)
        argv = ["run", "--dataset", ID, "--instruments", "AAA"]
        with mock.patch.dict(os.environ, {"QTL_DATA_ROOT": str(data)}), contextlib.redirect_stderr(io.StringIO()):
            code = engine_parity.main(argv)
        self.assertEqual(code, 1)
        receipt = json.loads(next((data / "parity").glob("*/receipt.json")).read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["type"], "DatasetBlocked")

    def test_dataset_and_bars_are_mutually_exclusive(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            engine_parity.main(["run", "--dataset", ID, "--bars", str(self.bars), "--instruments", "AAA"])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            engine_parity.main(["run", "--instruments", "AAA"])

    def _stock_stub(self):
        fixture = synthetic_fixture()

        def loader(dataset, instruments):
            data = fixture
            if instruments is not None:
                wanted = set(instruments)
                data = replace(fixture, bars={n: fixture.bars[n] for n in instruments},
                               dividends=tuple(d for d in fixture.dividends if d.instrument in wanted),
                               splits=tuple(s for s in fixture.splits if s.instrument in wanted))
            return data, {"manifest_sha256": "0" * 64, "quality_status": "pass-with-exceptions",
                          "quality_report": "quality/x/report.json", "half_days": [],
                          "inputs": [{"path": "n/A.json", "sha256": "a" * 64}, {"path": "n/B.json", "sha256": "b" * 64},
                                   {"path": "n/actions.json", "sha256": "c" * 64}],
                          "universe_kind": "current-holdings-proxy"}
        return loader

    def test_max_instruments_cost_model_and_timing_only(self):
        data = self.root / "dataroot"
        data.mkdir()
        make_root(data, report="pass-with-exceptions")
        argv = ["run", "--dataset", ID, "--max-instruments", "2", "--cost-model", "adv", "--timing-only"]
        with mock.patch.dict(os.environ, {"QTL_DATA_ROOT": str(data)}):
            code = engine_parity.main(argv, dataset_loader=self._stock_stub())
        self.assertEqual(code, 0)
        receipt = json.loads(next((data / "parity").glob("*/receipt.json")).read_text(encoding="utf-8"))
        self.assertEqual(receipt["instruments"], ["AAA", "BBB"])  # first N, alphabetical
        self.assertEqual(receipt["market"]["cost_model"], "adv")
        self.assertEqual(receipt["status"], "timing_only")
        self.assertIsNone(receipt["passed"])
        self.assertIsNone(receipt["mismatches"])
        self.assertIsNone(receipt["runs"])
        self.assertEqual(receipt["claim"], "timing only; no parity or financial claim")
        self.assertEqual(receipt["labels"], ["survivor-biased", "discovery-only"])
        self.assertEqual(receipt["inputs"]["manifest_sha256"], "0" * 64)
        self.assertEqual(receipt["inputs"]["quality_status"], "pass-with-exceptions")
        self.assertEqual(receipt["inputs"]["bars"]["files"], 2)
        self.assertEqual(receipt["inputs"]["actions"], [{"path": "n/actions.json", "sha256": "c" * 64}])
        self.assertEqual(receipt["timing"]["universe_names"], 3)
        self.assertFalse((data / "runs").exists())

    def test_max_instruments_parity_with_adv_costs(self):
        data = self.root / "dataroot"
        data.mkdir()
        make_root(data, report="pass-with-exceptions")
        argv = ["run", "--dataset", ID, "--max-instruments", "3", "--cost-model", "adv"]
        with mock.patch.dict(os.environ, {"QTL_DATA_ROOT": str(data)}):
            code = engine_parity.main(argv, dataset_loader=self._stock_stub())
        self.assertEqual(code, 0)
        receipt = json.loads(next((data / "parity").glob("*/receipt.json")).read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "passed")
        self.assertEqual(receipt["market"]["cost_model"], "adv")
        self.assertEqual(set(receipt["runs"]), {"screen", "nautilus"})

    def test_instruments_or_max_instruments_required(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            engine_parity.main(["run", "--dataset", ID])

    def test_missing_dataset_manifest_exits_2(self):
        data = self.root / "dataroot"
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"QTL_DATA_ROOT": str(data)}), contextlib.redirect_stderr(stderr):
            code = engine_parity.main(["run", "--dataset", "nope", "--instruments", "AAA"])
        self.assertEqual(code, 2)
        self.assertIn("blocked: data absent:", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
