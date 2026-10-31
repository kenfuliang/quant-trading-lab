"""Invented monthly observations only; no portfolio simulation or market inputs."""
from copy import deepcopy
import unittest

import numpy as np
import pandas as pd

from research.studies.residual_momentum.selector import score_month


def fixture():
    months = pd.period_range("2017-01", periods=40, freq="M")
    rng = np.random.default_rng(773)
    factors = pd.DataFrame(rng.normal(0, .02, (40, 3)), index=months,
                           columns=["mkt_rf", "smb", "hml"])
    factors["rf"] = .001
    design = np.column_stack([np.ones(36), factors.iloc[:36, :3]])
    noise = np.sin(np.arange(36) * .8) * .01
    # Orthogonal synthetic residual gives a known intercept and slope vector.
    residual = noise - design @ np.linalg.lstsq(design, noise, rcond=None)[0]
    values = design @ np.array([.006, 1.1, -.3, .2]) + .001 + residual
    returns = pd.DataFrame({"AAA": np.r_[values, [.02] * 4],
                            "BBB": np.r_[values + .01, [.02] * 4]}, index=months)
    times = pd.Series([p.end_time.tz_localize("UTC") + pd.Timedelta(days=1)
                       for p in months], index=months)
    stock_times = pd.DataFrame({c: times.copy() for c in returns.columns}).copy(deep=True)
    return returns, factors, stock_times, times, residual


def score(inputs):
    return score_month(*inputs[:4], formation_month="2020-01",
                       decision_time="2020-01-03T16:00:00Z")


class ResidualMomentumSelectorTests(unittest.TestCase):
    def test_known_coefficients_and_11_month_score_exclude_alpha(self):
        inputs = fixture()
        result = score(inputs)
        self.assertAlmostEqual(result["coefficients"]["AAA"]["alpha"], .006)
        self.assertAlmostEqual(result["coefficients"]["AAA"]["mkt_rf"], 1.1)
        signal = inputs[4][24:35]
        expected = signal.sum() / np.std(signal, ddof=1)
        self.assertAlmostEqual(result["scores"]["AAA"]["residual"], expected)
        # Constant alpha changes must not change residual rank scores.
        self.assertAlmostEqual(result["scores"]["BBB"]["residual"], expected)
        self.assertFalse(result["qualified_for_financial_run"])
        self.assertFalse(result["authorizes_orders"])

    def test_future_return_factor_and_publication_changes_do_not_change_prefix(self):
        original = fixture()
        expected = score(original)
        changed = deepcopy(original)
        changed[0].iloc[36:, :] = 100
        changed[1].iloc[36:, :] = np.nan
        changed[2].iloc[36:, :] = pd.NaT
        changed[3].iloc[36:] = pd.NaT
        self.assertEqual(score(changed), expected)

    def test_factors_not_published_at_cutoff_block_proposal(self):
        inputs = fixture()
        inputs[3].iloc[35] = pd.Timestamp("2020-01-04T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "not available"):
            score(inputs)

    def test_missing_stock_and_late_stock_exclude_from_all_controls(self):
        for late in (False, True):
            inputs = fixture()
            if late:
                inputs[2].loc["2019-12", "AAA"] = pd.Timestamp("2020-02-01T00:00:00Z")
            else:
                inputs[0].loc["2019-01", "AAA"] = np.nan
            result = score(inputs)
            self.assertIn("AAA", result["excluded"])
            self.assertEqual(result["eligible"], ["BBB"])
            for weights in result["weights"].values():
                self.assertEqual(weights, {"BBB": 1.0})

    def test_missing_month_and_duplicates_never_impute(self):
        inputs = fixture()
        bad_factors = inputs[1].drop(pd.Period("2018-02", "M"))
        bad_times = inputs[3].reindex(bad_factors.index)
        with self.assertRaisesRegex(ValueError, "36 contiguous"):
            score((inputs[0], bad_factors, inputs[2], bad_times))
        duplicate = pd.concat([inputs[0], inputs[0].iloc[:1]])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            score((duplicate, inputs[1], inputs[2], inputs[3]))

    def test_rank_deficient_and_zero_residual_variance_fail_explicitly(self):
        inputs = fixture()
        inputs[1]["hml"] = inputs[1]["smb"]
        with self.assertRaisesRegex(ValueError, "Rank-deficient"):
            score(inputs)
        inputs = fixture()
        inputs[0].loc[:, :] = np.repeat(
            (.001 + .01 + inputs[1]["mkt_rf"]).to_numpy()[:, None], 2, axis=1)
        result = score(inputs)
        self.assertEqual(result["status"], "no_eligible_targets")
        self.assertEqual(set(result["excluded"].values()), {"zero_residual_volatility"})
        self.assertTrue(all(not w for w in result["weights"].values()))

    def test_naive_and_missing_availability_never_assume_publication(self):
        inputs = fixture()
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            score_month(*inputs[:4], formation_month="2020-01", decision_time="2020-01-03")
        inputs[3].iloc[0] = pd.NaT
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            score(inputs)

    def test_returns_units_and_schema_validation(self):
        inputs = fixture()
        inputs[0].loc["2018-01", "AAA"] = -2
        result = score(inputs)
        self.assertEqual(result["excluded"]["AAA"], "invalid_or_missing_returns")
        with self.assertRaisesRegex(ValueError, "align exactly"):
            score((inputs[0], inputs[1], inputs[2].iloc[1:], inputs[3]))
        with self.assertRaisesRegex(ValueError, "Missing"):
            score((inputs[0], inputs[1].drop(columns="rf"), inputs[2], inputs[3]))

    def test_decile_breadth_lexical_ties_and_inputs_preserved(self):
        original = fixture()
        returns = pd.concat([original[0]["AAA"].rename(f"S{i:02d}") for i in range(13)], axis=1)
        availability = pd.DataFrame({s: original[3].copy() for s in returns.columns})
        before = returns.copy(deep=True)
        result = score((returns, original[1], availability, original[3]))
        pd.testing.assert_frame_equal(returns, before)
        self.assertEqual(result["weights"]["residual"], {"S00": .5, "S01": .5})
        self.assertEqual(result["weights"]["ordinary"], {"S00": .5, "S01": .5})
        self.assertEqual(len(result["weights"]["equal_weight"]), 13)
        for weights in result["weights"].values():
            self.assertAlmostEqual(sum(weights.values()), 1)


if __name__ == "__main__":
    unittest.main()
