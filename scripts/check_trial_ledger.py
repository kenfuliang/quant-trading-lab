#!/usr/bin/env python3
"""Verify a trial-ledger hash chain and optionally audit one receipt for leakage; never writes."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.control.leakage_audit import audit_receipt
from research.control.trial_ledger import LedgerError, read_ledger


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ledger', type=Path, help='Ledger directory (contains ledger.jsonl)')
    parser.add_argument('--receipt', type=Path, help='Receipt to audit against this ledger')
    parser.add_argument('--root', type=Path, help='Artifact root (default: receipt directory)')
    args = parser.parse_args()
    try:
        view = read_ledger(args.ledger)
    except LedgerError as exc:
        print(f'Ledger invalid: {exc}', file=sys.stderr)
        return 1
    print(f'Ledger chain valid: {len(view.events)} event(s), head {view.head_hash[:12]}'
          + (' (head update pending; reopen as writer to resume)' if view.head_lag else '')
          + (' (torn unacknowledged tail ignored)' if view.torn_tail else ''))
    if args.receipt is None:
        return 0
    try:
        receipt = json.loads(args.receipt.read_text())
    except (OSError, ValueError) as exc:
        print(f'Receipt unreadable: {exc}', file=sys.stderr)
        return 1
    errors = audit_receipt(receipt, args.root or args.receipt.parent, ledger_dir=args.ledger)
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('Leakage audit passed: ledger-recorded evidence only; no proof the holdout data was unread.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
