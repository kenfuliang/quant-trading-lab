import unittest

from research.evaluation.market_model import MarketConfig, sma_trend_targets
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

    def test_engines_agree_when_holding_through_split_and_dividends(self):
        data, cfg = synthetic_fixture(), MarketConfig()
        fn = hold_targets({"AAA": 50, "BBB": 10, "CCC": 20})
        report = compare(run_screen(data, fn, cfg), run_native(data, fn, cfg))
        self.assertTrue(report.passed, report.mismatches)

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
