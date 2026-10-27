"""Offline migration guarantees, independent of any historical research budget."""
import ast
from dataclasses import asdict
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / 'research/compatibility.json').read_text())


class PackageCompatibilityTests(unittest.TestCase):
    def test_frozen_compatibility_files_are_byte_identical(self):
        for name, expected in MANIFEST['protected_files'].items():
            with self.subTest(path=name):
                self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected)

    def test_all_canonical_modules_import_and_have_own_implementations(self):
        old_modules = {p[:-3].replace('/', '.') for p in MANIFEST['modules']}
        for old, entry in MANIFEST['modules'].items():
            canonical = entry['canonical_path']
            with self.subTest(path=canonical):
                module = importlib.import_module(canonical[:-3].replace('/', '.'))
                self.assertEqual(Path(module.__file__).resolve(), ROOT / canonical)
                tree = ast.parse((ROOT / canonical).read_text())
                self.assertTrue(any(isinstance(n, (ast.FunctionDef, ast.ClassDef)) for n in tree.body))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        self.assertNotIn(node.module, old_modules)
                        self.assertFalse(node.module == 'research' and any(
                            'research.' + name.name in old_modules for name in node.names))
                    if isinstance(node, ast.Import):
                        self.assertFalse(any(n.name in old_modules for n in node.names))

    def test_catalogue_resource_and_repository_root_are_not_relocated(self):
        from research.control import catalogue
        from research.studies.spy import bounded_study
        from research import catalogue as legacy_catalogue
        self.assertEqual(catalogue.load_catalogue(), legacy_catalogue.load_catalogue())
        self.assertEqual(bounded_study.ROOT, ROOT)
        for name in bounded_study.CODE_FILES:
            self.assertTrue((ROOT / name).is_file(), name)

    def test_current_code_identity_rejects_legacy_plan_without_execution(self):
        from research import bounded_study as legacy
        from research.studies.spy import bounded_study as current
        self.assertNotEqual(legacy.current_code_hashes(), current.current_code_hashes())
        # Reuse the existing synthetic fixture, not a historical financial study.
        from current.test_bounded_study import BoundedStudyTests
        fixture = BoundedStudyTests()
        fixture.setUp()
        try:
            plan = dict(fixture.plan, code_hashes=legacy.current_code_hashes())
            with self.assertRaises(ValueError):
                current.preflight(plan)
            current.preflight(fixture.plan)
            self.assertEqual(sorted(p.name for p in fixture.root.iterdir()), ['source.json'])
        finally:
            fixture.doCleanups()

    def test_gate_defaults_cannot_reserve_historical_state_or_plans(self):
        from research.studies.spy import risk_gate_study as current
        from research import risk_gate_study as legacy
        self.assertNotEqual(current.STATE, legacy.STATE)
        self.assertNotEqual(current.PLAN, legacy.PLAN)
        self.assertEqual(current.PLAN.parts[:3], ('research', 'plans', 'current'))
        self.assertEqual(current.ROOT, ROOT)
        from research.evaluation import etf_readiness_probe as current_probe
        from research import etf_readiness_probe as legacy_probe
        self.assertNotEqual(current_probe.STATE, legacy_probe.STATE)

    def test_legacy_and_current_ledgers_scores_and_report_rows_match(self):
        from research import risk_gate as legacy_gate, leveraged_spy as legacy_ledger
        from research.policies import risk_gate as current_gate
        from research.evaluation import leveraged_spy as current_ledger
        from research import spy_report as legacy_report
        from research.studies.spy import spy_report as current_report
        n = 320
        prices = 100 + np.arange(n) * .03 + 6 * np.sin(np.arange(n) / 20)
        raw = pd.DataFrame(dict(open=prices, close=prices, high=prices+1, low=prices-1),
                           index=pd.bdate_range('2019-01-01', periods=n))
        before, timeline_before = legacy_gate.frames(raw)
        after, timeline_after = current_gate.frames(raw)
        pd.testing.assert_frame_equal(timeline_before, timeline_after)
        self.assertEqual(asdict(legacy_ledger.FinancingModel()), asdict(current_ledger.FinancingModel()))
        for name in ('hold', 'ema', 'gate_ema'):
            with self.subTest(case=name):
                pd.testing.assert_frame_equal(before[name], after[name])
                frame = before[name].iloc[-100:].copy()
                frame.index = frame.index.strftime('%Y-%m-%d')
                dividends = {frame.index[20]: .25}
                left, left_trades = legacy_ledger.simulate(frame, dividends, 'trend', 1.)
                right, right_trades = current_ledger.simulate(frame, dividends, 'trend', 1.)
                pd.testing.assert_frame_equal(left, right)
                pd.testing.assert_frame_equal(left_trades, right_trades)
                self.assertEqual(legacy_ledger.score_rows(left, legacy_ledger.FinancingModel(), name, 'trend', 1.),
                                 current_ledger.score_rows(right, current_ledger.FinancingModel(), name, 'trend', 1.))
                pd.testing.assert_series_equal(legacy_report.annual_returns(left.rename(columns={"equity_usd": "equity"})),
                                               current_report.annual_returns(right.rename(columns={"equity_usd": "equity"})))
                from reporting.temporal import analyze_temporal
                def temporal(curve):
                    anchor = pd.Series([current_ledger.FinancingModel().capital],
                                       index=[pd.Timestamp(curve.index[0]) - pd.Timedelta(days=1)])
                    path = pd.concat([anchor, pd.Series(curve.equity_usd.to_numpy(),
                                                       index=pd.to_datetime(curve.index))])
                    return analyze_temporal(path, initial_capital=current_ledger.FinancingModel().capital)
                left_summary, left_table = temporal(left)
                right_summary, right_table = temporal(right)
                self.assertEqual(left_summary, right_summary)
                pd.testing.assert_frame_equal(left_table, right_table)


    def test_old_and_current_bounded_cli_help_work_from_another_directory(self):
        for script in ('scripts/bounded_study.py', 'scripts/current/bounded_study.py'):
            result = subprocess.run([sys.executable, str(ROOT / script), '--help'],
                                    cwd=ROOT.parent, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('--execute', result.stdout)


if __name__ == '__main__':
    unittest.main()
