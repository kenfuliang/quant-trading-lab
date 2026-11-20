"""Offline tests of the candidate confirmation core."""
import copy
import dataclasses
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from research.control import run_refs
from research.evaluation import confirm as core
from research.evaluation.ladder import Rung, run_ladder
from research.evaluation.market_model import MarketConfig
from research.evaluation.parity_fixture import synthetic_fixture
from research.evaluation.run_output import read_run, write_run
from research.evaluation.screening_engine import run_screen
from research.evaluation.strategies import build_target_fn

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
SPEC = {"name": "ema_trend", "fast": 10, "slow": 30, "gross": 0.99}
SHA = "a" * 64
DATASETS = {"dataset_id": "d", "manifest_sha256": SHA, "quality_status": "pass"}
FINANCIAL = {"use": "financial", "acceptance_sha256": "b" * 64}


class ConfirmCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = synthetic_fixture()
        cls.market = MarketConfig()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        base = {"code_commit": "c" * 40, "datasets": DATASETS, **FINANCIAL}
        results = run_ladder(cls.data, [Rung("trend", SPEC, cls.market)], cls.root, base, NOW)
        cls.manifest, cls.tables = read_run(cls.root / results[0]["run_id"])
        cls.target_fn = staticmethod(build_target_fn(SPEC))
        cls.confirmation = core.confirm(cls.data, cls.target_fn, cls.market, cls.tables)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_candidate_from_manifest_rebuilds_inputs(self):
        candidate = core.candidate_from_manifest(self.manifest)
        self.assertEqual(candidate["strategy"], SPEC)
        self.assertEqual(candidate["market"], self.market)
        self.assertEqual(candidate["instruments"], tuple(self.data.bars))
        self.assertIsNone(candidate["universe"])
        self.assertEqual(candidate["datasets"], DATASETS)
        masked = copy.deepcopy(self.manifest)
        masked["config"]["universe"] = {"membership_id": "m", "identity_id": "i"}
        self.assertEqual(core.candidate_from_manifest(masked)["universe"], {"membership_id": "m", "identity_id": "i"})
        adv = copy.deepcopy(self.manifest)
        adv["config"]["market"] = {"initial_cash": 1e5, "cost_bps": 5.0, "commission_usd": 1.0,
                                   "cost_model": "adv", "adv_tiers": [[1e9, 1.0], [0, 5.0]]}
        self.assertEqual(core.candidate_from_manifest(adv)["market"].cost_model, "adv")

    def test_non_screen_or_incomplete_manifest_refused(self):
        native = copy.deepcopy(self.manifest)
        native["engine"] = "nautilus"
        parity_style = copy.deepcopy(self.manifest)
        del parity_style["config"]["strategy"]["gross"]
        incomplete = copy.deepcopy(self.manifest)
        del incomplete["config"]["instruments"]
        combiner = copy.deepcopy(self.manifest)
        combiner["config"] = {"engine": "combine", "sleeves": []}
        combiner["engine"] = "combine"
        halfmasked = copy.deepcopy(self.manifest)
        halfmasked["config"]["universe"] = {"membership_id": "m"}
        for bad, pattern in ((native, "only a screen run"), (incomplete, "missing"),
                             (combiner, "only a screen run"), (halfmasked, "membership_id")):
            with self.subTest(pattern=pattern), self.assertRaisesRegex(core.ConfirmError, pattern):
                core.candidate_from_manifest(bad)

    def test_confirm_passes_on_fixture_and_returns_identical_flag(self):
        c = self.confirmation
        self.assertTrue(c.stored_identical)
        self.assertTrue(c.report.passed, c.report.mismatches)
        self.assertEqual(c.native.engine, "nautilus")
        self.assertEqual(len(c.native.returns), 250)
        self.assertGreater(c.screen_seconds, 0)
        self.assertGreater(c.native_seconds, 0)

    def test_changed_stored_run_is_refused_naming_table_and_date(self):
        for table, column in (("returns", "equity"), ("fills", "price"), ("signals", "value")):
            tables = {name: frame.copy() for name, frame in self.tables.items()}
            tables[table].loc[3, column] += 0.5
            day = tables[table]["date"][3]
            with self.subTest(table=table), self.assertRaises(core.ConfirmError) as ctx:
                core.confirm(self.data, self.target_fn, self.market, tables,
                             run_native_fn=lambda *a: self.fail("native must not run"))
            message = str(ctx.exception)
            self.assertIn("not reproducible", message)
            self.assertIn(table, message)
            self.assertIn(day, message)
        short = {name: frame.copy() for name, frame in self.tables.items()}
        short["returns"] = short["returns"].iloc[:-1]
        with self.assertRaisesRegex(core.ConfirmError, "returns"):
            core.confirm(self.data, self.target_fn, self.market, short)

    def test_native_manifest_satisfies_rule3_binding(self):
        manifest = core.native_manifest(self.manifest, self.confirmation.native, code_commit="d" * 40,
                                        now=NOW, engine_version="nautilus_trader test")
        self.assertEqual(manifest["engine"], "nautilus")
        self.assertEqual(manifest["config"]["engine"], "nautilus")
        self.assertNotIn("ladder", manifest["config"])
        self.assertEqual(manifest["parent_run"], self.manifest["run_id"])
        self.assertEqual(manifest["code_commit"], "d" * 40)
        run_refs.require_nautilus_run(manifest, self.manifest)  # same checks Plan 6 rule 3 makes
        for key in run_refs.BOUND_CONFIG_KEYS:
            self.assertEqual(manifest["config"][key], self.manifest["config"][key])
        self.assertEqual(manifest["datasets"]["manifest_sha256"], self.manifest["datasets"]["manifest_sha256"])
        with tempfile.TemporaryDirectory() as tmp:  # write_run and read_run tolerate every copied key
            native = self.confirmation.native
            tables = {name: getattr(native, name)[list(cols)] for name, cols in core.COLUMNS.items()}
            read, _ = read_run(write_run(Path(tmp), manifest, tables))
            self.assertEqual(read["engine"], "nautilus")
        drifted = copy.deepcopy(manifest)
        drifted["config"]["instruments"] = ["X"]
        with self.assertRaisesRegex(Exception, "instruments"):
            run_refs.require_nautilus_run(drifted, self.manifest)

    def test_native_manifest_copies_use_labels_and_acceptance(self):
        screen = dict(self.manifest, labels=["survivor-biased"], universe_kind="current-holdings-proxy")
        manifest = core.native_manifest(screen, self.confirmation.native, code_commit="d" * 40,
                                        now=NOW, engine_version="v")
        self.assertEqual((manifest["use"], manifest["acceptance_sha256"]), ("financial", "b" * 64))
        self.assertEqual(manifest["labels"], ["survivor-biased"])
        self.assertEqual(manifest["universe_kind"], "current-holdings-proxy")
        engineering = {k: v for k, v in self.manifest.items() if k not in ("use", "acceptance_sha256")}
        plain = core.native_manifest(engineering, self.confirmation.native, code_commit="d" * 40, now=NOW,
                                     engine_version="v")
        for key in core.COPIED_KEYS:
            self.assertNotIn(key, plain)

    def test_mismatch_is_reported_not_raised(self):
        def perturbed(data, target_fn, market):
            native = run_screen(data, target_fn, market)
            fills = native.fills.copy()
            fills.loc[0, "price"] += 0.05
            return dataclasses.replace(native, engine="nautilus", fills=fills)

        c = core.confirm(self.data, self.target_fn, self.market, self.tables, run_native_fn=perturbed)
        self.assertFalse(c.report.passed)
        self.assertTrue(c.stored_identical)
        receipt = self._receipt(c)
        self.assertEqual((receipt["status"], receipt["passed"]), ("mismatch", False))
        self.assertEqual(receipt["mismatch_count"], len(c.report.mismatches))
        self.assertIn("fills price", receipt["mismatches"][0])
        with self.assertRaisesRegex(Exception, "did not pass"):
            run_refs.require_passed_parity(receipt)

    def _receipt(self, confirmation, **overrides):
        args = dict(parity_id="P1", now=NOW, command=["scripts/confirm.py", "--run-id", "R"],
                    code_commit="e" * 40, screen_manifest=self.manifest, screen_sha256="1" * 64,
                    native_run_id="N1", native_sha256="2" * 64, confirmation=confirmation,
                    runs_root="/runs")
        return core.build_receipt(**{**args, **overrides})

    def test_receipt_shape_and_rule3_parity_checks(self):
        receipt = self._receipt(self.confirmation)
        engine_parity_keys = {
            "schema", "parity_id", "run_id", "created_utc", "use", "command", "code_commit", "inputs",
            "instruments", "max_instruments", "timing_only", "strategy", "market", "tolerances",
            "cash_interest", "runs_root", "calendar", "timing", "runs", "status", "passed",
            "mismatch_count", "mismatches", "error"}
        self.assertTrue(engine_parity_keys <= set(receipt))
        self.assertEqual(receipt["schema"], "parity-receipt/v1")
        self.assertEqual(receipt["kind"], "candidate-confirmation")
        self.assertEqual(receipt["status"], "passed")
        self.assertEqual(receipt["runs"]["screen"]["run_id"], self.manifest["run_id"])
        self.assertEqual(receipt["runs"]["nautilus"]["run_id"], "N1")
        self.assertEqual(receipt["run_use"], "financial")
        self.assertEqual(receipt["acceptance_sha256"], "b" * 64)
        self.assertTrue(receipt["stored_screen_identical"])
        self.assertTrue(receipt["bindable"])
        self.assertEqual(receipt["candidate"]["ladder"]["rung"], "trend")
        run_refs.require_passed_parity(receipt)
        with self.assertRaisesRegex(Exception, "dirty"):
            run_refs.require_passed_parity(self._receipt(self.confirmation, code_commit="e" * 40 + "+dirty"))
        unhashed = {k: v for k, v in self.manifest.items() if k not in ("use", "acceptance_sha256")}
        unhashed["datasets"] = {"dataset_id": "synthetic"}
        engineering = self._receipt(self.confirmation, screen_manifest=unhashed)
        self.assertFalse(engineering["bindable"])
        for key in ("run_use", "acceptance_sha256"):
            self.assertNotIn(key, engineering)
        self.assertIn("not financial use", engineering["use"])


if __name__ == "__main__":
    unittest.main()
