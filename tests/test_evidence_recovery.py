"""Copy-only recovery fixtures; preserve failure state and all existing files."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from research.control import evidence_recovery as recovery

ROOT = Path(__file__).resolve().parents[1]


class EvidenceRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'original'
        self.source.mkdir()
        self.data = self.source / 'case/ledger.csv'
        self.data.parent.mkdir()
        self.data.write_text('date,equity\n2020-01-01,100\n')
        self.backup = self.root / 'backup'
        self.destination = self.root / 'restored'
        self.set_status('completed')

    def set_status(self, status):
        hashes = {p.relative_to(self.source).as_posix(): recovery.digest(p)
                  for p in self.source.rglob('*') if p.is_file() and p.name != 'manifest.json'}
        (self.source / 'manifest.json').write_text(json.dumps({'status': status, 'artifact_hashes': hashes}))

    def test_complete_and_failed_bundle_restore_with_originals_unchanged(self):
        for status in ('completed', 'recovery_failed_no_further_launch'):
            with self.subTest(status=status):
                self.set_status(status)
                before = recovery.file_hashes(self.source)
                backup = self.root / ('backup-' + status)
                destination = self.root / ('restore-' + status)
                receipt = recovery.create_recovery_copy(self.source, backup)
                result = recovery.restore_recovery_copy(backup, destination, receipt['inventory_sha256'])
                self.assertEqual(result['original_status'], status)
                self.assertEqual(recovery.file_hashes(destination), before)
                self.assertEqual(recovery.file_hashes(self.source), before)

    def test_failed_json_is_not_repaired_or_promoted(self):
        (self.source / 'failure.json').write_text('{"status":"failed","attempts":1}')
        self.set_status('failed')
        record = recovery.create_recovery_copy(self.source, self.backup)
        recovery.restore_recovery_copy(self.backup, self.destination, record['inventory_sha256'])
        self.assertEqual((self.destination / 'failure.json').read_bytes(), (self.source / 'failure.json').read_bytes())
        self.assertEqual(json.loads((self.destination / 'manifest.json').read_text())['status'], 'failed')

    def test_existing_backup_and_restore_refuse_overwrite_even_when_empty(self):
        self.backup.mkdir()
        with self.assertRaises(FileExistsError):
            recovery.create_recovery_copy(self.source, self.backup)
        other = self.root / 'fresh-backup'
        record = recovery.create_recovery_copy(self.source, other)
        self.destination.mkdir()
        with self.assertRaises(FileExistsError):
            recovery.restore_recovery_copy(other, self.destination, record['inventory_sha256'])
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_nonterminal_or_unknown_status_rejected_before_backup(self):
        for status in ('running', 'pending_review', 'unknown'):
            self.set_status(status)
            with self.assertRaisesRegex(ValueError, 'closed bundle statuses'):
                recovery.create_recovery_copy(self.source, self.backup)
            self.assertFalse(self.backup.exists())

    def test_corrupt_original_and_unlisted_or_missing_file_stop_before_backup(self):
        self.data.write_text('corrupt')
        with self.assertRaisesRegex(ValueError, 'hash/coverage mismatch'):
            recovery.create_recovery_copy(self.source, self.backup)
        self.assertFalse(self.backup.exists())
        self.set_status('failed')
        (self.source / 'unlisted.txt').write_text('extra')
        with self.assertRaises(ValueError):
            recovery.create_recovery_copy(self.source, self.backup)
        (self.source / 'unlisted.txt').unlink()
        self.data.unlink()
        with self.assertRaises(ValueError):
            recovery.create_recovery_copy(self.source, self.backup)

    def test_corrupt_copy_or_inventory_identity_stop_before_restore(self):
        record = recovery.create_recovery_copy(self.source, self.backup)
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            recovery.restore_recovery_copy(self.backup, self.destination, '0' * 64)
        (self.backup / 'files/case/ledger.csv').write_text('corrupt backup')
        with self.assertRaises(ValueError):
            recovery.restore_recovery_copy(self.backup, self.destination, record['inventory_sha256'])
        self.assertFalse(self.destination.exists())
        self.assertTrue((self.backup / 'files/case/ledger.csv').exists())

    def test_symlink_traversal_and_overlap_rejected(self):
        (self.source / 'link').symlink_to(self.data)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            recovery.verify_bundle(self.source)
        (self.source / 'link').unlink()
        for name in ('../outside', '/tmp/outside', 'case/../outside', 'case\\outside', 'case//ledger.csv'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                recovery.validate_hash_map({name: '0' * 64})
        with self.assertRaisesRegex(ValueError, 'disjoint'):
            recovery.create_recovery_copy(self.source, self.source / 'backup')

    def test_interrupted_copy_is_retained_and_not_reused(self):
        original = recovery.copy_files
        def partial(source, destination, hashes):
            first = next(iter(hashes))
            original(source, destination, {first: hashes[first]})
            raise OSError('injected copy interruption')
        with patch.object(recovery, 'copy_files', side_effect=partial):
            with self.assertRaisesRegex(OSError, 'interruption'):
                recovery.create_recovery_copy(self.source, self.backup)
        self.assertTrue(any((self.backup / 'files').rglob('*')))
        with self.assertRaises(FileExistsError):
            recovery.create_recovery_copy(self.source, self.backup)

    def test_original_mutation_during_copy_is_detected_without_cleanup(self):
        original = recovery.copy_files
        def mutate(source, destination, hashes):
            original(source, destination, hashes)
            self.data.write_text('changed concurrently')
        with patch.object(recovery, 'copy_files', side_effect=mutate):
            with self.assertRaises(ValueError):
                recovery.create_recovery_copy(self.source, self.backup)
        self.assertTrue(self.backup.exists())
        self.assertEqual(self.data.read_text(), 'changed concurrently')

    def test_restore_interruption_retains_partial_output_and_rejects_retry(self):
        record = recovery.create_recovery_copy(self.source, self.backup)
        before = recovery.file_hashes(self.backup)
        original = recovery.copy_files
        def partial(source, destination, hashes):
            first = next(iter(hashes))
            original(source, destination, {first: hashes[first]})
            raise OSError('injected restore interruption')
        with patch.object(recovery, 'copy_files', side_effect=partial):
            with self.assertRaisesRegex(OSError, 'interruption'):
                recovery.restore_recovery_copy(self.backup, self.destination, record['inventory_sha256'])
        self.assertTrue(self.destination.exists())
        self.assertEqual(recovery.file_hashes(self.backup), before)
        with self.assertRaises(FileExistsError):
            recovery.restore_recovery_copy(self.backup, self.destination, record['inventory_sha256'])

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'FIFO fixture requires POSIX')
    def test_fifo_inventory_is_rejected_before_any_content_read(self):
        self.backup.mkdir()
        (self.backup / 'files').mkdir()
        os.mkfifo(self.backup / 'inventory.json')
        command = ROOT / 'scripts/current/evidence_recovery.py'
        result = subprocess.run([sys.executable, str(command), 'restore', str(self.backup),
                                 str(self.destination), '--inventory-sha256', '0' * 64],
                                cwd=self.root, capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('inventory identity mismatch', result.stderr)
        self.assertFalse(self.destination.exists())
        self.assertTrue((self.backup / 'inventory.json').exists())

    def test_cli_copy_restore_and_tamper_failure_exit(self):
        command = ROOT / 'scripts/current/evidence_recovery.py'
        copied = subprocess.run([sys.executable, str(command), 'backup', str(self.source), str(self.backup)],
                                cwd=self.root, capture_output=True, text=True, timeout=15)
        self.assertEqual(copied.returncode, 0, copied.stderr)
        sha = json.loads(copied.stdout)['inventory_sha256']
        restored = subprocess.run([sys.executable, str(command), 'restore', str(self.backup), str(self.destination), '--inventory-sha256', sha],
                                 cwd=self.root, capture_output=True, text=True, timeout=15)
        self.assertEqual(restored.returncode, 0, restored.stderr)
        failed = subprocess.run([sys.executable, str(command), 'restore', str(self.backup), str(self.destination), '--inventory-sha256', sha],
                               cwd=self.root, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn('preserve all existing files', failed.stderr)


if __name__ == '__main__':
    unittest.main()
