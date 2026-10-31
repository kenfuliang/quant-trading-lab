#!/usr/bin/env python3
"""Validate one explicit experiment receipt and its local artifacts; never execute it."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.control.experiment_receipts import validate_receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipt', type=Path)
    parser.add_argument('--root', type=Path, required=True, help='Allowed artifact root; receipt paths are relative to this directory')
    args = parser.parse_args()
    try:
        receipt = json.loads(args.receipt.read_text(), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f'nonfinite JSON: {value}')))
        errors = validate_receipt(receipt, args.root)
    except (OSError, ValueError) as exc:
        print(f'Receipt unreadable: {exc}', file=sys.stderr)
        return 1
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('Receipt valid: structure and explicit local artifact hashes only; no financial or operational certification.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
