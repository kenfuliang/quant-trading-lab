"""Synthetic, offline tests of bounded execution—not new strategy research trials."""
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from research.studies.spy import bounded_study as study
from research.policies.daily_signals import build_signal
from research.evaluation.leveraged_spy import FinancingModel, simulate


class BoundedStudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.json'
        self.source.write_text('{"synthetic_fixture": true}')
        dates = pd.date_range('2004-01-01', periods=280, freq='B')
        close = 100 + np.arange(280) * .04 + np.sin(np.arange(280) / 4)
        self.raw = pd.DataFrame({'open': close, 'high': close + 1, 'low': close - 1,
                                 'close': close, 'volume': 1000}, index=dates)
        self.plan = {'schema_version': 1, 'plan_id': 'synthetic-test', 'parent': 'synthetic-parent',
                     'hypothesis': 'Check bounded execution without historical strategy search.',
                     'assumptions': ['Synthetic fixture; all viewed development evidence.'],
                     'evaluation': {'label': 'development/viewed-history', 'start': str(dates[250].date()),
                                    'end': str(dates[-1].date()), 'expected_sessions': 30},
                     'source': {'path': str(self.source), 'sha256': study.digest(self.source)},
                     'code_hashes': study.current_code_hashes(), 'financing_model': asdict(FinancingModel()),
                     'max_cases': 2, 'cases': [{'case_id': 'ema', 'strategy_id': 2, 'exposure': 1.0}]}
        def load(path):
            return self.raw.copy(), {}, {'sha256': study.digest(path)}
        self.loader = patch.object(study, 'load_data', side_effect=load)
        self.loader.start()
        self.addCleanup(self.loader.stop)

    def test_budget_and_unsupported_cases_rejected_before_source_load(self):
        for change in ({'max_cases': 13}, {'max_cases': 0}, {'cases': self.plan['cases'] * 3},
                       {'cases': [{'case_id': 'short', 'strategy_id': 200, 'exposure': 1}]},
                       {'cases': [{'case_id': '../escape', 'strategy_id': 2, 'exposure': 1}]},
                       {'cases': [{'case_id': 'leveraged', 'strategy_id': 2, 'exposure': 2}]},
                       {'evaluation': dict(self.plan['evaluation'], label='untouched-test')}):
            plan = dict(self.plan, **change)
            with self.assertRaises(ValueError):
                study.preflight(plan)
        study.load_data.assert_not_called()
        self.assertFalse((self.root / 'output').exists())

    def test_mixture_preserves_existing_lag_and_allocates_cash(self):
        case = {'case_id': 'mixed', 'components': [{'strategy_id': 2, 'weight': .5},
                                                {'strategy_id': 11, 'weight': .25}], 'exposure': 1}
        frame = study.build_case_frame(self.raw, case)
        expected = .5 * build_signal(self.raw, 2).want_long + .25 * build_signal(self.raw, 11).want_long
        pd.testing.assert_series_equal(frame.allocation_factor, expected, check_names=False)
        pd.testing.assert_series_equal(frame.want_long, expected > 0, check_names=False)
        self.assertEqual(frame.allocation_factor.iloc[0], 0)
        altered = self.raw.copy()
        altered.loc[altered.index[270]:, ['open', 'high', 'low', 'close']] *= 2
        pd.testing.assert_frame_equal(frame.iloc[:270], study.build_case_frame(altered, case).iloc[:270])
        with self.assertRaises(ValueError):
            study.validate_plan(dict(self.plan, cases=[dict(case, components=[{'strategy_id': 2, 'weight': .8}, {'strategy_id': 11, 'weight': .3}])]))
        with self.assertRaises(ValueError):
            study.validate_plan(dict(self.plan, cases=[dict(case, components=[{'strategy_id': 34, 'weight': 1}])]))

    def test_completed_case_audits_and_matches_unwrapped_ledger(self):
        result = study.run_plan(self.plan, self.root / 'output')
        self.assertFalse(result['reused'])
        directory = Path(result['directory'])
        saved = pd.read_csv(directory / 'ema/ledger.csv', index_col='date')
        raw = self.raw.round(2)
        expected_frame = build_signal(raw, 2).loc[self.plan['evaluation']['start']:self.plan['evaluation']['end']].copy()
        expected_frame.index = expected_frame.index.strftime('%Y-%m-%d')
        expected, trades = simulate(expected_frame, {}, 'trend', 1., FinancingModel())
        pd.testing.assert_frame_equal(saved, expected, check_dtype=False, check_exact=False, atol=1e-7, rtol=0)
        actual_trades = pd.read_csv(directory / 'ema/trades.csv')
        pd.testing.assert_frame_equal(actual_trades, trades, check_dtype=False)
        self.assertTrue(json.loads((directory / 'ema/audit.json').read_text())['passed'])
        with patch.object(study, 'simulate', side_effect=AssertionError('Cache must not simulate')):
            self.assertTrue(study.run_plan(self.plan, self.root / 'output')['reused'])

    def test_preflight_is_output_free_and_hash_mutation_stops(self):
        study.preflight(self.plan)
        self.assertEqual(sorted(x.name for x in self.root.iterdir()), ['source.json'])
        self.source.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'Source input hash'):
            study.run_plan(self.plan, self.root / 'output')
        self.assertFalse((self.root / 'output').exists())
        self.plan['source']['sha256'] = study.digest(self.source)
        self.plan['code_hashes']['research/evaluation/leveraged_spy.py'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Code/method input hash'):
            study.preflight(self.plan)

    def test_failure_retains_attempt_and_partial_artifact_hashes(self):
        with patch.object(study, 'simulate', side_effect=RuntimeError('synthetic failure')):
            with self.assertRaisesRegex(RuntimeError, 'synthetic failure'):
                study.run_plan(self.plan, self.root / 'output')
        directories = list((self.root / 'output').iterdir())
        self.assertEqual(len(directories), 1)
        saved = json.loads((directories[0] / 'manifest.json').read_text())
        self.assertEqual(saved['status'], 'failed')
        self.assertIn('ema/signal.csv', saved['artifact_hashes'])
        self.assertEqual(saved['failure']['type'], 'RuntimeError')
        with self.assertRaisesRegex(ValueError, 'Failed/incomplete'):
            study.run_plan(self.plan, self.root / 'output')

    def test_input_mutation_during_execution_is_failed_and_retained(self):
        original = study.simulate
        def mutate(*args, **kwargs):
            result = original(*args, **kwargs)
            self.source.write_text('mutated during computation')
            return result
        with patch.object(study, 'simulate', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, 'Source input hash'):
                study.run_plan(self.plan, self.root / 'output')
        saved = json.loads(next((self.root / 'output').glob('*/manifest.json')).read_text())
        self.assertEqual(saved['status'], 'failed')

    def test_cache_tampering_and_incomplete_directories_fail_closed(self):
        result = study.run_plan(self.plan, self.root / 'output')
        directory = Path(result['directory'])
        with (directory / 'ema/ledger.csv').open('a') as stream:
            stream.write('tampered\n')
        with self.assertRaisesRegex(ValueError, 'artifact hash mismatch'):
            study.run_plan(self.plan, self.root / 'output')
        saved = json.loads((directory / 'manifest.json').read_text())
        saved['status'] = 'running'
        (directory / 'manifest.json').write_text(json.dumps(saved))
        with self.assertRaisesRegex(ValueError, 'Failed/incomplete'):
            study.run_plan(self.plan, self.root / 'output')

    def test_undefined_ratios_remain_null_and_not_favorable_zero(self):
        self.raw.loc[:, ['open', 'close']] = 100.
        self.raw['high'] = 101.
        self.raw['low'] = 99.
        result = study.run_plan(self.plan, self.root / 'output')
        rows = json.loads((Path(result['directory']) / 'ema/scores.json').read_text())
        self.assertIsNone(rows[0]['sharpe'])
        self.assertIsNone(rows[0]['calmar'])
        self.assertEqual(rows[0]['return_pct'], 0.)

    def test_mixture_executes_one_net_account_and_audits(self):
        self.plan['cases'] = [{'case_id': 'joint', 'components': [{'strategy_id': 2, 'weight': .5},
                                                               {'strategy_id': 11, 'weight': .5}], 'exposure': 1}]
        result = study.run_plan(self.plan, self.root / 'output')
        directory = Path(result['directory'])
        ledger = pd.read_csv(directory / 'joint/ledger.csv')
        trades = pd.read_csv(directory / 'joint/trades.csv')
        self.assertTrue(ledger.effective_target_leverage.between(0, 1).all())
        self.assertEqual(ledger.commission_usd.sum(), len(trades))
        self.assertTrue(result['manifest']['cases'][0]['audit']['passed'])


if __name__ == '__main__':
    unittest.main()
