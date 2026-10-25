#!/usr/bin/env python3
"""Render a supplied local research-review bundle without starting services."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reporting.recursive_research import render, register_local_review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--register-existing',type=Path,help='Verify an existing snapshot and link it from local performance home.')
    args = parser.parse_args()
    if args.register_existing:
        if args.input or args.output:
            parser.error('Registration is separate from rendering.')
        print(register_local_review(ROOT/'.local/performance',args.register_existing))
        return
    if not args.input or not args.output:
        parser.error('Rendering needs both --input and --output.')
    if args.output.exists():
        raise ValueError('Preserve the existing snapshot; select a new output directory.')
    print(render(json.loads(args.input.read_text()), args.output))


if __name__ == '__main__':
    main()
