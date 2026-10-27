"""Preserve the independent reviewer's arithmetic and saved-artifact behavior."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

from scripts import recursive_research_review as legacy
from research.evaluation import saved_review as current

ROOT = Path(__file__).resolve().parents[1]


class SavedReviewBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.case = self.root / 'synthetic'
        self.case.mkdir()
        dates = pd.bdate_range('2020-12-21', periods=20)
        values = 300000 + np.array([0, 20, -100, -80, 10] * 4, dtype=float)
        curve = pd.DataFrame(dict(equity_usd=values, shares=1., close=100.,
                                  commission_usd=0., slippage_usd=0., financing_usd=0., dividend_usd=0.), index=dates)
        curve.to_csv(self.case / 'ledger.csv', index_label='date')
        pd.DataFrame({'side': ['BUY']}).to_csv(self.case / 'trades.csv', index=False)
        rows = [dict(period='Overall', **legacy.metrics(np.r_[300000, values], (dates[-1]-dates[0]).days))]
        previous = 300000
        for year, group in curve.groupby(curve.index.year):
            rows.append(dict(period=str(year), **legacy.metrics(np.r_[previous, group.equity_usd.to_numpy()])))
            previous = float(group.equity_usd.iloc[-1])
        (self.case / 'scores.json').write_text(json.dumps(rows))
        hashes = {str(p.relative_to(self.root)): current.digest(p) for p in self.case.iterdir()}
        (self.root / 'manifest.json').write_text(json.dumps({'artifact_hashes': hashes}))

    def test_extracted_function_bodies_are_identical_to_frozen_reviewer(self):
        def functions(path):
            return {n.name: ast.dump(n) for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}
        old = functions(ROOT / 'scripts/recursive_research_review.py')
        new = functions(ROOT / 'research/evaluation/saved_review.py')
        self.assertEqual(set(new), {'digest', 'metrics', 'inspect', 'verify_artifacts'})
        for name, body in new.items():
            self.assertEqual(body, old[name])

    def test_saved_bundle_annual_and_overall_metrics_match_without_mutation(self):
        before = {str(p): current.digest(p) for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(legacy.inspect(self.case), current.inspect(self.case))
        self.assertEqual(legacy.verify_artifacts(self.root), current.verify_artifacts(self.root))
        self.assertEqual(before, {str(p): current.digest(p) for p in self.root.rglob('*') if p.is_file()})

    def test_artifact_and_score_corruption_rejects_and_preserves_failed_inputs(self):
        path = self.case / 'scores.json'
        rows = json.loads(path.read_text())
        rows[0]['return_pct'] += 1
        path.write_text(json.dumps(rows))
        changed = path.read_bytes()
        for review in (legacy, current):
            with self.assertRaisesRegex(ValueError, 'Artifact hash mismatch'):
                review.verify_artifacts(self.root)
            with self.assertRaisesRegex(ValueError, 'Independent metric mismatch'):
                review.inspect(self.case)
            self.assertEqual(path.read_bytes(), changed)

    def test_old_and_current_cli_match_and_refuse_receipt_overwrite(self):
        records = []
        for number, command in enumerate(('scripts/recursive_research_review.py', 'scripts/current/recursive_research_review.py')):
            output = self.root.parent / (self.root.name + f'-receipt-{number}.json')
            self.addCleanup(output.unlink, missing_ok=True)
            args = [sys.executable, str(ROOT / command), str(self.root), '--cases', 'synthetic', '--output', str(output)]
            first = subprocess.run(args, cwd=self.root, text=True, capture_output=True, timeout=15)
            self.assertEqual(first.returncode, 0, first.stderr)
            records.append(json.loads(output.read_text()))
            digest = hashlib.sha256(output.read_bytes()).hexdigest()
            repeated = subprocess.run(args, cwd=self.root, text=True, capture_output=True, timeout=15)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn('Preserve existing receipt', repeated.stderr)
            self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), digest)
        self.assertEqual(records[0]['cases'], records[1]['cases'])
        self.assertNotEqual(records[0]['reviewer_code_sha256'], records[1]['reviewer_code_sha256'])
        self.assertEqual(records[1]['independent_metrics_code_sha256'],
                         current.digest(ROOT / 'research/evaluation/saved_review.py'))


if __name__ == '__main__':
    unittest.main()
