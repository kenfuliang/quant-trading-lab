#!/usr/bin/env python3
"""Create and check tracked validation receipts (validation-receipt/v1).

  create  write research/registry/validation-receipts/<id>.json (exclusive; validated first)
  check   load every receipt in the directory and validate it

Skill names are self-reported: this enforces separation of recorded roles, not the
independence of the model or session that produced the work. Offline only.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.control.validation_receipts import SCHEMA, ValidationReceiptError, load_receipt, utc_now, validate_receipt

RECEIPTS = ROOT / "research/registry/validation-receipts"


def parse_check(text):
    parts = text.split(":", 2)
    if len(parts) != 3:
        raise ValidationReceiptError(f"--check must be name:status:detail, got {text!r}")
    return {"name": parts[0], "status": parts[1], "detail": parts[2]}


def cmd_create(args):
    doc = {"schema": SCHEMA, "receipt_id": args.receipt_id, "created_utc": utc_now(),
           "run_ids": list(args.run_id), "parity_receipt_id": args.parity_receipt_id,
           "validator": {"skill": args.validator_skill},
           "researcher": {"skills": [s.strip() for s in args.researcher_skills.split(",") if s.strip()]},
           "checks": [parse_check(c) for c in args.check], "result": args.result, "notes": args.notes}
    validate_receipt(doc, args.receipt_id)
    target = Path(args.dir) / f"{args.receipt_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as handle:  # exclusive: never overwrite a receipt
        handle.write(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {target}")
    return 0


def cmd_check(args):
    paths = sorted(Path(args.dir).glob("*.json"))
    for path in paths:
        try:
            load_receipt(path)
        except ValidationReceiptError as error:
            print(f"error: {path.name}: {error}", file=sys.stderr)
            return 1
    print(f"Validation receipts passed: {len(paths)} receipts.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--receipt-id", required=True)
    create.add_argument("--run-id", action="append", required=True)
    create.add_argument("--parity-receipt-id", required=True)
    create.add_argument("--validator-skill", required=True)
    create.add_argument("--researcher-skills", required=True, help="comma-separated Research skills")
    create.add_argument("--check", action="append", default=[], help="name:status:detail (pass|fail|waived)")
    create.add_argument("--result", required=True, choices=("pass", "fail"))
    create.add_argument("--notes", default="")
    create.add_argument("--dir", default=str(RECEIPTS))
    create.set_defaults(fn=cmd_create)
    check = sub.add_parser("check")
    check.add_argument("--dir", default=str(RECEIPTS))
    check.set_defaults(fn=cmd_check)
    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except (ValidationReceiptError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
