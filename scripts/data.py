#!/usr/bin/env python3
"""Local ETF data library commands.

  fetch-yahoo   take one receipted raw Yahoo chart snapshot under <data root>/raw/yahoo/<snapshot-id>/
  fetch-github  take one receipted raw GitHub snapshot (S&P 500 membership sources) under <data root>/raw/github/
  membership    build membership/v1 from that snapshot (no network)
  stock-actions write etf-normalise-format stock actions from a Yahoo stock snapshot (no network)
  identity      write instrument-identity/v1 (archive ids + membership symbols + sourced ticker changes)
                under <data root>/identity/ and re-run the membership cross-checks with renames resolved
  coverage      write membership-coverage/v1: per session, index members with data in a stock dataset
  normalise     prove the etf-normalise/v1 recipe applies to a bars+actions pair (or a per-symbol
                bars directory) and write a manifest
  quality       write a quality-report/v1 for a normalised dataset (optionally cross-checked to Yahoo)

The only commands that use the network are fetch-yahoo and fetch-github; every request is receipted.
Exit codes: 0 ok, 1 failure or incomplete snapshot, 2 data absent.
"""
import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.data import github_snapshot, identity as identity_lib, membership as membership_lib
from research.data.manifest import ManifestError, read_manifest, sha256_file, write_manifest
from research.data.root import DataAbsent, data_root, require
from research.data.stock_actions import build_stock_actions, read_symbols_file, write_actions, yahoo_symbol
from research.data.yahoo_snapshot import STOCK_RIGHTS, SnapshotIncomplete, fetch_snapshot, parse_chart
from research.evaluation.data_quality import build_failure_report, build_report, write_report
from research.evaluation.datasets import load_dataset, read_inputs
from research.evaluation.etf_normalise import RECIPE, normalise
from research.evaluation.market_model import MarketDataError


# Acquisition manifests written before manifests carried a `source` field.
LEGACY_SOURCES = {"sector-etf-acquisition-v1": "alpaca", "current-spy-stock-library-v1": "alpaca",
                  "alpaca-pilot-v1": "alpaca"}


