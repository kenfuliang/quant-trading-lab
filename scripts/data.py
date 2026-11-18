#!/usr/bin/env python3
"""Local ETF data library commands.

  fetch-yahoo   take one receipted raw Yahoo chart snapshot under <data root>/raw/yahoo/<snapshot-id>/
  normalise     prove the etf-normalise/v1 recipe applies to a bars+actions pair and write a manifest

The only command that uses the network is fetch-yahoo; every request is receipted.
Exit codes: 0 ok, 1 failure or incomplete snapshot, 2 data absent.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.data.manifest import ManifestError, sha256_file, write_manifest
from research.data.root import DataAbsent, data_root, require
from research.data.yahoo_snapshot import SnapshotIncomplete, fetch_snapshot
from research.evaluation.etf_normalise import RECIPE, normalise
from research.evaluation.market_model import MarketDataError


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


def _relative(root: Path, path: Path) -> str:
    absolute, base = os.path.abspath(path), os.path.abspath(root)
    if os.path.commonpath([absolute, base]) != base:
        raise ValueError(f"{path}: input must be inside the data root {root}")
    return Path(os.path.relpath(absolute, base)).as_posix()


def cmd_normalise(args):
    root = Path(args.root) if args.root else data_root()
    bars_path, actions_path = require(Path(args.bars)), require(Path(args.actions))
    try:
        inputs = [{"path": _relative(root, p), "sha256": sha256_file(p)} for p in (bars_path, actions_path)]
        source_path = require(root / "manifests" / (bars_path.stem + ".json"))
        source = json.loads(source_path.read_text(encoding="utf-8"))
        rows = json.loads(bars_path.read_text(encoding="utf-8"))
        actions = json.loads(actions_path.read_text(encoding="utf-8"))
        instruments = tuple(sorted({row["symbol"] for row in rows}))
        result = normalise(rows, actions, instruments)
        rights = {"source": "alpaca", "redistribution": "not_qualified", "source_manifest": bars_path.stem}
        for key in ("feed", "adjustment", "personal_use_review"):
            if key in source:
                rights[key] = source[key]
        changed = sum(sum(counts.values()) for counts in result.rounding.values())
        notes = (f"rounding changed {changed} values; converted {len(result.converted)}; "
                 f"excluded {len(result.excluded)}")
        manifest = {
            "schema": "dataset-manifest/v1", "dataset_id": args.dataset_id, "kind": "normalised",
            "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": f"alpaca, normalised on load from {bars_path.stem}",
            "inputs": inputs, "recipe": RECIPE, "rights": rights, "files": [], "notes": notes,
        }
        path = write_manifest(root, manifest)
    except FileExistsError as error:
        print(f"error: manifest already exists: {error.filename}", file=sys.stderr)
        return 1
    except (ValueError, ManifestError, MarketDataError, KeyError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Normalised {args.dataset_id}: {len(instruments)} instruments, {len(result.data.sessions)} sessions")
    print(f"rounding changed {changed} values")
    for symbol, counts in result.rounding.items():
        if any(counts.values()):
            print(f"  {symbol}: " + ", ".join(f"{k} {v}" for k, v in counts.items() if v))
    print(f"converted {len(result.converted)}")
    for event in result.converted:
        print(f"  {event['id']}: per share {event['per_share']} ({event['label']})")
    print(f"excluded {len(result.excluded)}")
    for event in result.excluded:
        print(f"  {event['id']}: {event['reason']}")
    print(f"manifest {path}")
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
    nm = sub.add_parser("normalise", help="apply etf-normalise/v1 and write a normalised manifest")
    nm.add_argument("--bars", required=True, help="source bars JSON inside the data root")
    nm.add_argument("--actions", required=True, help="source issuer-actions JSON inside the data root")
    nm.add_argument("--dataset-id", required=True)
    nm.add_argument("--root", help="data root (default: shared data root)")
    nm.set_defaults(func=cmd_normalise)
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
