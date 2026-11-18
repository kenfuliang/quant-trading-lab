#!/usr/bin/env python3
"""Run unittest discovery, time each test and fail if any single test is too slow.

Discovery matches `python -m unittest discover -s <start> -v`.
"""
import argparse
import os
import sys
import time
import unittest


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

    suite = unittest.TestLoader().discover(args.start)
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
