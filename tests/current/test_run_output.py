import json
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
        self.manifest.update(schema=SCHEMA, run_id="20261117T083000Z-abcd1234", config={"a": 1},
                             config_hash=config_hash({"a": 1}), datasets=[], coverage={}, parent_run=None)
        date = "2026-01-02"
        rows = {
            "returns": [date, 0.01, 0.001, 0.009, 1.009],
            "positions": [date, "SPY", 10, 0.5],
            "signals": [date, "SPY", "trend", 1.0],
            "fills": [date, "SPY", "BUY", 10, 100.0, 0.5],
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


    def test_rejects_wrong_dtypes(self):
        cases = {
            "float quantity": ("positions", "quantity", 10.5),
            "float-typed integral quantity": ("fills", "quantity", 10.0),
            "timestamp date": ("returns", "date", pd.Timestamp("2026-01-02")),
            "badly formatted date": ("signals", "date", "2026/01/02"),
            "string price": ("fills", "price", "100.0"),
            "bool weight": ("positions", "weight", True),
            "numeric instrument": ("signals", "instrument", 1),
        }
        for label, (name, column, value) in cases.items():
            frame = self.tables[name].copy()
            frame[column] = [value]
            with self.subTest(label), self.assertRaises(RunOutputError):
                write_run(self.root, self.manifest, dict(self.tables, **{name: frame}))

    def test_typed_empty_tables_round_trip(self):
        tables = dict(self.tables, fills=self.tables["fills"].iloc[0:0], signals=self.tables["signals"].iloc[0:0])
        manifest, read = read_run(write_run(self.root, self.manifest, tables))
        self.assertTrue(read["fills"].empty)

    def test_config_hash_must_match_config(self):
        with self.assertRaisesRegex(RunOutputError, "config_hash"):
            write_run(self.root, dict(self.manifest, config_hash="0" * 64), self.tables)
        path = write_run(self.root, self.manifest, self.tables)
        manifest_path = path / "manifest.json"
        stored = json.loads(manifest_path.read_text(encoding="utf-8"))
        stored["config"] = {"a": 2}
        manifest_path.write_text(json.dumps(stored), encoding="utf-8")
        with self.assertRaisesRegex(RunOutputError, "config_hash"):
            read_run(path)

    def test_docstring_states_units(self):
        import research.evaluation.run_output as module

        for phrase in ("YYYY-MM-DD", "fraction of the", "USD", "integer"):
            self.assertIn(phrase, module.__doc__)


if __name__ == "__main__":
    unittest.main()
