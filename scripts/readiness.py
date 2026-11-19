#!/usr/bin/env python3
"""Render or check the generated readiness checklist from the readiness registry.

  render     rewrite docs/readiness-checklist.md from research/registry/readiness.json
  check      validate the registry (gate ids, evidence files) and that the document is current
  build      write .local/progress/readiness.html (the Readiness tab; not tracked, it carries a build time)

The registry and gates are only read. Offline only: no network, broker or order.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.control.readiness import ReadinessError, load_readiness, render_markdown, render_page

REGISTRY = ROOT / "research/registry/readiness.json"
GATES = ROOT / "research/registry/gates.json"
DOC = ROOT / "docs/readiness-checklist.md"


def gate_ids(path):
    """Every gate id and gate item id declared in the gates registry."""
    try:
        gates = json.loads(Path(path).read_text(encoding="utf-8"))
        ids = set()
        for gate in gates["gates"]:
            ids.add(gate["id"])
            ids.update(item["id"] for item in gate["items"])
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ReadinessError(f"gates unreadable: {error}") from None
    return ids


def load(args):
    return load_readiness(args.registry, gate_ids(args.gates), ROOT)


def cmd_render(args):
    doc = load(args)
    Path(args.doc).write_text(render_markdown(doc), encoding="utf-8")
    print(f"Rendered {args.doc} from {len(doc['aspects'])} aspects.")
    return 0


def cmd_check(args):
    doc = load(args)
    path = Path(args.doc)
    if not path.is_file() or path.read_text(encoding="utf-8") != render_markdown(doc):
        print(f"error: {path} is stale; run scripts/readiness.py render", file=sys.stderr)
        return 1
    print(f"Readiness passed: {len(doc['aspects'])} aspects; evidence present; document current.")
    return 0


def cmd_build(args):
    doc = load(args)
    Path(args.dir).mkdir(parents=True, exist_ok=True)
    target = Path(args.dir) / "readiness.html"
    target.write_text(render_page(doc, datetime.now().strftime("%Y-%m-%d %H:%M")), encoding="utf-8")
    print(f"Wrote {target} from {len(doc['aspects'])} aspects.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--gates", type=Path, default=GATES)
    parser.add_argument("--doc", type=Path, default=DOC)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("render").set_defaults(fn=cmd_render)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    build = sub.add_parser("build")
    build.add_argument("--dir", type=Path, default=ROOT / ".local/progress", help="folder for readiness.html")
    build.set_defaults(fn=cmd_build)
    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except (ReadinessError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
