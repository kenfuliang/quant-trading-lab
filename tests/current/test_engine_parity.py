import unittest

from research.evaluation.market_model import (
    MarketConfig, MarketData, cost_bps, execution_price, sma_trend_targets)
from research.evaluation.native_engine import run_native
from research.evaluation.parity import compare
from research.evaluation.parity_fixture import synthetic_fixture
from research.evaluation.screening_engine import EngineResult, run_screen
from tests.current.engine_helpers import hold_targets


class EngineParityTests(unittest.TestCase):
    def test_engines_agree_on_synthetic_fixture(self):
        data, fn, cfg = synthetic_fixture(), sma_trend_targets(), MarketConfig()
        report = compare(run_screen(data, fn, cfg), run_native(data, fn, cfg))
        self.assertTrue(report.passed, report.mismatches)

    def test_engines_agree_with_adv_costs(self):
        # Per-instrument volume scales put the names in different tiers, and BBB crosses
        # tiers mid-run, so the bps varies per instrument and per session.
        data = synthetic_fixture()
        bars = {name: frame.copy() for name, frame in data.bars.items()}
        bars["AAA"]["volume"] *= 400.0
        bars["CCC"]["volume"] *= 0.05
        bars["BBB"].iloc[130:, bars["BBB"].columns.get_loc("volume")] *= 100.0
        data = MarketData(data.sessions, bars, data.dividends, data.splits)
        cfg = MarketConfig(cost_model="adv")
        seen = {cost_bps(data, n, i, cfg) for n in data.bars for i in range(len(data.sessions) - 1)}
        self.assertGreaterEqual(len(seen), 3, seen)
        fn = sma_trend_targets()
        screen, native = run_screen(data, fn, cfg), run_native(data, fn, cfg)
        report = compare(screen, native)
        self.assertTrue(report.passed, report.mismatches)
        self.assertGreater(len(screen.fills), 10)
        # fills use the tier computed at the decision session (fill session - 1)
        sessions = list(data.sessions)
        used = set()
        for row in screen.fills.itertuples():
            j = sessions.index(row.date)
            bps = cost_bps(data, row.instrument, j - 1, cfg)
            used.add(bps)
            expected = execution_price(float(data.bars[row.instrument]["open"].iloc[j]), row.side, bps)
            self.assertEqual(row.price, expected)
        self.assertGreaterEqual(len(used), 2, used)
        self.assertFalse(screen.fills["price"].equals(run_screen(data, fn, MarketConfig()).fills["price"]))

    def test_engines_agree_when_holding_through_split_and_dividends(self):
        data, cfg = synthetic_fixture(), MarketConfig()
        fn = hold_targets({"AAA": 50, "BBB": 10, "CCC": 20})
        report = compare(run_screen(data, fn, cfg), run_native(data, fn, cfg))
        self.assertTrue(report.passed, report.mismatches)

    def test_split_with_indivisible_close_moves_no_cash(self):
        # 3:1 split whose pre-split close is not divisible by 3 cents: the R11 rule says a
        # whole-share forward split moves no cash in either engine.
        data, cfg = synthetic_fixture(split_ratio=3, divisible_split_close=False), MarketConfig()
        split = data.splits[0]
        i = data.sessions.index(split.effective_date)
        self.assertEqual(split.ratio, 3)
        self.assertNotEqual(round(data.bars["BBB"]["close"].iloc[i - 1] * 100) % 3, 0)
        fn = hold_targets({"AAA": 50, "BBB": 10, "CCC": 20})
        screen, native = run_screen(data, fn, cfg), run_native(data, fn, cfg)
        report = compare(screen, native)
        self.assertTrue(report.passed, report.mismatches)
        day, before = split.effective_date, data.sessions[i - 1]
        for result in (screen, native):
            with self.subTest(engine=result.engine):
                pos = result.positions.set_index(["date", "instrument"]).quantity
                self.assertEqual(pos[(day, "BBB")], 30)
                self.assertEqual(result.cash[day], result.cash[before])

    def test_comparator_reports_a_real_difference(self):
        data, fn = synthetic_fixture(), sma_trend_targets()
        report = compare(run_screen(data, fn, MarketConfig()), run_native(data, fn, MarketConfig(cost_bps=6.0)))
        self.assertFalse(report.passed)
        self.assertTrue(any("price" in m for m in report.mismatches))

    def test_comparator_names_session_and_field_for_cash(self):
        data, fn, cfg = synthetic_fixture(), sma_trend_targets(), MarketConfig()
        a = run_screen(data, fn, cfg)
        self.assertTrue(compare(a, run_screen(data, fn, cfg)).passed)
        cash = a.cash.copy()
        cash.iloc[3] += 0.5
        bad = EngineResult(a.engine, a.returns, a.positions, a.signals, a.fills, cash)
        report = compare(a, bad)
        self.assertFalse(report.passed)
        day = str(a.cash.index[3])
        self.assertTrue(any(m.startswith(day) and "cash" in m for m in report.mismatches), report.mismatches)

    def test_non_finite_cash_or_equity_is_a_mismatch(self):
        data, fn, cfg = synthetic_fixture(), sma_trend_targets(), MarketConfig()
        a = run_screen(data, fn, cfg)
        cash = a.cash.copy().astype(float)
        cash.iloc[2] = float("nan")
        bad_cash = EngineResult(a.engine, a.returns, a.positions, a.signals, a.fills, cash)
        report = compare(a, bad_cash)
        self.assertTrue(any(m.startswith(str(a.cash.index[2])) and "cash" in m for m in report.mismatches))
        returns = a.returns.copy()
        returns.loc[4, "equity"] = float("nan")
        bad_eq = EngineResult(a.engine, returns, a.positions, a.signals, a.fills, a.cash)
        report = compare(a, bad_eq)
        self.assertTrue(any(m.startswith(str(a.returns["date"].iloc[4])) and "equity" in m for m in report.mismatches))

    def test_sub_cent_price_difference_is_a_mismatch(self):
        data, fn, cfg = synthetic_fixture(), sma_trend_targets(), MarketConfig()
        a = run_screen(data, fn, cfg)
        fills = a.fills.copy()
        fills.loc[0, "price"] = fills.loc[0, "price"] + 0.004
        bad = EngineResult(a.engine, a.returns, a.positions, a.signals, fills, a.cash)
        report = compare(a, bad)
        self.assertFalse(report.passed)
        self.assertTrue(any("price" in m for m in report.mismatches), report.mismatches)
