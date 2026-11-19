"""Point-in-time masking: causal, per decision date, recorded as the universe signal stage."""
import unittest

from research.evaluation.lookahead import check_lookahead
from research.evaluation.market_model import Decision, MarketConfig
from research.evaluation.parity_fixture import synthetic_fixture
from research.evaluation.screening_engine import run_screen
from research.evaluation.strategies import build_target_fn
from research.evaluation.universe import LABELS, UNIVERSE_SIGNAL, members_only


def all_in(session, bars, holdings, equity):
    return Decision(targets={name: 5 for name in bars}, signals={("AAA", "trend"): 1.0})


class UniverseTests(unittest.TestCase):
    def test_labels_constant(self):
        self.assertEqual(LABELS, ("survivor-biased", "discovery-only"))

    def test_members_only_masks_non_members_causally(self):
        intervals = {"AAA": [{"start": "2024-01-02", "end": None}],
                     "BBB": [{"start": "2024-03-01", "end": "2024-04-30"}],
                     "CCC": [{"start": "2024-05-01", "end": None}]}
        fn = members_only(all_in, intervals)
        before = fn("2024-02-29", {"AAA": None, "BBB": None, "CCC": None}, {}, 1.0)
        self.assertEqual(before.targets, {"AAA": 5, "BBB": 0, "CCC": 0})
        self.assertEqual(before.signals[UNIVERSE_SIGNAL], 2.0)
        self.assertEqual(before.signals[("AAA", "trend")], 1.0)  # the wrapped signals stay
        first = fn("2024-03-01", {"AAA": None, "BBB": None, "CCC": None}, {}, 1.0)
        self.assertEqual(first.targets, {"AAA": 5, "BBB": 5, "CCC": 0})
        last = fn("2024-04-30", {"AAA": None, "BBB": None, "CCC": None}, {}, 1.0)
        self.assertEqual(last.targets["BBB"], 5)
        gone = fn("2024-05-01", {"AAA": None, "BBB": None, "CCC": None}, {}, 1.0)
        self.assertEqual(gone.targets, {"AAA": 5, "BBB": 0, "CCC": 5})
        # membership that begins tomorrow does not count today, and one that ended yesterday does not either
        self.assertEqual(before.targets["CCC"], 0)

    def test_a_later_membership_row_cannot_change_an_earlier_decision(self):
        base = {"AAA": [{"start": "2024-01-02", "end": None}], "BBB": [{"start": "2024-01-02", "end": "2024-02-01"}]}
        extended = {"AAA": base["AAA"], "BBB": [{"start": "2024-01-02", "end": "2024-02-01"}],
                    "CCC": [{"start": "2024-06-03", "end": None}]}
        bars = {"AAA": None, "BBB": None, "CCC": None}
        a = members_only(all_in, base)("2024-01-31", bars, {}, 1.0)
        b = members_only(all_in, extended)("2024-01-31", bars, {}, 1.0)
        self.assertEqual(a.targets, b.targets)

    def test_the_masked_run_trades_only_members_and_passes_lookahead(self):
        data = synthetic_fixture()
        sessions = data.sessions
        intervals = {"AAA": [{"start": sessions[0], "end": None}], "BBB": [{"start": sessions[100], "end": sessions[180]}],
                     "CCC": []}
        strategy = {"name": "buy_hold", "gross": 0.95}

        def wrapped(_data=None):
            return members_only(build_target_fn(strategy), intervals)

        result = run_screen(data, wrapped(), MarketConfig(cost_bps=0, commission_usd=0))
        fills = result.fills
        self.assertEqual(set(fills["instrument"]), {"AAA", "BBB"})
        self.assertGreater(fills[fills["instrument"] == "BBB"]["date"].min(), sessions[100])  # t+1 fill
        stage = result.signals[result.signals["stage"] == "universe"]
        self.assertEqual(len(stage), len(sessions) - 1)
        self.assertEqual(set(stage["value"]), {1.0, 2.0})
        look = check_lookahead(data, lambda d: wrapped(), MarketConfig(), cutoffs=3)
        self.assertEqual(look["status"], "pass")
        self.assertTrue(all(c["compared_signals"] > 0 for c in look["compared"]))


if __name__ == "__main__":
    unittest.main()
