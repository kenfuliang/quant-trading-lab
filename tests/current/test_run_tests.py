"""Test-duration guard: the runner names a test that exceeds the limit."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_tests.py"

SLOW = """import time, unittest
class T(unittest.TestCase):
    def test_sleepy(self):
        time.sleep(0.5)
"""
FAST = """import unittest
class T(unittest.TestCase):
    def test_quick(self):
        self.assertTrue(True)
"""


def run_runner(source, *extra):
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "test_sample.py").write_text(source)
        return subprocess.run(
            [sys.executable, str(RUNNER), "--start", tmp, *extra],
            capture_output=True, text=True, cwd=ROOT, timeout=60)


class RunTestsTests(unittest.TestCase):
    def test_slow_test_fails_with_name(self):
        result = run_runner(SLOW, "--max-seconds", "0.2")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("test_sleepy", result.stdout + result.stderr)
        self.assertIn("exceeded", result.stdout + result.stderr)

    def test_fast_suite_passes(self):
        result = run_runner(FAST, "--max-seconds", "5")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Slowest", result.stdout + result.stderr)

    def test_zero_tests_discovered_fails(self):
        result = run_runner("x = 1\n")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("no tests discovered", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
