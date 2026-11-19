"""Offline tests of the liquidity-scaled (ADV tier) cost model."""
import dataclasses
import unittest

import pandas as pd

from research.evaluation.engine_contract import EngineError, check_config
from research.evaluation.lookahead import check_lookahead
from research.evaluation.market_model import MarketConfig, MarketData, cost_bps, cost_table, market_config_dict
from research.evaluation.parity_fixture import synthetic_fixture
from research.evaluation.strategies import build_target_fn

ADV = MarketConfig(cost_model="adv")


def _data(volumes, close=10.0):
    """One instrument; ADV (median close x volume) over a constant window is close x volume."""
    n = len(volumes)
    sessions = tuple(d.strftime("%Y-%m-%d") for d in pd.bdate_range("2024-01-02", periods=n))
    frame = pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                          "volume": [float(v) for v in volumes]}, index=pd.Index(sessions, name="date"))
    return MarketData(sessions=sessions, bars={"X": frame}, dividends=(), splits=())


class CostModelTests(unittest.TestCase):
    def test_flat_model_unchanged(self):
        data = synthetic_fixture()
        for i in (0, 5, 100, 249):
            self.assertEqual(cost_bps(data, "AAA", i, MarketConfig()), 5.0)
            self.assertEqual(cost_bps(data, "AAA", i, MarketConfig(cost_bps=7.5)), 7.5)
        # default config keys (and so run hashes) are exactly the pre-existing three
        self.assertEqual(market_config_dict(MarketConfig()),
                         {"initial_cash": 100_000.0, "cost_bps": 5.0, "commission_usd": 1.0})
        self.assertEqual(market_config_dict(ADV), dataclasses.asdict(ADV))

    def test_adv_tiers_and_short_history(self):
        # close 10 x volume v: ADV = 10 v. Tier minimums 1e9 / 1e8 / 2e7 / 0.
        for volume, expected in ((1e8, 2.0), (1e7, 5.0), (2e6, 10.0), (1e6, 25.0), (2e5, 25.0)):
            self.assertEqual(cost_bps(_data([volume] * 30), "X", 25, ADV), expected, volume)
        data = _data([1e8] * 30)
        self.assertEqual(cost_bps(data, "X", 20, ADV), 2.0)   # exactly 20 prior sessions (0..19)
        self.assertEqual(cost_bps(data, "X", 19, ADV), 25.0)  # only 19 prior sessions
        self.assertEqual(cost_bps(data, "X", 0, ADV), 25.0)
        # median, not mean: a single huge day does not lift the tier
        vols = [1e6] * 30
        vols[10] = 1e12
        self.assertEqual(cost_bps(_data(vols), "X", 25, ADV), 25.0)

    def test_adv_uses_only_prior_sessions(self):
        base = [1e6] * 40
        # session i and every later session never enter the window at i
        for index in (25, 26, 39):
            changed = list(base)
            changed[index] = 1e12
            self.assertEqual(cost_bps(_data(base), "X", 25, ADV), cost_bps(_data(changed), "X", 25, ADV), index)
        changed = list(base)
        changed[25:] = [1e12] * 15
        self.assertEqual(cost_bps(_data(changed), "X", 25, ADV), 25.0)
        # window is exactly i-20 .. i-1
        far = list(base)
        far[4] = 1e12                     # session i-21: outside
        self.assertEqual(cost_bps(_data(far), "X", 25, ADV), 25.0)
        high = list(base)
        high[5:25] = [1e9] * 20           # sessions 5..24 = i-20..i-1: all inside
        self.assertEqual(cost_bps(_data(high), "X", 25, ADV), 2.0)
        low_end = list(base)
        low_end[6:26] = [1e9] * 20        # i-20 = 5 is now outside, i-1 = 24 low... window 5..24 has 19 high
        self.assertEqual(cost_bps(_data(low_end), "X", 25, ADV), 2.0)
        half = list(base)
        half[15:25] = [1e9] * 10          # 10 high + 10 low in the window: median is their mean (5e8*10)
        self.assertEqual(cost_bps(_data(half), "X", 25, ADV), 2.0)

    def test_table_matches_cost_bps(self):
        data = synthetic_fixture()
        bars = {n: f.assign(volume=f["volume"] * (n == "AAA") * 400 + f["volume"] * (n != "AAA")) for n, f in data.bars.items()}
        data = MarketData(data.sessions, bars, data.dividends, data.splits)
        table = cost_table(data, ADV)
        for name in data.bars:
            for i in range(len(data.sessions)):
                self.assertEqual(table[name][i], cost_bps(data, name, i, ADV), (name, i))
        self.assertEqual(set(cost_table(data, MarketConfig(cost_bps=3.0))["AAA"]), {3.0})

    def test_custom_tiers_and_validation(self):
        data = _data([1e6] * 30)
        config = MarketConfig(cost_model="adv", adv_tiers=((1e6, 3.0), (0.0, 40.0)))
        self.assertEqual(cost_bps(data, "X", 25, config), 3.0)
        # tiers as lists (e.g. from a JSON spec) work too
        listy = MarketConfig(cost_model="adv", adv_tiers=[[1e6, 3.0], [0.0, 40.0]])
        self.assertEqual(cost_bps(data, "X", 25, listy), 3.0)
        for bad in (MarketConfig(cost_model="vwap"),
                    MarketConfig(cost_model="adv", adv_tiers=()),
                    MarketConfig(cost_model="adv", adv_tiers=((1e9, 2.0), (1e8, -1.0), (0.0, 25.0))),
                    MarketConfig(cost_model="adv", adv_tiers=((1e8, 5.0), (1e9, 2.0), (0.0, 25.0))),
                    MarketConfig(cost_model="adv", adv_tiers=((1e9, 2.0), (1e8, 5.0))),
                    MarketConfig(cost_model="adv", adv_tiers=((1e9, 2.0, 1.0), (0.0, 25.0))),
                    MarketConfig(cost_model="adv", adv_tiers=((float("nan"), 2.0), (0.0, 25.0)))):
            with self.assertRaises(EngineError, msg=str(bad)):
                check_config(bad)
        check_config(ADV)
        check_config(MarketConfig())

    def test_lookahead_passes_with_adv_costs(self):
        spec = {"name": "sma_trend", "window": 20, "gross": 0.95}
        result = check_lookahead(synthetic_fixture(), lambda d: build_target_fn(spec), ADV, cutoffs=4)
        self.assertEqual(result["status"], "pass", result["differences"])


if __name__ == "__main__":
    unittest.main()
