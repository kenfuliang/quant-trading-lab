#!/usr/bin/env python3
"""Render or check the generated artifact catalog from the artifact registry.

  render     rewrite docs/artifacts.md from research/registry/artifacts.json
  check      validate the registry, that every schema id declared in code is catalogued,
             and that the document is current

The registry and source are only read. Offline only: no network, broker or order.
"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.control.artifacts import ArtifactsError, load_artifacts, load_updated, render_markdown, scan_schema_ids

REGISTRY = ROOT / "research/registry/artifacts.json"
DOC = ROOT / "docs/artifacts.md"
SCAN_ROOTS = [ROOT / name for name in ("research", "scripts", "paper_trading", "reporting")]


def load(args):
    return load_artifacts(args.registry), load_updated(args.registry)


def cmd_render(args):
    entries, updated = load(args)
    Path(args.doc).write_text(render_markdown(entries, updated), encoding="utf-8")
    print(f"Rendered {args.doc} from {len(entries)} artifacts.")
    return 0


def cmd_check(args):
    entries, updated = load(args)
    known = {e["schema_id"] for e in entries}
    roots = args.scan or [r for r in SCAN_ROOTS if r.exists()]
    found = scan_schema_ids(roots)
    missing = {ident: files for ident, files in found.items() if ident not in known}
    for ident, files in missing.items():
        print(f"error: schema id {ident} is declared in {', '.join(files)} but not in {args.registry}",
              file=sys.stderr)
    if missing:
        return 1
    path = Path(args.doc)
    if not path.is_file() or path.read_text(encoding="utf-8") != render_markdown(entries, updated):
        print(f"error: {path} is stale; run scripts/artifacts.py render", file=sys.stderr)
        return 1
    print(f"Artifacts passed: {len(entries)} artifacts; {len(found)} scanned schema ids catalogued; "
          "document current.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--doc", type=Path, default=DOC)
    parser.add_argument("--scan", type=Path, action="append", help="folder to scan (repeatable); default: the code roots")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("render").set_defaults(fn=cmd_render)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except (ArtifactsError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
