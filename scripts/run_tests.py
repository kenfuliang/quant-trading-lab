#!/usr/bin/env python3
"""Run unittest discovery, time each test and fail if any single test is too slow.

Discovery matches `python -m unittest discover -s <start> -v`.
"""
import argparse
import ipaddress
import os
import socket
import sys
import time
import unittest


class NetworkBlocked(OSError):
    """Raised when a test tries to reach a non-loopback network address."""


def _is_loopback(host):
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def install_network_guard():
    """Block AF_INET/AF_INET6 connects to anything but loopback; AF_UNIX passes."""
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def check(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6) and isinstance(address, tuple):
            host, port = address[0], address[1]
            if not _is_loopback(host):
                raise NetworkBlocked(f"network access blocked in tests: {host}:{port}")

    def connect(self, address):
        check(self, address)
        return original_connect(self, address)

    def connect_ex(self, address):
        check(self, address)
        return original_connect_ex(self, address)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex


class TimedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.durations = []
        self._started = 0.0

    def startTest(self, test):
        self._started = time.perf_counter()
        super().startTest(test)

    def stopTest(self, test):
        self.durations.append((time.perf_counter() - self._started, test.id()))
        super().stopTest(test)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-seconds", type=float, default=30.0,
                        help="fail if any single test takes longer (default 30)")
    parser.add_argument("--start", default="tests", help="discovery start directory")
    args = parser.parse_args(argv)
    sys.path.insert(0, os.getcwd())  # same as `python -m unittest`: cwd is importable

    install_network_guard()
    suite = unittest.TestLoader().discover(args.start)
    if suite.countTestCases() == 0:
        print(f"FAIL: no tests discovered under {args.start}", file=sys.stderr)
        return 1
    runner = unittest.TextTestRunner(verbosity=2, resultclass=TimedResult)
    result = runner.run(suite)

    slowest = sorted(result.durations, reverse=True)[:10]
    print("\nSlowest ten tests:")
    for seconds, name in slowest:
        print(f"  {seconds:8.3f}s  {name}")

    slow = [(s, n) for s, n in slowest if s > args.max_seconds]
    for seconds, name in slow:
        print(f"FAIL: {name} took {seconds:.3f}s, exceeded the {args.max_seconds:g}s limit")
    if slow:
        return 1
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
