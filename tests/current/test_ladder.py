"""Offline tests of the ablation ladder and waterfall."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from research.evaluation.ladder import Rung, run_ladder, waterfall
from research.evaluation.market_model import MarketConfig
from research.evaluation.metrics import METRIC_KEYS
from research.evaluation.parity_fixture import synthetic_fixture
from research.evaluation.run_output import read_run

ZERO = MarketConfig(cost_bps=0, commission_usd=0)
RUNGS = [
    Rung("hold", {"name": "buy_hold", "gross": 0.99}, ZERO),
    Rung("trend", {"name": "ema_trend", "fast": 10, "slow": 30, "gross": 0.99}, ZERO),
    Rung("costs", {"name": "ema_trend", "fast": 10, "slow": 30, "gross": 0.99}, MarketConfig()),
]


class LadderTests(unittest.TestCase):
    def test_ladder_links_parent_runs_and_writes_outputs(self):
        now = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
        base = {"code_commit": "abc123", "datasets": {"dataset_id": "synthetic"}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "runs"
            results = run_ladder(synthetic_fixture(), RUNGS, root, base, now)
            self.assertEqual([r["rung"] for r in results], ["hold", "trend", "costs"])
            self.assertEqual(len({r["run_id"] for r in results}), 3)
            for r in results:
                self.assertEqual(tuple(r["summary"]), METRIC_KEYS)
            parents = []
            for index, r in enumerate(results):
                manifest, tables = read_run(root / r["run_id"])
                parents.append(manifest["parent_run"])
                self.assertEqual(manifest["config"]["ladder"]["rung"], RUNGS[index].name)
                self.assertEqual(manifest["config"]["ladder"]["index"], index)
                self.assertEqual(manifest["config"]["engine"], "screen")
                self.assertEqual(manifest["datasets"], base["datasets"])
                self.assertEqual(manifest["code_commit"], "abc123")
                self.assertEqual(len(tables["returns"]), 250)
            self.assertEqual(parents, [None, results[0]["run_id"], results[1]["run_id"]])
            self.assertEqual(len({r["run_id"] for r in results}), len(list(root.iterdir())))
            with self.assertRaises(Exception):  # exclusive create: same inputs, same instant
                run_ladder(synthetic_fixture(), RUNGS, root, base, now)

    def test_waterfall_deltas_and_none_propagation(self):
        def summary(**kw):
            return {k: kw.get(k, 1.0) for k in METRIC_KEYS}

        steps = [
            {"rung": "a", "summary": summary(net_cagr=0.10, calmar=None)},
            {"rung": "b", "summary": summary(net_cagr=0.07, calmar=2.0)},
            {"rung": "c", "summary": summary(net_cagr=0.08, calmar=3.0)},
        ]
        out = waterfall(steps)
        self.assertEqual([(s["from"], s["to"]) for s in out], [("a", "b"), ("b", "c")])
        self.assertAlmostEqual(out[0]["delta"]["net_cagr"], -0.03)
        self.assertIsNone(out[0]["delta"]["calmar"])
        self.assertAlmostEqual(out[1]["delta"]["calmar"], 1.0)
        self.assertEqual(tuple(out[0]["delta"]), METRIC_KEYS)
        self.assertEqual(waterfall(steps[:1]), [])


if __name__ == "__main__":
    unittest.main()
