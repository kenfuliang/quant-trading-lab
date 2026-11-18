#!/usr/bin/env python3
"""Local ETF data library commands.

  fetch-yahoo   take one receipted raw Yahoo chart snapshot under <data root>/raw/yahoo/<snapshot-id>/

The only command that uses the network is fetch-yahoo; every request is receipted.
Exit codes: 0 ok, 1 failure or incomplete snapshot, 2 data absent.
"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.data.manifest import ManifestError
from research.data.root import DataAbsent, data_root
from research.data.yahoo_snapshot import SnapshotIncomplete, fetch_snapshot


def cmd_fetch_yahoo(args):
    root = Path(args.root) if args.root else data_root()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    if not symbols:
        print("error: no symbols given", file=sys.stderr)
        return 1
    try:
        folder = fetch_snapshot(symbols, args.start, args.end, args.snapshot_id, root)
    except SnapshotIncomplete as error:
        print(f"error: {error}; receipt {error.snapshot_dir / 'requests.json'}", file=sys.stderr)
        print(f"manifest {root / 'manifests' / (args.snapshot_id + '.json')}", file=sys.stderr)
        return 1
    except (ValueError, ManifestError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except FileExistsError as error:
        print(f"error: snapshot already exists: {error.filename}", file=sys.stderr)
        return 1
    print(f"Snapshot {args.snapshot_id}: {len(symbols)} received in {folder}")
    print(f"manifest {root / 'manifests' / (args.snapshot_id + '.json')}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    fy = sub.add_parser("fetch-yahoo", help="fetch a receipted raw Yahoo snapshot")
    fy.add_argument("--symbols", required=True, help="comma-separated, e.g. SPY,XLB")
    fy.add_argument("--start", required=True, help="YYYY-MM-DD")
    fy.add_argument("--end", required=True, help="YYYY-MM-DD, inclusive")
    fy.add_argument("--snapshot-id", required=True)
    fy.add_argument("--root", help="data root (default: shared data root)")
    fy.set_defaults(func=cmd_fetch_yahoo)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except DataAbsent as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
