import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from research.evaluation.run_output import (
    COLUMNS,
    MANIFEST_KEYS,
    SCHEMA,
    RunOutputError,
    config_hash,
    new_run_id,
    read_run,
    write_run,
)


class RunOutputTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.manifest = {key: f"value-{key}" for key in MANIFEST_KEYS}
        self.manifest.update(schema=SCHEMA, run_id="20261117T083000Z-abcd1234", config={"a": 1}, datasets=[], coverage={}, parent_run=None)
        date = pd.Timestamp("2026-01-02")
        rows = {
            "returns": [date, 0.01, 0.001, 0.009, 1.009],
            "positions": [date, "SPY", 10.0, 0.5],
            "signals": [date, "SPY", "trend", 1.0],
            "fills": [date, "SPY", "buy", 10.0, 100.0, 0.5],
        }
        self.tables = {name: pd.DataFrame([rows[name]], columns=list(COLUMNS[name])) for name in COLUMNS}

    def test_round_trip_preserves_tables_and_records_hashes(self):
        path = write_run(self.root, self.manifest, self.tables)
        manifest, tables = read_run(path)
        self.assertEqual(set(manifest["files"]), {"returns", "positions", "signals", "fills"})
        for name in COLUMNS:
            pd.testing.assert_frame_equal(tables[name], self.tables[name])

    def test_refuses_existing_run_directory(self):
        write_run(self.root, self.manifest, self.tables)
        with self.assertRaises(RunOutputError):
            write_run(self.root, self.manifest, self.tables)

    def test_detects_tampered_file(self):
        path = write_run(self.root, self.manifest, self.tables)
        (path / "fills.parquet").write_bytes(b"x")
        with self.assertRaises(RunOutputError):
            read_run(path)

    def test_rejects_missing_column_and_missing_manifest_key(self):
        bad = dict(self.tables, returns=self.tables["returns"].drop(columns="equity"))
        with self.assertRaises(RunOutputError):
            write_run(self.root, self.manifest, bad)
        with self.assertRaises(RunOutputError):
            write_run(self.root, {k: v for k, v in self.manifest.items() if k != "engine"}, self.tables)

    def test_run_id_and_config_hash_are_deterministic(self):
        now = datetime(2026, 11, 17, 8, 30, tzinfo=timezone.utc)
        self.assertEqual(config_hash({"b": 1, "a": 2}), config_hash({"a": 2, "b": 1}))
        self.assertTrue(new_run_id({"a": 1}, now).startswith("20261117T083000Z-"))


if __name__ == "__main__":
    unittest.main()
