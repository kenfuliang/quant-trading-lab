"""Pipeline stage taxonomy and the reviewed stage-map sidecar.

Registry tags describe a record's configuration, not the stage it tests, and the registry
is hash-chained and never edited. This sidecar holds, per record, the single stage under
test and (for a challenger) the control it is matched to. Only entries with `reviewed: true`
place a record in a stage cell; a draft never does. Pure functions; no file writes here.
"""
import json
from pathlib import Path

SCHEMA = "stage-map/v1"
STAGES = ("features", "market conditions", "position proposal", "target selection",
          "risk gate", "sizing", "execution")
MULTIPLE = "multiple"
_TAG_TO_STAGE = {"feature representation": "features", "selection": "target selection",
                 "traffic gate": "risk gate"}
_TAG_TO_STAGE.update({stage: stage for stage in STAGES if stage != "features"})


class StageMapError(ValueError):
    pass


def tag_stages(tags):
    """Normalised stages named by a record's tags; non-stage tags are ignored."""
    return frozenset(_TAG_TO_STAGE[t] for t in tags if t in _TAG_TO_STAGE)


def _context(record):
    return record["context"]["code"], record["context"]["period"]


def draft_stage_map(records):
    """A stage-map document with one unreviewed entry per record, derived from tags only."""
    controls = {}
    for record in records:
        if record["disposition"] == "control":
            controls.setdefault(_context(record), []).append(record["record_id"])
    entries = []
    for record in records:
        stages = tag_stages(record.get("tags") or [])
        stage = next(iter(stages)) if len(stages) == 1 else MULTIPLE if stages else None
        siblings = controls.get(_context(record), [])
        control = siblings[0] if "challenger" in (record.get("tags") or []) and len(siblings) == 1 else None
        entries.append({"record_id": record["record_id"], "stage_under_test": stage,
                        "control": control, "reviewed": False})
    return {"schema": SCHEMA, "entries": entries}


def load_stage_map(path, record_ids):
    """Entries keyed by record_id. Raises StageMapError on any shape or reference problem."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise StageMapError(f"stage map unreadable: {error}") from None
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA or not isinstance(doc.get("entries"), list):
        raise StageMapError(f"stage map must have schema {SCHEMA} and an entries list")
    loaded = {}
    for item in doc["entries"]:
        if not isinstance(item, dict) or set(item) != {"record_id", "stage_under_test", "control", "reviewed"}:
            raise StageMapError(f"bad stage map entry: {item!r}")
        rid = item["record_id"]
        if rid not in record_ids:
            raise StageMapError(f"stage map names unknown record {rid}")
        if rid in loaded:
            raise StageMapError(f"stage map repeats record {rid}")
        if item["stage_under_test"] not in (*STAGES, MULTIPLE, None):
            raise StageMapError(f"{rid}: unknown stage_under_test {item['stage_under_test']!r}")
        if item["control"] == rid:
            raise StageMapError(f"{rid}: a record cannot be its own control")
        if item["control"] is not None and item["control"] not in record_ids:
            raise StageMapError(f"{rid}: stage map names unknown control {item['control']}")
        if not isinstance(item["reviewed"], bool):
            raise StageMapError(f"{rid}: reviewed must be true or false")
        loaded[rid] = item
    return loaded
