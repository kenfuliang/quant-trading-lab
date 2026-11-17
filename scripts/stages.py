#!/usr/bin/env python3
"""Draft the stage map and render or check the generated pipeline status document.

  draft-map  write an unreviewed stage-map.json from the registry (refuses to overwrite)
  render     rewrite docs/pipeline-status.md from the registry, stage map and incumbents
  check      validate both declarations against the registry and that the status document is current

The registry, receipts and gates are only read. Offline only: no network, broker or order.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.control import experiment_registry as registry
from research.control.experiment_registry import RegistryError
from research.control.incumbents import IncumbentsError, load_incumbents, render_status
from research.control.stage_map import StageMapError, draft_stage_map, load_stage_map
from research.control.stage_view import build_model

REGISTRY = ROOT / "research/registry/experiments.jsonl"
STAGE_MAP = ROOT / "research/registry/stage-map.json"
INCUMBENTS = ROOT / "research/registry/incumbents.json"
STATUS_DOC = ROOT / "docs/pipeline-status.md"


def load_inputs(args):
    """(records, stage_map, incumbents, errors). Every missing or invalid input adds an error."""
    errors = []
    try:
        records = registry.load(args.registry)
    except RegistryError as error:
        return [], {}, {}, [f"registry: {error}"]
    ids = {r["record_id"] for r in records}
    loaded = {}
    for label, path, loader in (("stage map", args.stage_map, load_stage_map),
                                ("incumbents", args.incumbents, load_incumbents)):
        if not Path(path).is_file():
            errors.append(f"{label} is missing: {path}")
            loaded[label] = {}
            continue
        try:
            loaded[label] = loader(path, ids)
        except (StageMapError, IncumbentsError) as error:
            errors.append(f"{label}: {error}")
            loaded[label] = {}
    return records, loaded["stage map"], loaded["incumbents"], errors


def render_text(records, stage_map, incumbents):
    return render_status(records, incumbents, build_model(records, stage_map))


def cmd_draft(args):
    target = Path(args.out or args.stage_map)
    if target.exists():
        print(f"error: {target} exists; the stage map is hand-reviewed and is not overwritten", file=sys.stderr)
        return 1
    document = draft_stage_map(registry.load(args.registry))
    target.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Drafted {len(document['entries'])} unreviewed entries in {target}.")
    return 0


def cmd_render(args):
    records, stage_map, incumbents, errors = load_inputs(args)
    if errors:
        print("\n".join(f"error: {e}" for e in errors), file=sys.stderr)
        return 1
    Path(args.status_doc).write_text(render_text(records, stage_map, incumbents), encoding="utf-8")
    print(f"Rendered {args.status_doc} from {len(records)} records.")
    return 0


def cmd_check(args):
    records, stage_map, incumbents, errors = load_inputs(args)
    if not errors:
        status = Path(args.status_doc)
        if not status.is_file() or status.read_text(encoding="utf-8") != render_text(records, stage_map, incumbents):
            errors.append(f"{status.name} is stale or missing; run scripts/stages.py render")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Pipeline status passed: {len(records)} records; stage map and incumbents valid; status document current.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--stage-map", type=Path, default=STAGE_MAP)
    parser.add_argument("--incumbents", type=Path, default=INCUMBENTS)
    parser.add_argument("--status-doc", type=Path, default=STATUS_DOC)
    sub = parser.add_subparsers(dest="command", required=True)
    draft = sub.add_parser("draft-map")
    draft.add_argument("--out", type=Path, help="default: the --stage-map path")
    draft.set_defaults(fn=cmd_draft)
    sub.add_parser("render").set_defaults(fn=cmd_render)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except (RegistryError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
