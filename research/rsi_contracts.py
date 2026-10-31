"""Versioned, offline research contracts; no execution or adoption authority.

``validate_cycle`` accepts exactly the RSI-CYCLE-1 object documented below.
All identifiers/text are nonempty strings, all hashes are lowercase SHA-256,
all UTC times are ISO-8601 with an explicit zero offset, and unknown fields fail.

    contract_version: "RSI-CYCLE-1"
    program_id, cycle_id, created_utc
    parent: {cycle_id, receipt_sha256}
    incumbent: {version, sha256}
    change: {kind, stage, description, changed_stages: [stage]}
    proposal: {hypothesis, mechanism, falsifier, prior_lessons: [text],
               simpler_control_ids: [control_id]}
    interface: {input_fields: [{name, meaning, unit}], output_fields: [...]}
    timing: {as_of_utc, data_available_utc, decision_utc, execution_utc,
             target, horizon}
    evaluation: {start_utc, end_utc, exposure, prior_access_count,
                 prior_access_note}
    criteria: {objective, meaningful_effect, guardrails: [text], tolerance}
    controls: [{id, description, sha256}]
    budget: {max_attempts, wall_seconds, workers: 1, automatic_retries: 0}
    artifacts: [{path, sha256}]

``kind`` is improve_existing_stage or add_optional_stage. ``exposure`` is
development, previously_viewed, or protected_forward. Times obey availability
<= as-of <= decision < execution; creation <= decision. Protected forward
evaluation starts after creation/as-of and declares zero accesses; previously viewed
evaluation declares at least one access. The schema records declarations, not
proof of causality, unseen data, successful controls, or permission to launch.
The caller freezes canonical_hash(plan) and checks it again before using a plan.

Hashing uses Python's sorted compact UTF-8 JSON (not RFC 8785): JSON primitives
only, finite floats, string keys, no implicit conversions. Integer and float
spellings remain distinct. Artifact reads use directory-relative no-follow file
descriptors and reject symlinks, special files and lexical path traversal.

``preflight_known_c001`` is a read-only saved-output lesson regression. Its pinned
historical receipt is the trust anchor; a changed receipt needs a new reviewed
contract version. Only this function lazily imports existing pandas/helper code.
It preserves the failed closed C001 gate and never changes its consumed attempt.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
import stat


CYCLE_CONTRACT_VERSION = "RSI-CYCLE-1"
C001_PREFLIGHT_VERSION = "RSI-C001-PREFLIGHT-1"
_C001_RECEIPT = {
    "path": "docs/tasks/evidence/2026-10-27-grs-c001.json",
    "sha256": "dea21e854ebf01cc80901e0d404562f3d8b34a5d7ff75e9328d345d0ccdebc4f",
}
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]*\Z")


class ContractError(ValueError):
    """A declared contract or its saved evidence is invalid."""


def _json_value(value):
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            _json_value(item)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _json_value(item)
        return
    raise ContractError("Canonical values must contain only finite JSON primitives")


def canonical_hash(value):
    """Return deterministic SHA-256 for strict JSON values without mutating them."""
    _json_value(value)
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _object(value, keys, label):
    if type(value) is not dict or set(value) != set(keys.split()):
        raise ContractError(f"{label} requires exactly: {keys}")
    return value


def _text(value, label):
    if type(value) is not str or not value.strip():
        raise ContractError(f"{label} must be nonempty text")
    return value


def _identifier(value, label):
    if not _IDENTIFIER.fullmatch(_text(value, label)):
        raise ContractError(f"Invalid {label}")
    return value


def _sha(value):
    if type(value) is not str or not _HASH.fullmatch(value):
        raise ContractError("Expected lowercase SHA-256")
    return value


def _relative(value):
    if (type(value) is not str or not value or "\\" in value or "\0" in value
            or any(part in ("", ".", "..") for part in value.split("/"))):
        raise ContractError("Artifact path must be a contained relative POSIX path")
    return value


def _entries(entries):
    if type(entries) is not list:
        raise ContractError("Artifact entries must be a list")
    result, seen = [], set()
    for entry in entries:
        _object(entry, "path sha256", "artifact")
        path, digest = _relative(entry["path"]), _sha(entry["sha256"])
        if path in seen:
            raise ContractError(f"Duplicate artifact: {path}")
        seen.add(path)
        result.append({"path": path, "sha256": digest})
    return result


def _read_relative(path, root):
    """Read regular bytes without following any artifact-path symlink."""
    parts = _relative(path).split("/")
    descriptors = []
    try:
        directory = os.open(Path(root).resolve(strict=True), os.O_RDONLY | os.O_DIRECTORY)
        descriptors.append(directory)
        for part in parts[:-1]:
            directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=directory)
            descriptors.append(directory)
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                     dir_fd=directory)
        descriptors.append(fd)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ContractError(f"Artifact is not a regular file: {path}")
        with os.fdopen(os.dup(fd), "rb") as stream:
            return stream.read()
    except OSError as error:
        raise ContractError(f"Artifact missing, unsafe or unreadable: {path}") from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _verified_bytes(entry, root):
    entry = _entries([entry])[0]
    data = _read_relative(entry["path"], root)
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise ContractError(f"Artifact hash mismatch: {entry['path']}")
    return data


def verify_artifacts(entries, root):
    """Verify contained regular files and return detached entries in input order.

    Empty lists are allowed here; cycle contracts require at least one artifact.
    All relative path symlinks fail, including symlinks remaining inside root.
    The explicit root itself resolves once as the caller's trusted directory.
    """
    result = _entries(entries)
    for entry in result:
        _verified_bytes(entry, root)
    return tuple(result)


def _number(value, label, *, minimum=0, strict=False, integer=False):
    allowed = (int,) if integer else (int, float)
    if (type(value) not in allowed or (type(value) is float and not math.isfinite(value))
            or value < minimum or (strict and value == minimum)):
        raise ContractError(f"Invalid finite {'integer' if integer else 'number'}: {label}")
    return value


def _utc(value, label):
    _text(value, label)
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ContractError(f"Invalid UTC timestamp: {label}") from error
    if "T" not in value or result.tzinfo is None or result.utcoffset() != timezone.utc.utcoffset(result):
        raise ContractError(f"Explicit UTC timestamp required: {label}")
    return result


def validate_cycle(plan):
    """Validate RSI-CYCLE-1 declarations; return a deep copy, perform no I/O."""
    _object(plan, "contract_version program_id cycle_id created_utc parent incumbent "
            "change proposal interface timing evaluation criteria controls budget artifacts", "cycle")
    _json_value(plan)
    if plan["contract_version"] != CYCLE_CONTRACT_VERSION:
        raise ContractError("Unsupported cycle contract version")
    _identifier(plan["program_id"], "program_id")
    _identifier(plan["cycle_id"], "cycle_id")
    created = _utc(plan["created_utc"], "created_utc")
    parent = _object(plan["parent"], "cycle_id receipt_sha256", "parent")
    _identifier(parent["cycle_id"], "parent cycle_id")
    _sha(parent["receipt_sha256"])
    if parent["cycle_id"] == plan["cycle_id"]:
        raise ContractError("A cycle cannot be its own parent")
    incumbent = _object(plan["incumbent"], "version sha256", "incumbent")
    _identifier(incumbent["version"], "incumbent version")
    _sha(incumbent["sha256"])
    change = _object(plan["change"], "kind stage description changed_stages", "change")
    if change["kind"] not in ("improve_existing_stage", "add_optional_stage"):
        raise ContractError("Unsupported stage change")
    _text(change["stage"], "stage")
    _text(change["description"], "change description")
    if type(change["changed_stages"]) is not list or change["changed_stages"] != [change["stage"]]:
        raise ContractError("Exactly one declared stage must change")
    proposal = _object(plan["proposal"], "hypothesis mechanism falsifier prior_lessons simpler_control_ids", "proposal")
    for key in ("hypothesis", "mechanism", "falsifier"):
        _text(proposal[key], key)
    if type(proposal["prior_lessons"]) is not list or not proposal["prior_lessons"]:
        raise ContractError("At least one concrete prior lesson is required")
    for lesson in proposal["prior_lessons"]:
        _text(lesson, "prior lesson")
    interface = _object(plan["interface"], "input_fields output_fields", "interface")
    for direction in ("input_fields", "output_fields"):
        fields = interface[direction]
        if type(fields) is not list or not fields:
            raise ContractError(f"Nonempty {direction} required")
        names = set()
        for field in fields:
            _object(field, "name meaning unit", "interface field")
            _identifier(field["name"], "interface field name")
            _text(field["meaning"], "field meaning")
            _text(field["unit"], "field unit")
            if field["name"] in names:
                raise ContractError("Duplicate interface field name")
            names.add(field["name"])
    timing = _object(plan["timing"], "as_of_utc data_available_utc decision_utc execution_utc target horizon", "timing")
    as_of, available, decision, execution = (
        _utc(timing[key], key) for key in
        ("as_of_utc", "data_available_utc", "decision_utc", "execution_utc"))
    if not available <= as_of <= decision < execution or created > decision:
        raise ContractError("Availability/as-of/decision/execution chronology violated")
    for key in ("target", "horizon"):
        _text(timing[key], key)
    evaluation = _object(plan["evaluation"], "start_utc end_utc exposure prior_access_count prior_access_note", "evaluation")
    start, end = (_utc(evaluation[key], key) for key in ("start_utc", "end_utc"))
    if start > end:
        raise ContractError("Evaluation end precedes start")
    exposure = evaluation["exposure"]
    if exposure not in ("development", "previously_viewed", "protected_forward"):
        raise ContractError("Unknown evaluation exposure")
    accesses = _number(evaluation["prior_access_count"], "prior_access_count", integer=True)
    _text(evaluation["prior_access_note"], "prior_access_note")
    if exposure == "previously_viewed" and accesses == 0:
        raise ContractError("Previously viewed evaluation must declare prior accesses")
    if exposure == "protected_forward" and (accesses != 0 or start <= max(created, as_of)):
        raise ContractError("Protected forward evidence must be unaccessed and begin after freeze")
    criteria = _object(plan["criteria"], "objective meaningful_effect guardrails tolerance", "criteria")
    _text(criteria["objective"], "objective")
    _number(criteria["meaningful_effect"], "meaningful_effect", strict=True)
    _number(criteria["tolerance"], "tolerance")
    if type(criteria["guardrails"]) is not list or not criteria["guardrails"]:
        raise ContractError("At least one guardrail is required")
    for guardrail in criteria["guardrails"]:
        _text(guardrail, "guardrail")
    if type(plan["controls"]) is not list or not plan["controls"]:
        raise ContractError("At least one frozen control is required")
    controls = set()
    for control in plan["controls"]:
        _object(control, "id description sha256", "control")
        _identifier(control["id"], "control id")
        _text(control["description"], "control description")
        _sha(control["sha256"])
        if control["id"] in controls:
            raise ContractError("Duplicate control id")
        controls.add(control["id"])
    simpler = proposal["simpler_control_ids"]
    if (type(simpler) is not list or not simpler
            or any(type(control) is not str for control in simpler)
            or len(set(simpler)) != len(simpler) or not set(simpler).issubset(controls)):
        raise ContractError("Simpler controls must reference unique declared control ids")
    budget = _object(plan["budget"], "max_attempts wall_seconds workers automatic_retries", "budget")
    _number(budget["max_attempts"], "max_attempts", strict=True, integer=True)
    _number(budget["wall_seconds"], "wall_seconds", strict=True)
    _number(budget["workers"], "workers", integer=True)
    _number(budget["automatic_retries"], "automatic_retries", integer=True)
    if budget["workers"] != 1 or budget["automatic_retries"] != 0:
        raise ContractError("This contract requires one writer and zero automatic retries")
    if not _entries(plan["artifacts"]):
        raise ContractError("At least one immutable artifact is required")
    return deepcopy(plan)


def _load_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ContractError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    try:
        value = json.loads(data, object_pairs_hook=pairs)
    except (ValueError, UnicodeDecodeError) as error:
        raise ContractError("Invalid saved JSON") from error
    _json_value(value)
    return value


def _hash_map(value, prefix=""):
    if type(value) is not dict or not value:
        raise ContractError("Nonempty recorded artifact hashes required")
    return _entries([{"path": f"{prefix}/{path}" if prefix else path, "sha256": digest}
                     for path, digest in value.items()])


def _manifest(entry, root):
    manifest = _load_json(_verified_bytes(entry, root))
    prefix = entry["path"].rsplit("/", 1)[0]
    artifacts = _hash_map(manifest["artifact_hashes"], prefix)
    verify_artifacts(artifacts, root)
    return manifest, {item["path"]: item for item in artifacts}


def _preflight_known_c001(root):
    """Recognize the recorded C001 lesson from verified bytes; launch nothing.

    Missing historical/local files, changed source, unrelated schema/monetary
    drift, and changed trades fail closed. This verifies recorded artifact
    integrity and the narrow diagnostic semantics, not financial performance.
    All parent files are checked without importing or executing their runners.
    """
    receipt = _load_json(_verified_bytes(_C001_RECEIPT, root))
    if (receipt["cycle"] != "GRS-C001"
            or receipt["status"] != "closed-inconclusive-control-schema-mismatch"
            or type(receipt["actual_financial_attempts"]) is not int
            or receipt["actual_financial_attempts"] != 1
            or receipt["incumbent_changed"] is not False
            or receipt["completed_comparisons"] != 0):
        raise ContractError("C001 must remain closed with one consumed attempt")
    plan_entry = {"path": receipt["plan"], "sha256": receipt["plan_sha256"]}
    plan = _load_json(_verified_bytes(plan_entry, root))
    if plan["cycle"] != "GRS-C001":
        raise ContractError("C001 plan identity changed")
    source_entries = _hash_map(plan["code_hashes"])
    source_entries += [{key: plan["source"][key] for key in ("path", "sha256")}]
    helper_entry = {"path": receipt["engineering_followup"]["source"],
                    "sha256": receipt["engineering_followup"]["sha256"]}
    source_entries += [helper_entry,
                       {"path": plan["design_path"], "sha256": plan["design_sha256"]},
                       {"path": "docs/research-standard.md", "sha256": plan["golden_standard_sha256"]}]
    verify_artifacts(source_entries, root)
    current_prefix = _relative(receipt["artifacts"])
    current_entry = {"path": f"{current_prefix}/manifest.json", "sha256": receipt["manifest_sha256"]}
    current_manifest, current = _manifest(current_entry, root)
    if current_manifest["cycle"] != "GRS-C001" or current_manifest["status"] != "closed-inconclusive-no-retry":
        raise ContractError("C001 current manifest is not closed")
    state = _load_json(_verified_bytes(current[f"{current_prefix}/state.json"], root))
    if (state["cycle"] != "GRS-C001" or state["status"] != "closed-inconclusive-no-retry"
            or type(state["actual_attempts"]) is not int or state["actual_attempts"] != 1
            or state["plan_sha256"] != plan_entry["sha256"]
            or state["attempts"][0]["status"] != "failed"):
        raise ContractError("C001 failed attempt state changed")
    if current[f"{current_prefix}/plan.json"]["sha256"] != plan_entry["sha256"]:
        raise ContractError("Current output plan differs from the frozen plan")
    parents = {}
    for prefix, digest in plan["parent_manifests"].items():
        _relative(prefix)
        _, parents[prefix] = _manifest({"path": f"{prefix}/manifest.json", "sha256": digest}, root)
    control = _relative(plan["control_paths"]["5bp_ema"])
    parent_prefix = control.rsplit("/", 1)[0]
    if parent_prefix not in parents:
        raise ContractError("EMA control is not in the recorded parent manifests")
    old_files = parents[parent_prefix]
    current_case = f"{current_prefix}/5bp_ema"
    required_old = [f"{control}/{name}.csv" for name in ("ledger", "trades", "signal")]
    required_new = [f"{current_case}/{name}.csv" for name in ("ledger", "trades", "signal")]
    if any(path not in old_files for path in required_old) or any(path not in current for path in required_new):
        raise ContractError("Recorded EMA ledger/trade/signal artifacts required")

    # Use the verified source only from this installed checkout, never execute
    # Python supplied by the artifact root. No financial runner is imported.
    installed_helper = Path(__file__).with_name("legacy_control_contract.py")
    if hashlib.sha256(installed_helper.read_bytes()).hexdigest() != helper_entry["sha256"]:
        raise ContractError("Installed diagnostic helper differs from the recorded helper")
    import pandas as pd
    from research.legacy_control_contract import compare_ema_diagnostic

    def frame(entry, indexed=True):
        return pd.read_csv(BytesIO(_verified_bytes(entry, root)), index_col="date" if indexed else None)

    oldcurve, newcurve = frame(old_files[required_old[0]]), frame(current[required_new[0]])
    oldtrades, newtrades = frame(old_files[required_old[1]], False), frame(current[required_new[1]], False)
    signal, oldsignal = frame(current[required_new[2]]), frame(old_files[required_old[2]])
    if signal.index.has_duplicates or not signal.index.is_monotonic_increasing:
        raise ContractError("EMA dates must be unique and increasing")
    if (not signal.index.equals(oldsignal.index)
            or not {"want_long", "intended_target"}.issubset(signal.columns)
            or signal["want_long"].dtype != bool
            or oldsignal["want_long"].dtype != bool
            or not signal["want_long"].equals(oldsignal["want_long"])):
        raise ContractError("Recorded EMA eligibility semantics differ")
    try:
        # The same known nominal/effective diagnostic transition appears in
        # allocation_factor. Eligibility, prices and intended targets stay exact.
        diagnostic = "allocation_factor"
        if (diagnostic not in oldsignal or diagnostic not in signal
                or not oldsignal[diagnostic].equals(oldsignal["intended_target"])
                or not signal[diagnostic].eq(1).all()):
            raise ContractError("Unrecognized signal diagnostic semantics")
        columns = [column for column in oldsignal if column != diagnostic]
        if list(oldsignal.columns) != list(signal.columns):
            raise ContractError("Unexpected signal schema change")
        pd.testing.assert_frame_equal(oldsignal[columns], signal[columns], check_exact=True)
        result = compare_ema_diagnostic(oldcurve, newcurve, oldtrades, newtrades, signal)
    except (AssertionError, ValueError) as error:
        raise ContractError("Known C001 diagnostic check failed") from error
    identity = {"version": C001_PREFLIGHT_VERSION, "receipt": _C001_RECEIPT,
                "plan": plan_entry, "current_manifest": current_entry,
                "parent_manifests": plan["parent_manifests"], "helper": helper_entry}
    return {"contract_version": C001_PREFLIGHT_VERSION,
            "check_id": "c001-ema-diagnostic-" + canonical_hash(identity),
            "passed": True, "identity": deepcopy(identity), "check": result,
            "signal_diagnostic_verified": "effective0or1-to-nominal1-allocation_factor",
            "financial_launches": 0, "original_financial_attempts": 1,
            "original_cycle_status": receipt["status"], "frozen_gate_overridden": False,
            "incumbent_changed": False}


def preflight_known_c001(root):
    """Read-only C001 saved-evidence check; see the module contract for scope."""
    try:
        return _preflight_known_c001(root)
    except (KeyError, IndexError, TypeError) as error:
        raise ContractError("Malformed recorded C001 evidence") from error
