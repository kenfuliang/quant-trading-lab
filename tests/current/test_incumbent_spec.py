"""The incumbent spec file matches the controller's decisions and the code's INCUMBENT_SPEC."""
import json
import unittest
from pathlib import Path

from research.evaluation.strategies import INCUMBENT_SPEC, build_target_fn

SPEC = Path(__file__).resolve().parents[2] / "research/registry/analysis-specs/incumbent-spy-gate.json"


class IncumbentSpecTests(unittest.TestCase):
    def test_incumbent_spec_matches_decisions(self):
        spec = json.loads(SPEC.read_text())
        self.assertEqual(spec["dataset_id"], "sector-etfs-2016-2025-n1")
        self.assertEqual(spec["instruments"], ["SPY"])
        self.assertEqual([r["name"] for r in spec["rungs"]], ["hold", "trend", "gate", "costs"])
        hold, trend, gate, costs = spec["rungs"]
        self.assertEqual(hold["strategy"], {"name": "buy_hold", "gross": 0.99})
        self.assertEqual(trend["strategy"], {"name": "ema_trend", "fast": 50, "slow": 200, "gross": 0.99})
        self.assertEqual(gate["strategy"], INCUMBENT_SPEC)
        self.assertEqual(costs["strategy"], INCUMBENT_SPEC)
        for rung in (hold, trend, gate):
            self.assertEqual(rung["market"], {"cost_bps": 0, "commission_usd": 0})
        self.assertEqual(costs["market"], {"cost_bps": 5, "commission_usd": 1})
        self.assertEqual(spec["comparison"], {"record_ids": ["legacy-030-discrete-ema-volatility-gate",
                                                              "legacy-058-gate-only-spy-control"]})
        self.assertEqual(spec["cutoffs"], 5)
        grid = spec["pbo_grid"]
        self.assertEqual(len(grid), 8)
        self.assertEqual({(g["fast"], g["slow"], g["red_vol"]) for g in grid},
                         {(f, s, v) for f in (20, 50) for s in (100, 200) for v in (0.35, 0.40)})
        for item in grid:
            self.assertEqual(item["name"], "traffic_light")
            build_target_fn(item)


if __name__ == "__main__":
    unittest.main()
