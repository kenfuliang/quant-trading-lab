"""Offline tests of the truncate-and-compare lookahead check."""
import unittest

from research.evaluation.lookahead import check_lookahead, truncate
from research.evaluation.market_model import Decision, MarketConfig, validate
from research.evaluation.parity_fixture import synthetic_fixture
from research.evaluation.strategies import INCUMBENT_SPEC, build_target_fn

CONFIG = MarketConfig()
# The incumbent's EMA200 leaves few assessed sessions in 250, so use shorter windows.
SMALL_INCUMBENT = {**INCUMBENT_SPEC, "fast": 5, "slow": 20, "vol_window": 5}


def _feature_factory(feature):
    """Factory whose target fn trades AAA on a feature precomputed from the data it receives."""

    def factory(data):
        series = feature(data.bars["AAA"]["close"])
        by_session = dict(zip(data.sessions, series))

        def target_fn(session, history, holdings, equity):
            value = float(by_session[session])
            close = float(history["AAA"]["close"].iloc[-1])
            targets = {name: 0 for name in history}
            if value > 0:
                targets["AAA"] = int(0.9 * equity / close)
            return Decision(targets=targets, signals={("AAA", "trend"): value})

        return target_fn

    return factory


class LookaheadTests(unittest.TestCase):
    def test_sma_trend_and_incumbent_pass_on_fixture(self):
        data = synthetic_fixture()
        for spec in ({"name": "sma_trend", "window": 20, "gross": 0.95}, SMALL_INCUMBENT):
            result = check_lookahead(data, lambda d, spec=spec: build_target_fn(spec), CONFIG, cutoffs=4)
            self.assertEqual(result["status"], "pass", result["differences"])
            self.assertEqual(len(result["cutoffs"]), 4)
            self.assertNotIn(data.sessions[-1], result["cutoffs"])
            self.assertEqual(result["differences"], [])

    def test_one_step_lookahead_feature_fails(self):
        # next session's close, from the data the run receives (shift(-1)); the truncated
        # run's last decision has no next close (NaN), so only the cutoff decision differs
        factory = _feature_factory(lambda close: close.shift(-1) / close - 1)
        result = check_lookahead(synthetic_fixture(), factory, CONFIG, cutoffs=4)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(all(d["first_date"] == d["cutoff"] for d in result["differences"]
                            if d["table"] == "decision"), result["differences"])
        self.assertIn("decision", {d["table"] for d in result["differences"]})

    def test_multi_step_lookahead_feature_fails(self):
        factory = _feature_factory(lambda close: close.shift(-5).fillna(close) / close - 1)
        result = check_lookahead(synthetic_fixture(), factory, CONFIG, cutoffs=4)
        self.assertEqual(result["status"], "fail")
        self.assertIn("signals", {d["table"] for d in result["differences"]})
        for diff in result["differences"]:
            self.assertGreater(diff["count"], 0)
            self.assertLessEqual(diff["first_date"], diff["cutoff"])

    def test_full_sample_normalisation_fails(self):
        factory = _feature_factory(lambda close: close / close.mean() - 1)
        result = check_lookahead(synthetic_fixture(), factory, CONFIG, cutoffs=4)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(result["differences"])

    def test_raising_target_fn_is_a_failure(self):
        def factory(data):
            def target_fn(session, history, holdings, equity):
                i = data.sessions.index(session)
                _ = data.bars["AAA"]["close"].iloc[i + 1]  # past the end on the last session
                return Decision(targets={name: 0 for name in history}, signals={})
            return target_fn

        result = check_lookahead(synthetic_fixture(), factory, CONFIG, cutoffs=3)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(all(d["table"] == "error" for d in result["differences"]))

    def test_truncate_drops_future_actions(self):
        data = synthetic_fixture()
        last = data.sessions[92]  # AAA dividend ex 90, pay 95
        cut = truncate(data, last)
        validate(cut)
        self.assertEqual(cut.sessions, data.sessions[:93])
        for name, frame in cut.bars.items():
            self.assertTrue(frame.equals(data.bars[name].iloc[:93]))
        self.assertTrue(all(d.pay_date <= last for d in cut.dividends))
        self.assertEqual(cut.splits, ())  # fixture split is at session 120
        late = truncate(data, data.sessions[130])
        self.assertEqual(late.splits, data.splits)
        # a dividend with ex <= last < pay is dropped (pending credit)
        pending = [d for d in data.dividends if d.ex_date <= last < d.pay_date]
        self.assertTrue(pending, "fixture should have a dividend pending at the cutoff")
        for d in pending:
            self.assertNotIn(d, cut.dividends)

    def test_truncate_rejects_non_session(self):
        with self.assertRaises(ValueError):
            truncate(synthetic_fixture(), "1999-01-01")


if __name__ == "__main__":
    unittest.main()
