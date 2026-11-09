"""Append-only experiment registry: one validated record per experiment case.

The registry is the single source for the leaderboard, the dead-ends list and the
learning curve (`registry_views`). Each stored line chains to the previous one with
`canonical_hash`, so edits or deletions are detected; the chain is local tamper
evidence, not a signature. Failed, blocked and inconclusive runs are first-class.
Metrics use actual units as fractions (0.12 = 12%); drawdown is a positive loss depth.
No scalar score exists: ranking is a CAGR-versus-drawdown frontier per context.
"""
import fcntl
from datetime import datetime
import json
import math
import os
from pathlib import Path
import re

from research.control.rsi_contracts import canonical_hash

SCHEMA = "experiment-record/v1"
CLASSES = ("live", "paper", "shadow", "sealed_forward", "development")  # strongest first
DISPOSITIONS = ("keep", "retire", "inconclusive", "control", "blocked")
METRICS = ("net_cagr", "max_drawdown", "longest_underwater_sessions",
           "longest_underwater_days", "calmar", "sharpe", "turnover")
DRAWDOWN_TOLERANCE = 0.30  # mandate reassessment reference, a flag and not a gate
GENESIS = "genesis"
_ID = re.compile(r"^[A-Za-z0-9._:/+-]{3,120}$")
_REQUIRED = ("schema", "record_id", "logged_at", "name", "context", "evidence_class",
             "disposition", "lesson", "metrics")


class RegistryError(ValueError):
    pass


def _finite(value, label, low=None, high=None, integer=False):
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise RegistryError(f"{label} must be a finite number or null")
    if integer and (not isinstance(value, int) or value < 0):
        raise RegistryError(f"{label} must be a non-negative integer or null")
    if low is not None and value < low or high is not None and value > high:
        raise RegistryError(f"{label} is out of range")


def validate(record):
    if not isinstance(record, dict):
        raise RegistryError("record must be an object")
    missing = [key for key in _REQUIRED if key not in record]
    if missing:
        raise RegistryError("record is missing " + ", ".join(missing))
    if record["schema"] != SCHEMA:
        raise RegistryError("unknown record schema")
    if not isinstance(record["record_id"], str) or not _ID.match(record["record_id"]):
        raise RegistryError("record_id must be 3-120 characters of letters, digits and ._:/+-")
    stamp = record["logged_at"]
    try:
        parsed = datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        raise RegistryError("logged_at must be an ISO timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise RegistryError("logged_at must be UTC with an offset")
    for key in ("name", "lesson"):
        if not isinstance(record[key], str) or not record[key].strip():
            raise RegistryError(f"{key} must be non-empty text")
    if record["evidence_class"] not in CLASSES:
        raise RegistryError("evidence_class must be one of " + ", ".join(CLASSES))
    if record["disposition"] not in DISPOSITIONS:
        raise RegistryError("disposition must be one of " + ", ".join(DISPOSITIONS))
    context = record["context"]
    if not isinstance(context, dict) or not all(
            isinstance(context.get(k), str) and context[k].strip() for k in ("code", "period")):
        raise RegistryError("context needs non-empty code and period")
    _finite(context.get("costs_bp"), "context.costs_bp", 0, 10_000)
    metrics = record["metrics"]
    if not isinstance(metrics, dict) or set(metrics) - set(METRICS):
        raise RegistryError("metrics may only use: " + ", ".join(METRICS))
    _finite(metrics.get("net_cagr"), "net_cagr", -1, 100)
    _finite(metrics.get("max_drawdown"), "max_drawdown", 0, 1)
    _finite(metrics.get("longest_underwater_sessions"), "longest_underwater_sessions", integer=True)
    _finite(metrics.get("longest_underwater_days"), "longest_underwater_days", integer=True)
    for key in ("calmar", "sharpe", "turnover"):
        _finite(metrics.get(key), key)
    for key in ("tags",):
        if key in record and (not isinstance(record[key], list) or not all(isinstance(t, str) for t in record[key])):
            raise RegistryError("tags must be a list of text")
    for key in ("refs",):
        if key in record and not isinstance(record[key], dict):
            raise RegistryError("refs must be an object")
    if "imported" in record and not isinstance(record["imported"], bool):
        raise RegistryError("imported must be true or false")
    canonical_hash(record)  # strict JSON only
    return record


def _entry(prev, record):
    return {"prev": prev, "record": record, "hash": canonical_hash({"prev": prev, "record": record})}


def load(path):
    """Return validated records in order; any chain, shape or duplicate problem raises."""
    path = Path(path)
    if not path.exists():
        return []
    records, prev, seen = [], GENESIS, set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            record = validate(entry["record"])
        except (ValueError, KeyError, TypeError) as error:
            raise RegistryError(f"line {number}: unreadable or invalid entry ({error})") from None
        if entry.get("prev") != prev or entry.get("hash") != canonical_hash({"prev": prev, "record": record}):
            raise RegistryError(f"line {number}: hash chain broken")
        if record["record_id"] in seen:
            raise RegistryError(f"line {number}: duplicate record_id {record['record_id']}")
        seen.add(record["record_id"])
        records.append(record)
        prev = entry["hash"]
    return records


def head_hash(path):
    records = load(path)
    prev = GENESIS
    for record in records:
        prev = _entry(prev, record)["hash"]
    return prev


def append(path, record):
    """Validate and durably append one record; refuses duplicates. Returns the new head."""
    path = Path(path)
    validate(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_name(path.name + ".lock"), "a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        records = load(path)
        if any(r["record_id"] == record["record_id"] for r in records):
            raise RegistryError(f"record_id {record['record_id']} already exists")
        prev = head_hash(path) if records else GENESIS
        entry = _entry(prev, record)
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    return entry["hash"]
