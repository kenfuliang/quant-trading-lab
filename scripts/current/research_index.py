#!/usr/bin/env python3
"""Generate or check research evidence navigation without executing research."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.control.evidence_index import generate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--write', action='store_true', help='Regenerate the two derived index files.')
    mode.add_argument('--check', action='store_true', help='Validate sources and fail on stale generated files; no writes.')
    args = parser.parse_args()
    try:
        coverage = generate(ROOT, write=args.write)
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(1, 'Research evidence index failed: ' + str(error) + '\n')
    print('Research evidence index passed: ' + str(coverage))


if __name__ == '__main__':
    main()
