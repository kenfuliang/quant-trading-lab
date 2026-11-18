"""Offline tests of the truncate-and-compare lookahead check."""
import unittest
from unittest import mock

from research.evaluation import lookahead
from research.evaluation.lookahead import check_lookahead, truncate
from research.evaluation.market_model import Decision, MarketConfig, validate
from research.evaluation.parity_fixture import synthetic_fixture
from research.evaluation.strategies import INCUMBENT_SPEC, build_target_fn

CONFIG = MarketConfig()
# The incumbent's EMA200 leaves few assessed sessions in 250, so use shorter windows.
SMALL_INCUMBENT = {**INCUMBENT_SPEC, "fast": 5, "slow": 20, "vol_window": 5}


class LookaheadTests(unittest.TestCase):
    def test_sma_trend_and_incumbent_pass_on_fixture(self):
        data = synthetic_fixture()
        for spec in ({"name": "sma_trend", "window": 20, "gross": 0.95}, SMALL_INCUMBENT):
            result = check_lookahead(data, lambda spec=spec: build_target_fn(spec), CONFIG, cutoffs=4)
            self.assertEqual(result["status"], "pass", result["differences"])
            self.assertEqual(len(result["cutoffs"]), 4)
            self.assertNotIn(data.sessions[-1], result["cutoffs"])
            self.assertEqual(result["differences"], [])

    def test_planted_leak_fails(self):
        # The leak is a target function closed over the MarketData of the run it serves
        # (the harness records it), reading the close 5 sessions ahead. A closure over one
        # fixed full dataset leaks identically into both runs and cannot be detected by
        # truncation; a one-step leak is invisible because the truncated run's last
        # session is excluded.
        data = synthetic_fixture()
        holder = {}
        real_run = lookahead.run_screen

        def recording_run(run_data, target_fn, market):
            holder["data"] = run_data
            return real_run(run_data, target_fn, market)

        def factory():
            def leaky(session, history, holdings, equity):
                run_data = holder["data"]
                i = run_data.sessions.index(session)
                close = run_data.bars["AAA"]["close"]
                ahead = float(close.iloc[min(i + 5, len(close) - 1)])
                now = float(close.iloc[i])
                targets = {name: 0 for name in history}
                if ahead > now:
                    targets["AAA"] = int(0.9 * equity / now)
                return Decision(targets=targets, signals={("AAA", "trend"): ahead / now - 1})
            return leaky

        with mock.patch.object(lookahead, "run_screen", recording_run):
            result = check_lookahead(data, factory, CONFIG, cutoffs=4)
        self.assertEqual(result["status"], "fail")
        self.assertIn("signals", {d["table"] for d in result["differences"]})
        for diff in result["differences"]:
            self.assertGreater(diff["count"], 0)
            self.assertLess(diff["first_date"], diff["cutoff"])

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
