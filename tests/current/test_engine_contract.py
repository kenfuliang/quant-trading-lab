import tempfile
import unittest
from pathlib import Path

from research.evaluation import screening_engine
from research.evaluation.engine_contract import EngineError, EngineResult, check_config, checked_targets
from research.evaluation.market_model import Decision, MarketConfig, sma_trend_targets
from research.evaluation.native_engine import run_native
from research.evaluation.parity import compare
from research.evaluation.parity_fixture import synthetic_fixture
from research.evaluation.run_output import COLUMNS, MANIFEST_KEYS, config_hash, read_run, write_run
from research.evaluation.screening_engine import run_screen
from tests.current.engine_helpers import hold_targets

NAMES = ("AAA", "BBB")


class CheckedTargetsTests(unittest.TestCase):
    def test_accepts_integral_values(self):
        self.assertEqual(checked_targets(Decision({"AAA": 10, "BBB": 3.0}, {}), NAMES), {"AAA": 10, "BBB": 3})

    def test_rejects_bad_values_without_truncating(self):
        for value in (10.7, float("nan"), float("inf"), True, -1, "5", None):
            with self.subTest(value=value), self.assertRaises(EngineError):
                checked_targets(Decision({"AAA": value}, {}), NAMES)

    def test_rejects_unknown_instrument(self):
        with self.assertRaisesRegex(EngineError, "unknown"):
            checked_targets(Decision({"ZZZ": 1}, {}), NAMES)

    def test_screening_engine_reexports_contract_types(self):
        self.assertIs(screening_engine.EngineError, EngineError)
        self.assertIs(screening_engine.EngineResult, EngineResult)

    def test_both_engines_reject_fractional_and_nan_targets(self):
        for value in (10.7, float("nan"), True):
            for engine in (run_screen, run_native):
                with self.subTest(value=value, engine=engine.__name__), self.assertRaises(EngineError):
                    engine(synthetic_fixture(), hold_targets({"AAA": value}), MarketConfig())


class MarketConfigTests(unittest.TestCase):
    def test_check_config_rejects_out_of_range_values(self):
        for config in (
            MarketConfig(initial_cash=0.0),
            MarketConfig(initial_cash=float("nan")),
            MarketConfig(cost_bps=-1.0),
            MarketConfig(cost_bps=float("inf")),
            MarketConfig(commission_usd=-1.0),
            MarketConfig(commission_usd=0.005),
        ):
            with self.subTest(config=config), self.assertRaises(EngineError):
                check_config(config)
        check_config(MarketConfig(commission_usd=0.0))

    def test_both_engines_reject_sub_cent_commission(self):
        for engine in (run_screen, run_native):
            with self.subTest(engine=engine.__name__), self.assertRaisesRegex(EngineError, "commission"):
                engine(synthetic_fixture(), hold_targets({"AAA": 10}), MarketConfig(commission_usd=0.005))

    def test_zero_commission_parity_passes(self):
        data, fn, cfg = synthetic_fixture(), sma_trend_targets(), MarketConfig(commission_usd=0.0)
        screen, native = run_screen(data, fn, cfg), run_native(data, fn, cfg)
        self.assertGreater(len(native.fills), 0)
        report = compare(screen, native)
        self.assertTrue(report.passed, report.mismatches)


class ResultTablesTests(unittest.TestCase):
    def test_flat_run_tables_are_typed_and_round_trip(self):
        for engine in (run_screen, run_native):
            result = engine(synthetic_fixture(), hold_targets({}), MarketConfig())
            self.assertTrue(result.fills.empty)
            manifest = {key: None for key in MANIFEST_KEYS}
            manifest.update(schema="run-output/v1", run_id="flat", config={}, config_hash=config_hash({}))
            with self.subTest(engine=result.engine), tempfile.TemporaryDirectory() as tmp:
                _, tables = read_run(write_run(Path(tmp), manifest, {n: getattr(result, n) for n in COLUMNS}))
                self.assertEqual(str(tables["fills"]["quantity"].dtype), "int64")


if __name__ == "__main__":
    unittest.main()
