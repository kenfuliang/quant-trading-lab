import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paper_trading import durable_journal
from paper_trading.durable_journal import JournalLockError, WriterLock, atomic_write_json, leftover_temps


class DurableJournalTests(unittest.TestCase):
    def test_write_round_trips_with_private_mode_and_no_leftovers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal.json"
            atomic_write_json(path, [{"status": "reserved"}])
            self.assertEqual(json.loads(path.read_text()), [{"status": "reserved"}])
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(leftover_temps(tmp), [])

    def test_file_and_directory_are_fsynced_before_return(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(durable_journal.os, "fsync", wraps=os.fsync) as fsync:
                atomic_write_json(Path(tmp) / "journal.json", {})
            self.assertEqual(fsync.call_count, 2)

    def test_crash_before_replace_keeps_old_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal.json"
            atomic_write_json(path, {"v": 1})
            with mock.patch.object(durable_journal.os, "replace", side_effect=OSError("crash")):
                with self.assertRaises(OSError):
                    atomic_write_json(path, {"v": 2})
            self.assertEqual(json.loads(path.read_text()), {"v": 1})

    def test_leftover_temp_is_kept_as_evidence_and_does_not_block_next_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal.json"
            with mock.patch.object(durable_journal.os, "replace", side_effect=OSError("crash")):
                with self.assertRaises(OSError):
                    atomic_write_json(path, {"v": 1})
            self.assertEqual(len(leftover_temps(tmp)), 1)
            atomic_write_json(path, {"v": 2})
            self.assertEqual(json.loads(path.read_text()), {"v": 2})
            self.assertEqual(len(leftover_temps(tmp)), 1)

    def test_invalid_value_never_touches_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal.json"
            atomic_write_json(path, {"v": 1})
            with self.assertRaises(ValueError):
                atomic_write_json(path, {"v": float("nan")})
            self.assertEqual(json.loads(path.read_text()), {"v": 1})
            self.assertEqual(leftover_temps(tmp), [])

    def test_lock_held_fails_closed_and_stale_lock_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "writer.lock"
            with WriterLock(lock):
                with self.assertRaises(JournalLockError):
                    with WriterLock(lock):
                        pass
                self.assertTrue(lock.exists())
            self.assertFalse(lock.exists())
            lock.write_text("999")  # simulated crash leftover
            with self.assertRaises(JournalLockError):
                with WriterLock(lock):
                    pass
            self.assertEqual(lock.read_text(), "999")

    def test_alpaca_save_uses_the_atomic_writer(self):
        from paper_trading.alpaca import save
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal.json"
            with mock.patch.object(durable_journal.os, "replace", side_effect=OSError("crash")):
                with self.assertRaises(OSError):
                    save(path, [1])
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
