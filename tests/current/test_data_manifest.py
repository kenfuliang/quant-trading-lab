import hashlib
import tempfile
import unittest
from pathlib import Path

from research.data import manifest as m


def make(root: Path, dataset_id="ds-1"):
    f = root / "raw" / "a.json"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"hello")
    return {
        "schema": m.SCHEMA, "dataset_id": dataset_id, "kind": "raw-snapshot",
        "created_utc": "2026-11-18T00:00:00Z", "source": "test", "inputs": [], "recipe": None,
        "rights": {"source": "yahoo"},
        "files": [{"path": "raw/a.json", "sha256": hashlib.sha256(b"hello").hexdigest()}],
        "notes": "",
    }


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.root = Path(self._t.name)

    def test_manifest_round_trip_and_exclusive_write(self):
        doc = make(self.root)
        path = m.write_manifest(self.root, doc)
        self.assertEqual(path, self.root / "manifests" / "ds-1.json")
        self.assertEqual(m.read_manifest(self.root, "ds-1"), doc)
        with self.assertRaises(FileExistsError):
            m.write_manifest(self.root, doc)

    def test_invalid_kind_and_keys_are_refused(self):
        doc = make(self.root)
        doc["kind"] = "bogus"
        with self.assertRaises(m.ManifestError):
            m.write_manifest(self.root, doc)
        doc = dict(doc, kind="raw-snapshot")
        del doc["rights"]
        with self.assertRaises(m.ManifestError):
            m.write_manifest(self.root, doc)

    def test_absolute_and_parent_paths_are_refused_on_read(self):
        for bad in ("/etc/hosts", "../outside.json"):
            doc = make(self.root, "ds-" + str(abs(hash(bad))))
            doc["files"] = [{"path": bad, "sha256": "0" * 64}]
            m.write_manifest(self.root, doc)
            with self.assertRaisesRegex(m.ManifestError, "path"):
                m.read_manifest(self.root, doc["dataset_id"])
            self.root.joinpath("raw", "a.json").unlink()
            self.root.joinpath("raw").rmdir()

    def test_sha256_mismatch_and_missing_file_are_refused(self):
        m.write_manifest(self.root, make(self.root))
        (self.root / "raw" / "a.json").write_bytes(b"tampered")
        with self.assertRaisesRegex(m.ManifestError, r"raw/a\.json: sha256 mismatch"):
            m.read_manifest(self.root, "ds-1")
        self.assertEqual(m.read_manifest(self.root, "ds-1", verify=False)["dataset_id"], "ds-1")
        (self.root / "raw" / "a.json").unlink()
        with self.assertRaisesRegex(m.ManifestError, r"raw/a\.json: missing"):
            m.read_manifest(self.root, "ds-1")

    def test_input_hashes_are_verified_too(self):
        doc = make(self.root)
        doc["inputs"] = [{"path": "raw/a.json", "sha256": "0" * 64}]
        m.write_manifest(self.root, doc)
        with self.assertRaisesRegex(m.ManifestError, "sha256 mismatch"):
            m.read_manifest(self.root, "ds-1")


if __name__ == "__main__":
    unittest.main()
