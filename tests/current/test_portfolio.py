"""Offline tests of the portfolio combiner (sleeve-level, long-only, no leverage)."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from research.evaluation import portfolio as pf
from research.evaluation.run_output import config_hash, read_run, write_run

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


def _returns(rets, dates, initial=100_000.0):
    equity, prev = [], initial
    for r in rets:
        prev = prev * (1 + r)
        equity.append(prev)
    return pd.DataFrame({"date": list(dates), "gross_return": list(map(float, rets)), "cost": 0.0,
                         "net_return": list(map(float, rets)), "equity": equity})


def _sleeve(run_id, rets, dates, **extra):
    manifest = {"run_id": run_id, "datasets": {"d": {"id": run_id}}, **extra}
    return pf.Sleeve(run_id, manifest, _returns(rets, dates))


def _sig(tables, stage):
    s = tables["signals"]
    return s[s["stage"] == stage].pivot(index="date", columns="instrument", values="value")


def _pos(tables):
    return tables["positions"].pivot(index="date", columns="instrument", values="weight")


D3 = ["2024-01-02", "2024-01-03", "2024-01-04"]


class CombineTests(unittest.TestCase):
    def test_equal_weight_hand_computed(self):
        a = _sleeve("A", [0.10, 0.0, -0.10], D3)
        b = _sleeve("B", [0.0, 0.10, 0.10], D3)
        t = pf.combine([a, b], "equal", rebalance="daily", rebalance_cost_bps=0.0)
        r = t["returns"]
        np.testing.assert_allclose(r["gross_return"], [0.05, 0.05, 0.0], atol=1e-15)
        np.testing.assert_allclose(r["cost"], 0.0)
        np.testing.assert_allclose(r["net_return"], [0.05, 0.05, 0.0], atol=1e-15)
        np.testing.assert_allclose(r["equity"], [105_000.0, 110_250.0, 110_250.0], rtol=1e-12)
        pos = _pos(t)
        np.testing.assert_allclose(pos["A"], [0.5 * 1.1 / 1.05, 0.5 / 1.05, 0.5 * 0.9 / 1.0], rtol=1e-12)
        np.testing.assert_allclose(pos["B"], [0.5 / 1.05, 0.5 * 1.1 / 1.05, 0.5 * 1.1 / 1.0], rtol=1e-12)
        self.assertTrue((t["positions"]["quantity"] == 0).all())
        np.testing.assert_allclose(_sig(t, "target_weight").to_numpy(), 0.5)
        self.assertEqual(len(t["fills"]), 0)
        self.assertEqual(list(t["fills"].columns), list(pf.COLUMNS["fills"]))

    def test_drift_between_monthly_rebalances(self):
        dates = ["2024-01-30", "2024-01-31", "2024-02-01", "2024-02-02"]
        a = _sleeve("A", [0.2, 0.1, 0.0, 0.0], dates)
        b = _sleeve("B", [0.0, 0.0, 0.0, 0.1], dates)
        t = pf.combine([a, b], "equal", rebalance="monthly", rebalance_cost_bps=0.0)
        pos = _pos(t)
        wa1 = 0.5 * 1.2 / 1.1
        self.assertAlmostEqual(pos["A"].iloc[0], wa1, places=12)
        wa2 = wa1 * 1.1 / (1 + wa1 * 0.1)  # B returns 0 on session 2
        self.assertAlmostEqual(pos["A"].iloc[1], wa2, places=12)
        # Session 2 return uses the drifted weight (no rebalance), not 0.5.
        self.assertAlmostEqual(t["returns"]["gross_return"].iloc[1], wa1 * 0.1, places=12)
        # Feb 1 is the first session of the month: reset to 0.5 before the (zero) return.
        self.assertAlmostEqual(pos["A"].iloc[2], 0.5, places=12)
        self.assertEqual(list(_sig(t, "target_weight").index), ["2024-01-30", "2024-02-01"])

    def test_rebalance_cost_charged_on_turnover(self):
        a = _sleeve("A", [0.0, 0.1, 0.0], D3)
        b = _sleeve("B", [0.0, 0.0, 0.0], D3)
        t = pf.combine([a, b], "equal", rebalance="daily", rebalance_cost_bps=10.0)
        r = t["returns"]
        self.assertAlmostEqual(r["cost"].iloc[0], 10 * 1.0 / 10_000, places=15)  # all-cash start
        self.assertAlmostEqual(r["net_return"].iloc[0], -0.001, places=15)
        self.assertAlmostEqual(r["equity"].iloc[0], 99_900.0, places=8)
        # session 2: weights drifted from 0.5 after A's +10% on session 2? no: drift is from session 1 (zero returns)
        self.assertAlmostEqual(r["cost"].iloc[1], 0.0, places=15)
        # session 3 starts from the drift of session 2: A 0.5*1.1/1.05
        wa = 0.5 * 1.1 / 1.05
        turnover = abs(0.5 - wa) + abs(0.5 - (1 - wa))
        self.assertAlmostEqual(r["cost"].iloc[2], 10 * turnover / 10_000, places=15)
        np.testing.assert_allclose(r["gross_return"], r["net_return"] + r["cost"], atol=1e-15)

    def test_inverse_vol_hand_computed_and_equal_before_window(self):
        dates = [f"2024-01-{d:02d}" for d in range(2, 7)]
        a = _sleeve("A", [0.01, -0.01, 0.01, -0.01, 0.01], dates)
        b = _sleeve("B", [0.02, -0.02, 0.02, -0.02, 0.02], dates)
        t = pf.combine([a, b], "inverse_vol", vol_window=3, rebalance="daily", rebalance_cost_bps=0.0)
        tw = _sig(t, "target_weight")
        np.testing.assert_allclose(tw.iloc[:3].to_numpy(), 0.5)
        sa = np.std([0.01, -0.01, 0.01], ddof=1)
        sb = np.std([0.02, -0.02, 0.02], ddof=1)
        expected_a = (1 / sa) / (1 / sa + 1 / sb)
        self.assertAlmostEqual(expected_a, 2 / 3, places=12)
        np.testing.assert_allclose(tw["A"].iloc[3:], expected_a, rtol=1e-12)
        np.testing.assert_allclose(tw["B"].iloc[3:], 1 - expected_a, rtol=1e-12)
        vol = _sig(t, "sleeve_vol")
        self.assertEqual(list(vol.index), dates[3:])
        np.testing.assert_allclose(vol["A"].iloc[0], sa, rtol=1e-12)
        # Gross < 1 scales the weights, leaving the rest in cash.
        g = pf.combine([a, b], "inverse_vol", gross=0.6, vol_window=3, rebalance="daily")
        tw2 = _sig(g, "target_weight")
        np.testing.assert_allclose(tw2.sum(axis=1).to_numpy(), 0.6, rtol=1e-12)

    def test_inverse_vol_is_causal(self):
        rng = np.random.default_rng(7)
        dates = [f"2024-02-{d:02d}" for d in range(1, 9)]
        ra, rb = rng.normal(0, 0.01, 8), rng.normal(0, 0.02, 8)
        base = pf.combine([_sleeve("A", ra, dates), _sleeve("B", rb, dates)], "inverse_vol",
                          vol_window=3, rebalance="daily")
        k = 5
        rb2 = rb.copy()
        rb2[k] += 0.05
        alt = pf.combine([_sleeve("A", ra, dates), _sleeve("B", rb2, dates)], "inverse_vol",
                         vol_window=3, rebalance="daily")
        s0, s1 = _sig(base, "target_weight"), _sig(alt, "target_weight")
        pd.testing.assert_frame_equal(s0.iloc[: k + 1], s1.iloc[: k + 1])  # weights through k unchanged
        self.assertFalse(np.allclose(s0.iloc[k + 1], s1.iloc[k + 1]))  # only later sessions react
        v0, v1 = _sig(base, "sleeve_vol"), _sig(alt, "sleeve_vol")
        pd.testing.assert_frame_equal(v0.loc[: dates[k]], v1.loc[: dates[k]])

    def test_no_leverage_and_cash_never_negative(self):
        dates = [f"2024-03-{d:02d}" for d in range(1, 5)]
        a = _sleeve("A", [-1.0, -1.5, 0.2, 0.0], dates)
        b = _sleeve("B", [3.0, 3.0, -0.5, 0.0], dates)
        for reb in ("daily", "monthly"):
            t = pf.combine([a, b], "equal", rebalance=reb, rebalance_cost_bps=5.0)
            r, pos = t["returns"], _pos(t)
            self.assertTrue((r["equity"] >= 0).all())
            self.assertTrue((r["net_return"] >= -1.0).all())
            self.assertTrue((pos.to_numpy() >= 0).all())
            self.assertTrue((pos.sum(axis=1) <= 1 + 1e-12).all())
            self.assertTrue(np.isfinite(t["returns"][["gross_return", "net_return", "equity"]].to_numpy()).all())
        # Daily, session 1 with 0 cost: 0.5 * (-1) + 0.5 * 3 = 1.0 -> equity doubles; A cannot lose more than its weight.
        t = pf.combine([a, b], "equal", rebalance="daily", rebalance_cost_bps=0.0)
        self.assertAlmostEqual(t["returns"]["net_return"].iloc[0], 1.0, places=12)
        # Session 2: A at -150% is clamped at -100% (loses its 0.5 weight, no more).
        self.assertAlmostEqual(t["returns"]["net_return"].iloc[1], 0.5 * -1.0 + 0.5 * 3.0, places=12)
        rec = pf.reconcile(t, [a, b])
        self.assertGreaterEqual(rec["cash_min"], -1e-12)
        # Everything wiped out: equity floors at 0 and stays finite.
        z = pf.combine([_sleeve("A", [-1.0, 0.5, 0.5], D3), _sleeve("B", [-1.2, 0.5, 0.5], D3)],
                       "equal", rebalance="daily", rebalance_cost_bps=0.0)
        np.testing.assert_allclose(z["returns"]["equity"], 0.0, atol=1e-12)
        self.assertTrue(np.isfinite(z["positions"]["weight"]).all())

    def test_misaligned_dates_rejected_naming_first_difference(self):
        a = _sleeve("A", [0.0, 0.0, 0.0], D3)
        b = _sleeve("B", [0.0, 0.0, 0.0], ["2024-01-02", "2024-01-03", "2024-01-05"])
        with self.assertRaises(pf.PortfolioError) as cm:
            pf.combine([a, b], "equal")
        msg = str(cm.exception)
        self.assertIn("B", msg)
        self.assertIn("2024-01-04", msg)
        self.assertIn("2024-01-05", msg)
        short = _sleeve("C", [0.0, 0.0], D3[:2])
        with self.assertRaises(pf.PortfolioError) as cm:
            pf.combine([a, short], "equal")
        self.assertIn("C", str(cm.exception))

    def test_gross_validation_and_fewer_than_two_sleeves(self):
        a = _sleeve("A", [0.0, 0.0, 0.0], D3)
        b = _sleeve("B", [0.0, 0.0, 0.0], D3)
        for g in (0.0, -0.1, 1.0001, float("nan")):
            with self.assertRaises(pf.PortfolioError):
                pf.combine([a, b], "equal", gross=g)
        pf.combine([a, b], "equal", gross=1.0)
        with self.assertRaises(pf.PortfolioError):
            pf.combine([a], "equal")
        with self.assertRaises(pf.PortfolioError):
            pf.combine([], "equal")
        with self.assertRaises(pf.PortfolioError):
            pf.combine([a, b], "risk_parity")
        with self.assertRaises(pf.PortfolioError):
            pf.combine([a, b], "equal", rebalance="weekly")
        with self.assertRaises(pf.PortfolioError):
            pf.combine([a, a], "equal")  # duplicate component

    def test_zero_volatility_sleeve_named_in_error(self):
        dates = [f"2024-01-{d:02d}" for d in range(2, 8)]
        a = _sleeve("A", [0.01, -0.02, 0.015, 0.0, 0.01, -0.01], dates)
        flat = _sleeve("FLAT", [0.01] * 6, dates)
        with self.assertRaises(pf.PortfolioError) as cm:
            pf.combine([a, flat], "inverse_vol", vol_window=3, rebalance="daily")
        self.assertIn("FLAT", str(cm.exception))
        nan = _sleeve("NAN", [0.01, -0.02, float("nan"), 0.0, 0.01, -0.01], dates)
        with self.assertRaises(pf.PortfolioError):
            pf.combine([a, nan], "inverse_vol", vol_window=3, rebalance="daily")

    def test_combination_is_reproducible_bit_for_bit(self):
        rng = np.random.default_rng(3)
        dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2024-01-02", periods=90)]
        sl = [_sleeve("A", rng.normal(0, 0.01, 90), dates), _sleeve("B", rng.normal(0, 0.02, 90), dates)]
        one = pf.combine(sl, "inverse_vol", vol_window=20)
        two = pf.combine(sl, "inverse_vol", vol_window=20)
        for name in one:
            pd.testing.assert_frame_equal(one[name], two[name], check_exact=True)
        m1 = pf.build_manifest(sl, "inverse_vol", {"vol_window": 20}, one, NOW, "abc", exploratory=True)
        m2 = pf.build_manifest(sl, "inverse_vol", {"vol_window": 20}, two, NOW, "abc", exploratory=True)
        self.assertEqual(m1["config_hash"], m2["config_hash"])
        self.assertEqual(m1["run_id"], m2["run_id"])
        self.assertEqual(m1["config_hash"], config_hash(m1["config"]))

    def test_output_tables_pass_write_run_and_read_run(self):
        rng = np.random.default_rng(5)
        dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2024-01-02", periods=70)]
        sl = [_sleeve("A", rng.normal(0, 0.01, 70), dates, labels=["survivor-biased"], universe_kind="stock", use="financial"),
              _sleeve("B", rng.normal(0, 0.02, 70), dates, use="engineering")]
        tables = pf.combine(sl, "equal")
        manifest = pf.build_manifest(sl, "equal", {}, tables, NOW, "abc123", trial={"cycle_id": "c1", "trial_number": 4})
        self.assertEqual(manifest["engine"], "combiner")
        self.assertEqual(manifest["engine_version"], "combiner/v1")
        self.assertIsNone(manifest["parent_run"])
        self.assertEqual(manifest["labels"], ["survivor-biased"])
        self.assertEqual(manifest["universe_kind"], "stock")
        self.assertNotEqual(manifest.get("use"), "financial")  # engineering + financial -> not financial
        self.assertEqual(manifest["combination"]["trial"], {"cycle_id": "c1", "trial_number": 4})
        self.assertNotIn("exploratory", manifest["combination"])
        self.assertEqual(manifest["combination"]["components"], ["A", "B"])
        self.assertAlmostEqual(sum(manifest["combination"]["weights_first_rebalance"].values()), 1.0)
        with tempfile.TemporaryDirectory() as tmp:
            path = write_run(Path(tmp), manifest, tables)
            back, tabs = read_run(path)
            self.assertEqual(back["combination"], manifest["combination"])
            for name in tables:
                pd.testing.assert_frame_equal(tabs[name], tables[name], check_dtype=False)
            self.assertEqual(len(tabs["fills"]), 0)
            with self.assertRaises(Exception):
                write_run(Path(tmp), manifest, tables)  # exclusive
        # Every component financial -> financial; no trial and no exploratory flag -> refused.
        fin = [_sleeve("A", [0.0] * 3, D3, use="financial", acceptance_sha256="x"),
               _sleeve("B", [0.0] * 3, D3, use="financial", acceptance_sha256="x")]
        tf = pf.combine(fin, "equal")
        m = pf.build_manifest(fin, "equal", {}, tf, NOW, "c", exploratory=True)
        self.assertEqual(m["use"], "financial")
        self.assertTrue(m["combination"]["exploratory"])
        with self.assertRaises(pf.PortfolioError):
            pf.build_manifest(fin, "equal", {}, tf, NOW, "c")
        with self.assertRaises(pf.PortfolioError):
            pf.build_manifest(fin, "equal", {}, tf, NOW, "c", trial={"cycle_id": "c", "trial_number": 1}, exploratory=True)

    def test_reconcile_matches_returns(self):
        rng = np.random.default_rng(11)
        dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2024-01-02", periods=80)]
        sl = [_sleeve(n, rng.normal(0, s, 80), dates) for n, s in (("A", 0.01), ("B", 0.02), ("C", 0.015))]
        t = pf.combine(sl, "inverse_vol", vol_window=20, gross=0.9)
        rec = pf.reconcile(t, sl)
        self.assertEqual(set(rec), {"max_abs_return_error", "weights_sum_max", "cash_min", "cost_total"})
        self.assertLess(rec["max_abs_return_error"], 1e-12)
        # Drift can lift the invested share above gross (sleeves outgrow cash) but never past 1.
        self.assertLessEqual(rec["weights_sum_max"], 1.0)
        self.assertGreaterEqual(rec["cash_min"], 0.0)
        self.assertLessEqual(float(_sig(t, "target_weight").sum(axis=1).max()), 0.9 + 1e-12)
        self.assertAlmostEqual(rec["cost_total"], float(t["returns"]["cost"].sum()))
        self.assertGreater(rec["cost_total"], 0.0)
        bad = {k: v.copy() for k, v in t.items()}
        bad["returns"].loc[10, "gross_return"] += 0.01
        self.assertGreater(pf.reconcile(bad, sl)["max_abs_return_error"], 0.009)


if __name__ == "__main__":
    unittest.main()
