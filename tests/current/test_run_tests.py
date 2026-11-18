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


REMOTE = """import socket, unittest
class T(unittest.TestCase):
    def test_remote_connect(self):
        socket.create_connection(("192.0.2.1", 80), timeout=0.5)
"""
LOOPBACK = """import http.server, threading, unittest, urllib.request
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, *args):
        pass
class T(unittest.TestCase):
    def test_loopback_fetch(self):
        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            url = "http://127.0.0.1:%d/" % server.server_address[1]
            self.assertEqual(urllib.request.urlopen(url, timeout=5).read(), b"ok")
        finally:
            server.shutdown()
            server.server_close()
"""


class RunTestsTests(unittest.TestCase):
    def test_non_loopback_connection_fails_naming_test(self):
        result = run_runner(REMOTE, "--max-seconds", "5")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 1, output)
        self.assertIn("test_remote_connect", output)
        self.assertIn("network access blocked in tests: 192.0.2.1:80", output)

    def test_loopback_server_allowed(self):
        result = run_runner(LOOPBACK, "--max-seconds", "10")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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
