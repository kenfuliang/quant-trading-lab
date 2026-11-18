import json
import tempfile
import unittest
from pathlib import Path

from research.evaluation.market_model import MarketDataError
from research.evaluation.parity_fixture import synthetic_fixture
from research.evaluation.run_output import read_run
from scripts.current import engine_parity


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

    def _argv(self):
        return ["run", "--bars", str(self.bars), "--actions", str(self.actions),
                "--instruments", "AAA,BBB,CCC", "--out", str(self.out)]

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

        screen_manifest, screen_tables = read_run(folder / receipt["runs"]["screening"])
        native_manifest, _ = read_run(folder / receipt["runs"]["native"])
        self.assertIsNone(screen_manifest["parent_run"])
        self.assertEqual(native_manifest["parent_run"], screen_manifest["run_id"])
        self.assertNotEqual(screen_manifest["run_id"], native_manifest["run_id"])
        self.assertFalse(screen_tables["fills"].empty)

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
        self.assertEqual(receipt["cash_interest"], "not modelled")


if __name__ == "__main__":
    unittest.main()
