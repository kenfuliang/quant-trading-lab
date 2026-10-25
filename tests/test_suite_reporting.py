"""Strategy suite reporting tests use deliberately tiny synthetic results."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from reporting import strategy_suite


class SuiteReportingTest(unittest.TestCase):
    def fixture(self, root):
        source = root / 'source'
        source.mkdir()
        manifest = {'status': 'completed', 'fingerprint': 'a' * 64,
                    'cases': [{'key': 'ema_1', 'strategy_id': 2, 'name': 'EMA · 1×', 'leverage': 1}]}
        (source / 'manifest.json').write_text(json.dumps(manifest))
        (source / 'catalogue.json').write_text(json.dumps({'strategies': [
            {'id': 2, 'name': 'EMA', 'family': 'trend', 'status': 'candidate'},
            {'id': 95, 'name': 'Lead/lag', 'family': 'microstructure', 'status': 'blocked', 'blockers': ['Missing synchronized quotes']}]}))
        pd.DataFrame([{'period': 'Overall', 'case': 'ema_1', 'strategy_id': 2, 'strategy': 'EMA',
                       'calmar': .3, 'sharpe': .6, 'return_pct': 8, 'drawdown_pct': -26,
                       'exposure': 1, 'ending_equity': 200, 'financing_usd': 0, 'liquidations': 0},
                      {'period': '2005', 'case': 'ema_1', 'strategy_id': 2, 'strategy': 'EMA',
                       'calmar': None, 'sharpe': None, 'return_pct': 0, 'drawdown_pct': 0,
                       'exposure': 1, 'ending_equity': 100, 'financing_usd': 0, 'liquidations': 0}]).to_csv(source / 'scores.csv', index=False)
        return source

    def test_render_preserves_missing_values_and_blockers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.fixture(root)
            with patch.object(strategy_suite, 'ROOT', root):
                out = strategy_suite.render(source)
            html = (out / 'index.html').read_text()
            # Extract only our payload; Plotly's own bundled JavaScript has NaN literals.
            payload = html.split('const data=', 1)[1].split(';\nconst $=', 1)[0]
            data = json.loads(payload)
            self.assertEqual(len(data['cases']), 1)
            self.assertEqual(len(data['catalogue']), 2)
            self.assertIsNone(data['scores'][1]['calmar'])
            self.assertEqual(data['catalogue'][1]['blockers'], ['Missing synchronized quotes'])
            self.assertEqual((source / 'scores.csv').read_bytes(), (out / 'scores.csv').read_bytes())
            self.assertIn('in-sample research', html)
            self.assertIn('year', html.lower())

    def test_render_updates_one_home_link(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.fixture(root)
            home = root / '.local/performance/index.html'
            home.parent.mkdir(parents=True)
            home.write_text('<body>Original reports</body>')
            with patch.object(strategy_suite, 'ROOT', root):
                strategy_suite.render(source)
                strategy_suite.render(source)
            self.assertEqual(home.read_text().count('id="strategy-suite-link"'), 1)
            self.assertIn('Original reports', home.read_text())

    def test_render_rejects_duplicate_period_case(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.fixture(root)
            rows = pd.read_csv(source / 'scores.csv')
            pd.concat([rows, rows.iloc[:1]]).to_csv(source / 'scores.csv', index=False)
            with patch.object(strategy_suite, 'ROOT', root), self.assertRaisesRegex(ValueError, 'Duplicate'):
                strategy_suite.render(source)

    def test_incomplete_suite_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = self.fixture(Path(temporary))
            manifest = json.loads((source / 'manifest.json').read_text())
            manifest['status'] = 'running'
            (source / 'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'Completed'):
                strategy_suite.render(source)
