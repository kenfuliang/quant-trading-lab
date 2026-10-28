"""Current checkpoint reports are derived views, never historical state repairs."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.current import build_risk_gate_checkpoint as checkpoint


class CheckpointPreservationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.state_path = self.root / '.local/current-risk-gate/state.json'
        self.state_path.parent.mkdir(parents=True)
        self.source = self.root / 'reports/failed-source'
        self.source.mkdir(parents=True)
        self.old = self.root / 'reports/leverage/3aba31cfafe4da76/base_6pct_buy_hold_1x'
        self.ema = self.root / 'reports/strategy-suite/97fc0717512bee9e/s002_1x'
        dates = pd.bdate_range('2005-01-03', periods=300).strftime('%Y-%m-%d')
        curve = pd.DataFrame({'equity_usd': 300000 + np.arange(300) * 10 + np.sin(np.arange(300))*20}, index=dates)
        for folder in (self.source / '5_hold', self.old, self.ema):
            folder.mkdir(parents=True)
            curve.to_csv(folder / 'ledger.csv', index_label='date')
            pd.DataFrame({'side': ['BUY']}).to_csv(folder / 'trades.csv', index=False)
        (self.source / 'failure.json').write_text('{"status":"failed"}')
        hashes = {p.relative_to(self.source).as_posix(): self.sha(p) for p in self.source.rglob('*') if p.is_file()}
        (self.source / 'manifest.json').write_text(json.dumps({'status': 'STOPPED_INCOMPLETE', 'artifact_hashes': hashes}))
        self.state = {'status': 'stopped_integrity_or_timeout', 'output': 'reports/failed-source',
                      'attempts': [{'status': 'failed'}] + [{'status': 'reserved'} for _ in range(11)]}
        self.state_path.write_text(json.dumps(self.state))
        for path in ('research/studies/spy/risk_gate_study.py', 'research/evaluation/control_parity.py', 'tests/current/test_control_parity.py'):
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('# Synthetic source identity fixture\n')
        self.out = self.root / 'derived/checkpoint'
        self.before = self.inputs()
        self.addCleanup(patch.stopall)
        patch.object(checkpoint, 'ROOT', self.root).start()
        patch.object(checkpoint, 'compare', return_value={'passed': True}).start()
        self.review = {'metric_checks': [{}], 'overall': {'return_pct': 1., 'drawdown_pct': -.1,
                       'sharpe': .5, 'calmar': 10., 'ending_equity_usd': 303000.},
                       'annual': [{'period': '2005', 'return_pct': 1., 'drawdown_pct': -.1, 'sharpe': .5, 'calmar': 10.}]}
        patch.object(checkpoint, 'inspect', return_value=self.review).start()
        patch.object(checkpoint.go.Figure, 'write_html', side_effect=lambda path, **kwargs: Path(path).write_text('Synthetic chart')).start()

    def sha(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def inputs(self):
        return {str(p): self.sha(p) for folder in (self.source, self.old, self.ema, self.state_path.parent)
                for p in folder.rglob('*') if p.is_file()}

    def run_report(self):
        checkpoint.main(['--state', str(self.state_path), '--output', str(self.out)])

    def test_success_leaves_state_failure_manifest_and_reference_bytes_unchanged(self):
        self.run_report()
        self.assertEqual(self.inputs(), self.before)
        self.assertTrue((self.out / 'post-stop-control-parity.json').is_file())
        self.assertFalse((self.source / 'post-stop-control-parity.json').exists())
        observation = json.loads((self.out / 'checkpoint-observation.json').read_text())
        self.assertEqual(observation['new_financial_attempts'], 0)
        self.assertEqual(observation['historical_financial_attempts'], 1)
        self.assertEqual(json.loads((self.out / 'review-bundle.json').read_text())['new_financial_attempts'], 0)
        checkpoint.verify_artifacts(self.source)
        checkpoint.verify_artifacts(self.out)

    def test_interruption_preserves_inputs_and_keeps_partial_output_separate(self):
        with patch.object(checkpoint, 'inspect', side_effect=RuntimeError('injected report interruption')):
            with self.assertRaisesRegex(RuntimeError, 'report interruption'):
                self.run_report()
        self.assertEqual(self.inputs(), self.before)
        self.assertTrue((self.out / 'post-stop-control-parity.json').is_file())
        with self.assertRaisesRegex(ValueError, 'Preserve existing checkpoint'):
            self.run_report()

    def test_later_epoch_cannot_be_mislabeled_as_the_old_checkpoint(self):
        self.state['attempts'][1]['status'] = 'completed'
        self.state_path.write_text(json.dumps(self.state))
        before = self.inputs()
        with self.assertRaisesRegex(ValueError, 'frozen stopped snapshot'):
            self.run_report()
        self.assertFalse(self.out.exists())
        self.assertEqual(self.inputs(), before)

    def test_output_cannot_be_nested_inside_input_bundle_or_state(self):
        for out in (self.source / 'derived', self.state_path.parent / 'derived'):
            with self.subTest(out=out), self.assertRaisesRegex(ValueError, 'separate from input evidence'):
                checkpoint.main(['--state', str(self.state_path), '--output', str(out)])
        self.assertEqual(self.inputs(), self.before)

    def test_default_state_namespace_does_not_fall_back_to_legacy_state(self):
        self.state_path.unlink()
        legacy = self.root / '.local/rsi-risk-gate/state.json'
        legacy.parent.mkdir(parents=True)
        legacy.write_text(json.dumps(self.state))
        with self.assertRaises(FileNotFoundError):
            checkpoint.main(['--output', str(self.out)])
        self.assertEqual(json.loads(legacy.read_text()), self.state)
        self.assertFalse(self.out.exists())


if __name__ == '__main__':
    unittest.main()
