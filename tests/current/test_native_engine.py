import unittest
from dataclasses import replace
from unittest import mock

from nautilus_trader.model.currencies import USD
from nautilus_trader.model.objects import Money

from research.evaluation import native_engine
from research.evaluation.market_model import Dividend, MarketConfig, execution_price, sma_trend_targets
from research.evaluation.native_engine import run_native
from research.evaluation.parity_fixture import synthetic_fixture
from research.evaluation.run_output import COLUMNS
from research.evaluation.screening_engine import EngineError, run_screen
from tests.current.engine_helpers import hold_targets


class NativeEngineTests(unittest.TestCase):
    def test_runs_fixture_and_conserves_cash(self):
        result = run_native(synthetic_fixture(), sma_trend_targets(), MarketConfig())
        self.assertEqual(result.engine, "nautilus")
        self.assertEqual(len(result.returns), 250)
        self.assertGreater(len(result.fills), 0)
        self.assertTrue((result.cash >= 0).all())
        for name in COLUMNS:
            self.assertEqual(tuple(getattr(result, name).columns), COLUMNS[name])

    def test_split_doubles_holding_without_a_fill(self):
        result = run_native(synthetic_fixture(), hold_targets({"BBB": 10}), MarketConfig())
        pos = result.positions.set_index(["date", "instrument"]).quantity
        day = synthetic_fixture().splits[0].effective_date
        self.assertEqual(pos[(day, "BBB")], 20)
        self.assertFalse(((result.fills.date == day) & (result.fills.instrument == "BBB")).any())

    def test_split_orders_are_not_reported_and_cost_nothing(self):
        result = run_native(synthetic_fixture(), hold_targets({"BBB": 10}), MarketConfig())
        day = synthetic_fixture().splits[0].effective_date
        before = result.cash[synthetic_fixture().sessions[synthetic_fixture().sessions.index(day) - 1]]
        self.assertAlmostEqual(result.cash[day], before, places=2)

    def test_flat_through_split_and_dividend_changes_nothing(self):   # Review Focus 3
        result = run_native(synthetic_fixture(), hold_targets({}), MarketConfig())
        self.assertTrue((result.cash == 100_000.0).all())
        self.assertTrue((result.returns.equity == 100_000.0).all())

    def test_overspend_raises(self):                                   # Review Focus 1
        with self.assertRaises(EngineError):
            run_native(synthetic_fixture(), hold_targets({"AAA": 10_000_000}), MarketConfig())

    def test_bad_targets_raise(self):                                  # Review Focus 4
        for targets in ({"ZZZ": 1}, {"AAA": -1}):
            with self.subTest(targets=targets), self.assertRaises(EngineError):
                run_native(synthetic_fixture(), hold_targets(targets), MarketConfig())

    def test_first_fill_and_dividend_credit(self):
        data = synthetic_fixture()
        result = run_native(data, hold_targets({"AAA": 10}), MarketConfig())
        fill = result.fills.iloc[0]
        self.assertEqual((fill.date, fill.instrument, fill.side, fill.quantity), (data.sessions[1], "AAA", "BUY", 10))
        open_px = data.bars["AAA"]["open"].iloc[1]
        self.assertAlmostEqual(fill.cost, 1.0 + abs(fill.price - open_px) * 10)
        self.assertEqual(len(result.fills), 1)
        div = data.dividends[0]
        before = result.cash[data.sessions[data.sessions.index(div.pay_date) - 1]]
        self.assertAlmostEqual(result.cash[div.pay_date] - before, 0.40 * 10)

    def test_split_with_less_cash_than_one_commission_completes(self):
        data = synthetic_fixture()
        day = data.splits[0].effective_date
        ask = execution_price(float(data.bars["BBB"]["open"].iloc[1]), "BUY", MarketConfig().cost_bps)
        for leftover in (0.50, 0.00):
            config = MarketConfig(initial_cash=10 * ask + MarketConfig().commission_usd + leftover)
            with self.subTest(leftover=leftover):
                native = run_native(data, hold_targets({"BBB": 10}), config)
                screen = run_screen(data, hold_targets({"BBB": 10}), config)
                self.assertEqual(len(native.returns), 250)
                self.assertAlmostEqual(native.cash[day], screen.cash[day], delta=0.01)
                self.assertAlmostEqual(native.cash[day], leftover, delta=0.01)

    def test_denied_order_and_early_stop_surface_their_cause(self):
        data = synthetic_fixture()
        ask = execution_price(float(data.bars["BBB"]["open"].iloc[1]), "BUY", MarketConfig().cost_bps)
        config = MarketConfig(initial_cash=10 * ask + 1.0)

        def no_credit(self, name, side, quantity):
            self._submit(name, side, quantity, tags=[native_engine.SPLIT_TAG])

        original_filled = native_engine._ScreenStrategy._on_filled

        def refund_after_fill(self, event):
            order = self.cache.order(event.client_order_id)
            if native_engine.SPLIT_TAG in (order.tags or []):
                self.refund(Money(event.commission.as_double(), USD))
                return
            original_filled(self, event)

        with mock.patch.object(native_engine._ScreenStrategy, "_submit_split", no_credit):
            with self.assertRaisesRegex(EngineError, "not accepted"):
                run_native(data, hold_targets({"BBB": 10}), config)
            with mock.patch.object(native_engine._ScreenStrategy, "_on_filled", refund_after_fill):
                with self.assertRaisesRegex(EngineError, r"stopped the run early.*last order .*\[split\]"):
                    run_native(data, hold_targets({"BBB": 10}), replace(config, initial_cash=config.initial_cash + 0.5))

    def test_dividend_credit_is_rounded_to_cents(self):
        data = synthetic_fixture()
        div = Dividend("AAA", data.sessions[30], data.sessions[35], 0.1234)
        data = replace(data, dividends=(div,))
        result = run_native(data, hold_targets({"AAA": 7}), MarketConfig())
        before = result.cash[data.sessions[34]]
        self.assertEqual(round(result.cash[div.pay_date] - before, 6), 0.86)


if __name__ == "__main__":
    unittest.main()
