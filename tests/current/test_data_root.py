import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from research.data.root import DataAbsent, data_root, parity_root, require, runs_root


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args],
                   cwd=cwd, check=True, capture_output=True)


class DataRootTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name).resolve()
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("QTL_DATA_ROOT", None)

    def test_env_var_wins(self):
        os.environ["QTL_DATA_ROOT"] = str(self.tmp / "custom")
        self.assertEqual(data_root(), self.tmp / "custom")
        self.assertEqual(runs_root(), self.tmp / "custom" / "runs")
        self.assertEqual(parity_root(), self.tmp / "custom" / "parity")

    def test_worktree_resolves_main_checkout_data(self):
        main = self.tmp / "main"
        main.mkdir()
        _git(main, "init", "-q")
        (main / "f.txt").write_text("x", encoding="utf-8")
        _git(main, "add", "f.txt")
        _git(main, "commit", "-q", "-m", "init")
        wt = self.tmp / "wt"
        _git(main, "worktree", "add", "-q", "-b", "side", str(wt))
        self.assertEqual(data_root(wt), main / "data")
        self.assertEqual(data_root(wt / "."), main / "data")

    def test_main_checkout_resolves_its_own_data(self):
        main = self.tmp / "main"
        main.mkdir()
        _git(main, "init", "-q")
        self.assertEqual(data_root(main), main / "data")

    def test_require_raises_blocked_message(self):
        missing = self.tmp / "absent.json"
        with self.assertRaises(DataAbsent) as ctx:
            require(missing)
        self.assertEqual(str(ctx.exception), f"blocked: data absent: {missing}")
        present = self.tmp / "here.json"
        present.write_text("{}", encoding="utf-8")
        self.assertEqual(require(present), present)


if __name__ == "__main__":
    unittest.main()
