"""Synthetic leakage-audit checks only: local temp files, no network or broker."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import research.control.experiment_receipts as canonical
import research.experiment_receipts as legacy
from research.control.leakage_audit import audit_receipt
from research.control.trial_ledger import TrialLedger, seal_hash

ROOT = Path(__file__).resolve().parents[1]


def receipt(start, end, used=1, **extra):
    return {'schema': canonical.SCHEMA, 'cycle_id': 'c1', 'status': 'incomplete',
            'cases': [{'case_id': 'a', 'date_range': {'start': start, 'end': end},
                       'attempts': {'used': used, 'limit': 5}}], **extra}


class LeakageAuditTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.dir = self.root / 'ledger'
        with TrialLedger(self.dir) as ledger:
            self.digest = ledger.seal('h1', '2026-01-01', '2026-06-30', 'synthetic holdout')
            ledger.trial('c1', 'first')

    def test_missing_ledger_passes(self):
        self.assertEqual(audit_receipt(receipt('2026-02-01', '2026-03-01'), self.root), [])
        self.assertEqual(audit_receipt(receipt('2026-02-01', '2026-03-01', trial_ledger_ref='absent'),
                                       self.root), [])

    def test_declared_seal_without_ledger_fails(self):
        errors = audit_receipt(receipt('2025-01-01', '2025-02-01', holdout_seal_hash=self.digest),
                               self.root / 'nowhere')
        self.assertTrue(any('no trial ledger' in e for e in errors))

    def test_window_overlapping_seal_fails(self):
        errors = audit_receipt(receipt('2026-06-30', '2026-08-01', trial_ledger_ref='ledger'), self.root)
        self.assertTrue(any('overlaps sealed holdout h1' in e for e in errors))

    def test_window_before_seal_passes(self):
        self.assertEqual(audit_receipt(receipt('2025-01-01', '2025-12-31', trial_ledger_ref='ledger'),
                                       self.root), [])

    def test_trial_count_mismatch_fails(self):
        errors = audit_receipt(receipt('2025-01-01', '2025-12-31', used=2, trial_ledger_ref='ledger'),
                               self.root)
        self.assertTrue(any('ledger records 1 trial' in e for e in errors))

    def test_protected_read_requires_ledger_open_event(self):
        r = receipt('2026-02-01', '2026-03-01', trial_ledger_ref='ledger', holdout_seal_hash=self.digest)
        errors = audit_receipt(r, self.root)
        self.assertTrue(any('no ledger open event' in e for e in errors))
        with TrialLedger(self.dir) as ledger:
            ledger.freeze('h1', 'a' * 64, 'frozen')
            ledger.open('h1', 'other-cycle', 'tester', 'wrong cycle')
        self.assertTrue(any('no ledger open event' in e for e in audit_receipt(r, self.root)))
        with TrialLedger(self.dir) as ledger:
            ledger.open('h1', 'c1', 'tester', 'single read')
        self.assertEqual(audit_receipt(r, self.root), [])

    def test_unknown_seal_hash_and_other_holdout_overlap_fail(self):
        r = receipt('2026-02-01', '2026-03-01', trial_ledger_ref='ledger', holdout_seal_hash='b' * 64)
        errors = audit_receipt(r, self.root)
        self.assertTrue(any('no seal with this hash' in e for e in errors))
        self.assertTrue(any('overlaps sealed holdout' in e for e in errors))

    def test_tampered_ledger_fails_audit(self):
        log = self.dir / 'ledger.jsonl'
        log.write_bytes(log.read_bytes().replace(b'synthetic holdout', b'changed holdout!'))
        errors = audit_receipt(receipt('2025-01-01', '2025-02-01', trial_ledger_ref='ledger'), self.root)
        self.assertTrue(errors[0].startswith('trial_ledger:'))

    def test_ref_escape_rejected(self):
        errors = audit_receipt(receipt('2025-01-01', '2025-02-01', trial_ledger_ref='../ledger'), self.root)
        self.assertEqual(errors, ['trial_ledger_ref: expected relative path inside the artifact root'])

    def test_receipt_field_shape_validated(self):
        bad = canonical.validate_receipt(receipt('2025-01-01', '2025-02-01', trial_ledger_ref='/abs',
                                                 holdout_seal_hash='xyz'), self.root)
        self.assertTrue(any(e.startswith('trial_ledger_ref') for e in bad))
        self.assertTrue(any(e.startswith('holdout_seal_hash') for e in bad))
        template = json.loads((ROOT / 'docs/templates/experiment-receipt.json').read_text())
        self.assertEqual(canonical.validate_receipt(template, self.root), [])

    def test_cli_audits_receipt(self):
        path = self.root / 'receipt.json'
        path.write_text(json.dumps(receipt('2026-02-01', '2026-03-01')))
        run = subprocess.run([sys.executable, str(ROOT / 'scripts/check_trial_ledger.py'), str(self.dir),
                              '--receipt', str(path)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 1)
        self.assertIn('overlaps sealed holdout', run.stderr)
        ok = subprocess.run([sys.executable, str(ROOT / 'scripts/check_trial_ledger.py'), str(self.dir)],
                            capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)

    def test_frozen_legacy_validator_agrees_on_pre_ledger_receipts(self):
        # research/experiment_receipts.py is a hash-frozen copy (compatibility.json), so it
        # cannot re-export; pin that both validators agree on receipts without ledger fields.
        self.assertEqual(legacy.SCHEMA, canonical.SCHEMA)
        template = json.loads((ROOT / 'docs/templates/experiment-receipt.json').read_text())
        old = {k: v for k, v in template.items() if k not in ('trial_ledger_ref', 'holdout_seal_hash')}
        for candidate in (old, receipt('2025-01-01', '2025-02-01'), {'schema': 'wrong'}):
            self.assertEqual(legacy.validate_receipt(candidate, self.root),
                             canonical.validate_receipt(candidate, self.root))


if __name__ == '__main__':
    unittest.main()
