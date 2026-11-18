import unittest

from research.evaluation.market_model import MarketConfig, sma_trend_targets
from research.evaluation.parity_fixture import synthetic_fixture
from research.evaluation.run_output import COLUMNS
from research.evaluation.screening_engine import EngineError, run_screen
from tests.current.engine_helpers import hold_targets


class ScreeningEngineTests(unittest.TestCase):
    def test_runs_fixture_and_conserves_cash(self):
        result = run_screen(synthetic_fixture(), sma_trend_targets(), MarketConfig())
        self.assertEqual(result.engine, "screen")
        self.assertEqual(len(result.returns), 250)
        self.assertGreater(len(result.fills), 0)
        self.assertTrue((result.cash >= 0).all())
        for name in COLUMNS:
            self.assertEqual(tuple(getattr(result, name).columns), COLUMNS[name])

    def test_split_doubles_holding_without_a_fill(self):
        result = run_screen(synthetic_fixture(), hold_targets({"BBB": 10}), MarketConfig())
        pos = result.positions.set_index(["date", "instrument"]).quantity
        day = synthetic_fixture().splits[0].effective_date
        self.assertEqual(pos[(day, "BBB")], 20)
        self.assertFalse(((result.fills.date == day) & (result.fills.instrument == "BBB")).any())

    def test_flat_through_split_and_dividend_changes_nothing(self):
        result = run_screen(synthetic_fixture(), hold_targets({}), MarketConfig())
        self.assertTrue((result.cash == 100_000.0).all())
        self.assertTrue((result.returns.equity == 100_000.0).all())

    def test_overspend_raises(self):
        with self.assertRaises(EngineError):
            run_screen(synthetic_fixture(), hold_targets({"AAA": 10_000_000}), MarketConfig())

    def test_bad_targets_raise(self):
        for targets in ({"ZZZ": 1}, {"AAA": -1}):
            with self.subTest(targets=targets), self.assertRaises(EngineError):
                run_screen(synthetic_fixture(), hold_targets(targets), MarketConfig())

    def test_first_fill_and_dividend_credit(self):
        data = synthetic_fixture()
        result = run_screen(data, hold_targets({"AAA": 10}), MarketConfig())
        fill = result.fills.iloc[0]
        self.assertEqual((fill.date, fill.instrument, fill.side, fill.quantity), (data.sessions[1], "AAA", "BUY", 10))
        open_px = data.bars["AAA"]["open"].iloc[1]
        self.assertAlmostEqual(fill.cost, 1.0 + abs(fill.price - open_px) * 10)
        self.assertEqual(len(result.fills), 1)
        div = data.dividends[0]
        before = result.cash[data.sessions[data.sessions.index(div.pay_date) - 1]]
        self.assertAlmostEqual(result.cash[div.pay_date] - before, 0.40 * 10)


if __name__ == "__main__":
    unittest.main()
