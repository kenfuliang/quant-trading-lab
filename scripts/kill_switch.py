#!/usr/bin/env python3
"""Operator CLI for the kill switch. Offline; touches only the sentinel and its log."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from paper_trading.kill_switch import KillSwitch, KillSwitchError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", help="sentinel path (default: QTL_KILL_SWITCH or .local/kill-switch/HALT)")
    sub = parser.add_subparsers(dest="command", required=True)
    engage = sub.add_parser("engage")
    engage.add_argument("--reason", required=True)
    engage.add_argument("--actor", default="operator")
    release = sub.add_parser("release")
    release.add_argument("--actor", required=True)
    release.add_argument("--note", required=True)
    sub.add_parser("status")
    args = parser.parse_args(argv)
    switch = KillSwitch(args.path)
    try:
        if args.command == "engage":
            result = switch.engage(args.reason, args.actor)
        elif args.command == "release":
            switch.release(args.actor, args.note)
            result = switch.status()
        else:
            result = switch.status()
    except KillSwitchError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 1 if result["engaged"] and args.command == "status" else 0


if __name__ == "__main__":
    sys.exit(main())
