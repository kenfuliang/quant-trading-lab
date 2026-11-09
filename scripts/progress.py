#!/usr/bin/env python3
"""Build the local progress page, or check the structured gates file. Offline and read-only.

  build   write .local/progress/progress.html (not tracked: it depends on today's date).
          Serve only that folder; evidence paths are links only with --links (file:// use).
  check   validate research/registry/gates.json and that every evidence path exists
"""
import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.control import experiment_registry as registry
from research.control.progress import build_model, render_html, validate_gates
from research.control.trial_ledger import LedgerError, read_ledger

GATES = ROOT / "research/registry/gates.json"
PLANS = ROOT / "research/registry/forward-plans"
LEDGER = ROOT / "research/registry/trial-ledger"


def exists(path):
    return (ROOT / path).exists()


def load_forward():
    plans = sorted(PLANS.glob("*.json"))
    if not plans:
        return None
    plan = json.loads(plans[-1].read_text())
    return {"start": plan["window"]["start"], "end": plan["window"]["end"], "holdout_id": plan["holdout_id"]}


def load_shadow(local):
    runs = [p for p in sorted((local / "shadow").glob("*/")) if (p / "summary.json").exists()] if (local / "shadow").is_dir() else []
    decisions = local / "shadow/decisions.jsonl"
    count = sum(1 for line in decisions.read_text().splitlines() if line.strip()) if decisions.exists() else 0
    return {"runs": len(runs), "decisions": count, "last_run": runs[-1].name if runs else None}


def load_ledger():
    try:
        events = read_ledger(LEDGER).events
    except LedgerError:
        return {"trials": 0, "events": 0}
    return {"trials": sum(1 for e in events if e["event"]["kind"] == "trial"), "events": len(events)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("build", "check"))
    parser.add_argument("--local", type=Path, default=ROOT / ".local")
    parser.add_argument("--out", type=Path, default=ROOT / ".local/progress/progress.html")
    parser.add_argument("--links", action="store_true", help="link evidence paths relative to the repo (for file:// viewing only)")
    args = parser.parse_args(argv)
    gates = json.loads(GATES.read_text())
    errors = validate_gates(gates, exists)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    if args.command == "check":
        print(f"Gates file passed: {sum(len(g['items']) for g in gates['gates'])} items; evidence paths exist.")
        return 0
    status = args.local / "status.json"
    health = json.loads(status.read_text()) if status.exists() else None
    model = build_model(gates, registry.load(ROOT / "research/registry/experiments.jsonl"), load_forward(),
                        load_shadow(args.local), health, load_ledger(), datetime.now(timezone.utc).date())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    depth = len(args.out.resolve().relative_to(ROOT).parts) - 1 if args.out.resolve().is_relative_to(ROOT) else 0
    args.out.write_text(render_html(model, (lambda p: "../" * depth + p if exists(p) else None) if args.links else (lambda p: None)))
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