def cmd_fetch_yahoo(args):
    root = Path(args.root) if args.root else data_root()
    options = {}
    if args.symbols_file:
        try:
            symbols, rejected = read_symbols_file(require(Path(args.symbols_file)))
        except (OSError, ValueError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        for item in rejected:
            print(f"rejected {item['symbol']!r}: {item['reason']}", file=sys.stderr)
        mapped = {s: yahoo_symbol(s) for s in symbols if yahoo_symbol(s) != s}
        options = {"rights": STOCK_RIGHTS, "symbol_map": mapped, "pause": args.pause,
                   "max_consecutive_http_failures": 5,
                   "notes_extra": f"; symbols not fetched (fail SYMBOL_RE): {[r['symbol'] for r in rejected] or 'none'}"
                                  f"; dot-to-dash request map: {mapped or 'none'}"}
    else:
        symbols = [s.strip().upper() for s in (args.symbols or "").split(",") if s.strip()]
    if not symbols:
        print("error: no symbols given", file=sys.stderr)
        return 1
    try:
        folder = fetch_snapshot(symbols, args.start, args.end, args.snapshot_id, root, **options)
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


def cmd_fetch_github(args):
    root = Path(args.root) if args.root else data_root()
    try:
        if args.url:  # explicit follow-up fetch of named URLs (host-checked), no discovery
            urls = dict(item.split("=", 1) for item in args.url)
            folder = github_snapshot.fetch_urls(urls, args.snapshot_id, root)
        else:
            folder = github_snapshot.fetch_urls(github_snapshot.membership_sources(), args.snapshot_id, root,
                                                expand=github_snapshot.expand_membership)
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
    print(f"GitHub snapshot {args.snapshot_id} in {folder}")
    print(f"manifest {root / 'manifests' / (args.snapshot_id + '.json')}")
    return 0


def cmd_membership(args):
    root = Path(args.root) if args.root else data_root()
    try:
        for snapshot in args.snapshot:
            require(root / "manifests" / (snapshot + ".json"))
        doc, inputs, rights = membership_lib.build_from_snapshot(root, args.snapshot, args.membership_id)
        path = membership_lib.write_membership(root, doc)
        write_manifest(root, membership_lib.membership_manifest(root, doc, path, inputs, rights))
    except FileExistsError as error:
        print(f"error: refusing to overwrite {error.filename}", file=sys.stderr)
        return 1
    except (ValueError, ManifestError, OSError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    intervals = doc["intervals"]
    print(f"Membership {args.membership_id}: {sum(len(v) for v in intervals.values())} intervals "
          f"for {len(intervals)} symbols")
    for check in doc["spot_checks"]:
        print(f"  spot {check['name']}: {check['result']} ({json.dumps(check['observed'])[:120]})")
    for check in doc["cross_checks"]:
        print(f"  cross-check {check['source']}: {check['status']}"
              + (f" ({check['reason']})" if check.get("reason") else ""))
    print(f"membership {path}")
    return 0


def cmd_stock_actions(args):
    root = Path(args.root) if args.root else data_root()
    try:
        manifest = read_manifest(root, args.snapshot)
        out = root / args.out
        _relative(root, out)
        actions, excluded = build_stock_actions(manifest, root)
        path = write_actions(out, actions)
    except FileExistsError as error:
        print(f"error: refusing to overwrite {error.filename}", file=sys.stderr)
        return 1
    except (ValueError, ManifestError, OSError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Stock actions from {args.snapshot}: {len(actions['splits'])} splits, "
          f"{len(actions['cash_and_in_kind'])} dividends, {len(excluded)} excluded symbols")
    for item in excluded:
        print(f"  excluded {item['symbol']}: {item['reason']}")
    print(f"actions {path}")
    return 0


TICKER_CHANGES = ROOT / "research/registry/ticker-changes.json"


def _other_sources(root: Path, membership_id: str) -> dict:
    """Parsed cross-check sources named in the membership manifest's inputs (verified by hash)."""
    manifest = read_manifest(root, membership_id)
    found = {}
    for entry in manifest["inputs"]:
        name = Path(entry["path"]).name
        if name == "hanshof-constituents.csv":
            found["hanshof"] = membership_lib.parse_current_list((root / entry["path"]).read_text(encoding="utf-8"))
        elif name == "index-constitution-sp500.csv":
            found["index"] = membership_lib.parse_opt_in_out((root / entry["path"]).read_text(encoding="utf-8"))
    return found


def _resolved_checks(root: Path, membership: dict, identity: dict) -> list:
    """Re-run the membership cross-checks with renames resolved; report before and after counts."""
    days = membership_lib.first_trading_days()
    before = {c["source"]: c for c in membership["cross_checks"]}
    out = []
    try:
        sources = _other_sources(root, membership["membership_id"])
    except (ManifestError, OSError, ValueError) as error:
        return [{"source": "all", "status": "blocked", "reason": f"cross-check sources unreadable: {error}"}]
    for key, repo in (("hanshof", membership_lib.HANSHOF_REPO), ("index", membership_lib.INDEX_REPO)):
        if key not in sources:
            out.append({"source": repo, "status": "blocked", "reason": "source file not among the membership inputs"})
            continue
        if key == "hanshof":
            as_of, added = sources[key]
            known = {day: [s for s, a in added.items() if a and a <= day] for day in days}
            dates = identity_lib.cross_check_resolved(membership, identity, {as_of: set(added)}, one_sided=known)
        else:
            dates = identity_lib.cross_check_resolved(
                membership, identity, {d: membership_lib.membership_on(sources[key], d) for d in days})
        old = (before.get(repo) or {}).get("dates", {})
        tally = {"before": {"only_primary": sum(v.get("only_primary_count", 0) for v in old.values()),
                            "only_other": sum(v.get("only_other_count", 0) for v in old.values())},
                 "after": {"only_primary": sum(v.get("only_primary_count", 0) for v in dates.values()),
                           "only_other": sum(v.get("only_other_count", 0) for v in dates.values())}}
        out.append({"source": repo, "status": "done", "totals": tally, "dates": dates})
    return out


def cmd_identity(args):
    root = Path(args.root) if args.root else data_root()
    try:
        archive = json.loads(require(root / "manifests" / (args.archive + ".json")).read_text(encoding="utf-8"))
        membership = membership_lib.read_membership(root, args.membership_id)
        changes = identity_lib.load_ticker_changes(args.ticker_changes)
        doc = identity_lib.build_identity(archive, membership, changes)
        doc["identity_id"] = args.identity_id
        doc["created_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        doc["cross_checks"] = _resolved_checks(root, membership, doc)
        path = identity_lib.write_identity(root, doc)
    except FileExistsError as error:
        print(f"error: refusing to overwrite {error.filename}", file=sys.stderr)
        return 1
    except (ValueError, ManifestError, OSError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    counts = doc["counts"]
    print(f"Identity {args.identity_id}: {counts['current_ids']} current ids, {counts['historical_only_ids']} "
          f"historical-only ids, {counts['aliases']} aliases, {counts['symbols']} symbols")
    print(f"  ticker changes applied {counts['ticker_changes_applied']}, unapplied {counts['ticker_changes_unapplied']}; "
          f"unresolved candidates {counts['unresolved_candidates']}")
    for check in doc["cross_checks"]:
        print(f"  cross-check {check['source']}: {check['status']} "
              + (json.dumps(check["totals"]) if "totals" in check else check.get("reason", "")))
    print(f"identity {path}")
    return 0


def cmd_coverage(args):
    root = Path(args.root) if args.root else data_root()
    try:
        membership = membership_lib.read_membership(root, args.membership_id)
        identity = identity_lib.read_identity(root, args.identity_id)
        manifest = read_manifest(root, args.dataset_id)
        rows, _actions = read_inputs(root, manifest)
        symbols = tuple(sorted({row["symbol"] for row in rows}))
        data, _provenance = load_dataset(args.dataset_id, symbols, root)
        doc = identity_lib.coverage(membership, identity, list(data.bars), data.sessions)
        doc["dataset_id"] = args.dataset_id
        path = identity_lib.write_coverage(root, doc, args.coverage_id)
    except FileExistsError as error:
        print(f"error: refusing to overwrite {error.filename}", file=sys.stderr)
        return 1
    except (ValueError, ManifestError, MarketDataError, OSError, KeyError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    summary = doc["summary"]
    print(f"Coverage {args.coverage_id}: {summary['sessions']} sessions, {doc['dataset_symbols']} dataset symbols; "
          f"share of index members with data: min {summary['min_share']:.4f}, median {summary['median_share']:.4f}")
    for item in summary["worst_dates"]:
        print(f"  worst {item['date']}: {item['with_data']} of {item['in_index']} ({item['share']:.4f})")
    print(f"coverage {path}")
    return 0


def _relative(root: Path, path: Path) -> str:
    absolute, base = os.path.abspath(path), os.path.abspath(root)
    if os.path.commonpath([absolute, base]) != base:
        raise ValueError(f"{path}: input must be inside the data root {root}")
    return Path(os.path.relpath(absolute, base)).as_posix()


def _stock_inputs(root: Path, args):
    """Per-symbol bar files for the coverage-listed symbols, minus the actions file's excluded symbols."""
    bars_dir = require(root / args.bars_dir)
    coverage = require(root / args.symbols_from)
    with open(coverage, newline="", encoding="utf-8") as handle:
        listed = [row["symbol"] for row in csv.DictReader(handle) if row["status"] == args.status]
    if not listed:
        raise ValueError(f"{args.symbols_from}: no symbols with status {args.status!r}")
    actions = json.loads(require(root / args.actions).read_text(encoding="utf-8"))
    excluded = actions.get("excluded_symbols", []) if args.exclude_from_actions else []
    dropped = {item["symbol"] for item in excluded}
    symbols = [symbol for symbol in listed if symbol not in dropped]
    paths = [require(bars_dir / f"{symbol}.json") for symbol in symbols]
    return symbols, paths, excluded, len(listed)


def cmd_normalise(args):
    root = Path(args.root) if args.root else data_root()
    stock = bool(args.bars_dir)
    if stock == bool(args.bars):
        print("error: give exactly one of --bars or --bars-dir", file=sys.stderr)
        return 1
    if stock and not (args.symbols_from and args.status):
        print("error: --bars-dir needs --symbols-from and --status", file=sys.stderr)
        return 1
    actions_path = require(root / args.actions) if stock else require(Path(args.actions))
    try:
        if stock:
            symbols, bar_paths, excluded, listed = _stock_inputs(root, args)
            bars_stem = Path(args.bars_dir).name
        else:
            bar_paths, excluded, listed = [require(Path(args.bars))], [], 0
            bars_stem = bar_paths[0].stem
        inputs = [{"path": _relative(root, p), "sha256": sha256_file(p)} for p in (*bar_paths, actions_path)]
        source_path = require(root / "manifests" / (bars_stem + ".json"))
        source = json.loads(source_path.read_text(encoding="utf-8"))
        rows = []
        for path in bar_paths:
            rows.extend(json.loads(path.read_text(encoding="utf-8")))
        actions = json.loads(actions_path.read_text(encoding="utf-8"))
        instruments = tuple(sorted({row["symbol"] for row in rows}))
        result = normalise(rows, actions, instruments)
        provider = source.get("source") or LEGACY_SOURCES.get(source.get("schema"))
        if not provider:
            raise ValueError(f"{source_path}: source manifest has no 'source' field "
                             f"and an unknown schema {source.get('schema')!r}")
        rights = {"source": provider, "redistribution": "not_qualified", "source_manifest": bars_stem}
        for key in ("feed", "adjustment", "personal_use_review"):
            if key in source:
                rights[key] = source[key]
        changed = sum(sum(counts.values()) for counts in result.rounding.values())
        notes = (f"rounding changed {changed} values; converted {len(result.converted)}; "
                 f"excluded {len(result.excluded)}")
        if stock:
            notes += (f"; universe {len(symbols)} of {listed} {args.status} symbols; "
                      f"excluded symbols ({len(excluded)}): "
                      + "; ".join(f"{item['symbol']}: {item['reason']}" for item in excluded))
        manifest = {
            "schema": "dataset-manifest/v1", "dataset_id": args.dataset_id, "kind": "normalised",
            "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": f"{provider}, normalised on load from {bars_stem}",
            "inputs": inputs, "recipe": RECIPE, "rights": rights, "files": [], "notes": notes,
        }
        if args.universe_kind:
            manifest["universe_kind"] = args.universe_kind
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
    for item in excluded:
        print(f"  universe-excluded {item['symbol']}: {item['reason']}")
    for event in result.converted:
        print(f"  {event['id']}: per share {event['per_share']} ({event['label']})")
    print(f"excluded {len(result.excluded)}")
    for event in result.excluded:
        print(f"  {event['id']}: {event['reason']}")
    print(f"manifest {path}")
    return 0


def _load_yahoo(root: Path, snapshot_id: str) -> dict:
    manifest = read_manifest(root, snapshot_id)
    frames, splits = {}, {}
    for entry in manifest["files"]:
        name = Path(entry["path"]).name
        if name.startswith("response-") and name.endswith(".json"):
            symbol = name[len("response-"):-len(".json")]
            frame, _dividends, yahoo_splits = parse_chart((root / entry["path"]).read_bytes(),
                                                          yahoo_symbol(symbol))
            frames[symbol] = frame
            splits[symbol] = yahoo_splits
    if not frames:
        raise ManifestError(f"{snapshot_id}: no response files")
    return frames, splits


def cmd_quality(args):
    root = Path(args.root) if args.root else data_root()
    require(root / "manifests" / (args.dataset_id + ".json"))
    if args.yahoo:
        require(root / "manifests" / (args.yahoo + ".json"))
    try:
        manifest = read_manifest(root, args.dataset_id)
        rows, actions = read_inputs(root, manifest)
        instruments = tuple(sorted({row["symbol"] for row in rows}))
        created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        inputs = {"manifest_sha256": sha256_file(root / "manifests" / (args.dataset_id + ".json")),
                  "yahoo_snapshot_id": args.yahoo,
                  "yahoo_manifest_sha256": (sha256_file(root / "manifests" / (args.yahoo + ".json"))
                                            if args.yahoo else None)}
        try:
            result = normalise(rows, actions, instruments)
        except MarketDataError as error:
            report = build_failure_report(args.dataset_id, manifest["recipe"], str(error),
                                          created_utc=created, inputs=inputs)
            folder = write_report(root, report)
            print(f"Quality {args.dataset_id}: fail (normalise: {error})")
            print(f"report {folder / 'report.json'}")
            return 1
        yahoo, yahoo_splits = _load_yahoo(root, args.yahoo) if args.yahoo else (None, None)
        extra = {}
        if manifest.get("universe_kind"):
            extra = {"excluded_symbols": actions.get("excluded_symbols", []), "actions": actions}
        report = build_report(args.dataset_id, rows, result, yahoo, result.data.splits, created_utc=created,
                              yahoo_splits=yahoo_splits, inputs=inputs, **extra)
        folder = write_report(root, report)
    except FileExistsError as error:
        print(f"error: report already exists: {error.filename}", file=sys.stderr)
        return 1
    except (ValueError, ManifestError, MarketDataError, KeyError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Quality {args.dataset_id}: {report['status']}")
    for check in report["checks"]:
        print(f"  {check['name']}: {check['status']} ({check['count']})")
        if check["name"] == "cross_source" and "stats" in check:
            print(f"    {check['detail']}")
    print(f"report {folder / 'report.json'}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    fy = sub.add_parser("fetch-yahoo", help="fetch a receipted raw Yahoo snapshot")
    fy.add_argument("--symbols", help="comma-separated, e.g. SPY,XLB")
    fy.add_argument("--symbols-file", help="CSV with a `symbol` column (stock set: dots mapped to dashes, "
                    "stock rights block, 5-failure stop)")
    fy.add_argument("--pause", type=float, default=0.3, help="seconds between requests with --symbols-file")
    fy.add_argument("--start", required=True, help="YYYY-MM-DD")
    fy.add_argument("--end", required=True, help="YYYY-MM-DD, inclusive")
    fy.add_argument("--snapshot-id", required=True)
    fy.add_argument("--root", help="data root (default: shared data root)")
    fy.set_defaults(func=cmd_fetch_yahoo)
    fg = sub.add_parser("fetch-github", help="fetch the S&P 500 membership sources (GitHub hosts only), receipted")
    fg.add_argument("--snapshot-id", required=True)
    fg.add_argument("--url", action="append", metavar="NAME=URL",
                    help="fetch only these named URLs (GitHub hosts only; repeatable) instead of discovering")
    fg.add_argument("--root", help="data root (default: shared data root)")
    fg.set_defaults(func=cmd_fetch_github)
    mb = sub.add_parser("membership", help="build membership/v1 from a GitHub snapshot (no network)")
    mb.add_argument("--snapshot", required=True, action="append",
                    help="GitHub snapshot id; repeat to combine (a later snapshot overrides an earlier "
                         "one by file name)")
    mb.add_argument("--membership-id", required=True)
    mb.add_argument("--root", help="data root (default: shared data root)")
    mb.set_defaults(func=cmd_membership)
    sa = sub.add_parser("stock-actions", help="write etf-normalise-format actions from a stock Yahoo snapshot")
    sa.add_argument("--snapshot", required=True, help="Yahoo snapshot id")
    sa.add_argument("--out", required=True, help="output path relative to the data root (never overwritten)")
    sa.add_argument("--root", help="data root (default: shared data root)")
    sa.set_defaults(func=cmd_stock_actions)
    idn = sub.add_parser("identity", help="write instrument-identity/v1 and the resolved cross-checks")
    idn.add_argument("--archive", default="spy-equities-2016-2025-v1", help="archive manifest id (universe.equities)")
    idn.add_argument("--membership-id", required=True)
    idn.add_argument("--identity-id", required=True)
    idn.add_argument("--ticker-changes", type=Path, default=TICKER_CHANGES)
    idn.add_argument("--root", help="data root (default: shared data root)")
    idn.set_defaults(func=cmd_identity)
    cv = sub.add_parser("coverage", help="write membership-coverage/v1 for a stock dataset")
    cv.add_argument("--membership-id", required=True)
    cv.add_argument("--identity-id", required=True)
    cv.add_argument("--dataset-id", required=True, help="normalised stock dataset manifest id")
    cv.add_argument("--coverage-id", required=True)
    cv.add_argument("--root", help="data root (default: shared data root)")
    cv.set_defaults(func=cmd_coverage)
    nm = sub.add_parser("normalise", help="apply etf-normalise/v1 and write a normalised manifest")
    nm.add_argument("--bars", help="source bars JSON inside the data root")
    nm.add_argument("--bars-dir", help="stock set: directory (relative to the data root) of <SYMBOL>.json bar files")
    nm.add_argument("--symbols-from", help="with --bars-dir: coverage CSV (relative to the data root)")
    nm.add_argument("--status", help="with --bars-dir: coverage status to include, e.g. structural_full_window")
    nm.add_argument("--exclude-from-actions", action="store_true",
                    help="drop the symbols the actions file lists under excluded_symbols")
    nm.add_argument("--universe-kind", help="e.g. current-holdings-proxy; recorded in the manifest")
    nm.add_argument("--actions", required=True,
                    help="issuer-actions JSON (with --bars-dir: relative to the data root)")
    nm.add_argument("--dataset-id", required=True)
    nm.add_argument("--root", help="data root (default: shared data root)")
    nm.set_defaults(func=cmd_normalise)
    ql = sub.add_parser("quality", help="write a quality-report/v1 for a normalised dataset")
    ql.add_argument("--dataset-id", required=True, help="normalised dataset manifest id")
    ql.add_argument("--yahoo", help="Yahoo snapshot id for the cross-source check (default: blocked)")
    ql.add_argument("--root", help="data root (default: shared data root)")
    ql.set_defaults(func=cmd_quality)
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
