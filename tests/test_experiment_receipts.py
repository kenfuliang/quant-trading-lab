"""Synthetic receipt checks only: no financial simulations or external connections."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

from research.experiment_receipts import SCHEMA, validate_receipt


def fixture():
    return {
        'schema': SCHEMA, 'cycle_id': 'synthetic-cycle', 'status': 'success',
        'missing_evidence': {},
        'cases': [{'case_id': 'fixture', 'name': 'synthetic', 'run_id': 'offline-1',
                   'source': 'synthetic-source-sha', 'build': 'python-fixture-v1',
                   'plan': 'frozen synthetic plan', 'data': 'invented input',
                   'date_range': {'start': '2020-01-01', 'end': '2020-01-02'},
                   'accounting': 'zero-cost synthetic checks, no fills',
                   'metric_conventions': 'daily-close-v1 fractional rates',
                   'attempts': {'used': 0, 'limit': 0}}],
        'artifacts': [{'path': 'result.txt', 'sha256': hashlib.sha256(b'fixture').hexdigest(), 'role': 'synthetic-result'}],
    }


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'result.txt').write_bytes(b'fixture')

    def test_published_template_is_valid_blocked_record(self):
        root = Path(__file__).resolve().parents[1]
        receipt = json.loads((root / "docs/templates/experiment-receipt.json").read_text())
        self.assertEqual(receipt["status"], "blocked")
        self.assertEqual(validate_receipt(receipt, root), [])

    def test_complete_success(self):
        self.assertEqual(validate_receipt(fixture(), self.root), [])

    def test_documented_failure_blocked_and_incomplete(self):
        for status in ('failed', 'blocked', 'incomplete'):
            receipt = fixture()
            receipt.update(status=status, outcome_reason='Launch not performed: local input unavailable')
            receipt['cases'][0]['run_id'] = None
            receipt['missing_evidence'] = {'cases.0.run_id': 'No launch; no run identifier exists'}
            with self.subTest(status=status):
                self.assertEqual(validate_receipt(receipt, self.root), [])

    def test_missing_identity_and_false_gap(self):
        receipt = fixture()
        del receipt['cases'][0]['run_id']
        self.assertTrue(any('run_id' in e for e in validate_receipt(receipt, self.root)))
        receipt = fixture()
        receipt.update(status='blocked', outcome_reason='fixture')
        receipt['missing_evidence'] = {'cases.0.build': 'Not actually absent'}
        self.assertTrue(any('null required' in e for e in validate_receipt(receipt, self.root)))

    def test_hash_mismatch_and_missing_artifact(self):
        receipt = fixture()
        receipt['artifacts'][0]['sha256'] = '0' * 64
        self.assertTrue(any('hash mismatch' in e for e in validate_receipt(receipt, self.root)))
        (self.root / 'result.txt').unlink()
        self.assertTrue(any('cannot read' in e for e in validate_receipt(receipt, self.root)))

    def test_comparison_conventions_accounting_dates(self):
        for field in ('metric_conventions', 'accounting', 'date_range'):
            receipt = fixture()
            second = deepcopy(receipt['cases'][0])
            second['case_id'] = 'other'
            second[field] = {'start': '2021-01-01', 'end': '2021-01-02'} if field == 'date_range' else 'different'
            receipt['cases'].append(second)
            receipt['comparison_groups'] = [['fixture', 'other']]
            with self.subTest(field=field):
                self.assertTrue(any(f'incompatible {field}' in e for e in validate_receipt(receipt, self.root)))

    def test_scope_escape_and_symlink(self):
        receipt = fixture()
        for value in ('../outside', '/tmp/outside', 'https://example.com/result'):
            receipt['artifacts'][0]['path'] = value
            self.assertTrue(validate_receipt(receipt, self.root))
        (self.root / 'outside').symlink_to('/etc/passwd')
        receipt['artifacts'][0]['path'] = 'outside'
        self.assertTrue(any('escapes' in e for e in validate_receipt(receipt, self.root)))

    def test_attempt_bounds_duplicates_and_invalid_date(self):
        receipt = fixture()
        receipt['cases'][0]['attempts'] = {'used': 1, 'limit': 0}
        receipt['cases'][0]['date_range']['start'] = 'not-a-date'
        receipt['cases'].append(deepcopy(receipt['cases'][0]))
        errors = validate_receipt(receipt, self.root)
        for expected in ('exceeds', 'ISO', 'duplicate'):
            self.assertTrue(any(expected in e for e in errors))

    def test_matching_comparison_group_and_internal_symlink(self):
        receipt = fixture()
        second = deepcopy(receipt['cases'][0])
        second['case_id'] = 'other'
        receipt['cases'].append(second)
        receipt['comparison_groups'] = [['fixture', 'other']]
        (self.root / 'alias.txt').symlink_to(self.root / 'result.txt')
        receipt['artifacts'][0]['path'] = 'alias.txt'
        self.assertEqual(validate_receipt(receipt, self.root), [])

    def test_date_key_must_exist_even_with_gap_reason(self):
        receipt = fixture()
        receipt.update(status='blocked', outcome_reason='No dates')
        del receipt['cases'][0]['date_range']['start']
        receipt['missing_evidence'] = {'cases.0.date_range.start': 'Unknown date'}
        self.assertTrue(any('key required' in e for e in validate_receipt(receipt, self.root)))

    def test_cli_success_malformed_json_and_hash_mismatch(self):
        script = Path(__file__).resolve().parents[1] / 'scripts/check_experiment_receipt.py'
        path = self.root / 'receipt.json'
        def run():
            return subprocess.run([sys.executable, str(script), str(path), '--root', str(self.root)],
                                  capture_output=True, text=True, timeout=10)
        path.write_text(json.dumps(fixture()))
        self.assertEqual(run().returncode, 0)
        path.write_text('{')
        invalid = run()
        self.assertEqual(invalid.returncode, 1)
        self.assertIn('Receipt unreadable', invalid.stderr)
        receipt = fixture()
        receipt['artifacts'][0]['sha256'] = '0' * 64
        path.write_text(json.dumps(receipt))
        mismatch = run()
        self.assertEqual(mismatch.returncode, 1)
        self.assertIn('hash mismatch', mismatch.stderr)

    def test_malformed_containers_report_errors(self):
        for receipt in (None, [], {'schema': SCHEMA}, fixture() | {'status': {}}, fixture() | {'cases': [None], 'artifacts': [None]}):
            self.assertTrue(validate_receipt(receipt, self.root))


if __name__ == '__main__':
    unittest.main()
