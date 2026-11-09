"""Append-only trial ledger and sealed-holdout read gate (offline, single local writer).

Events: ``seal`` reserves a dated holdout window, ``freeze`` binds the frozen plan
that may read it, ``open`` logs a granted read, ``trial`` counts one research
attempt per cycle. A read of a sealed holdout is refused until it is frozen and
every granted read is recorded, so the holdout's exposure moves from
``protected_forward`` to ``previously_viewed`` (the vocabulary of
``rsi_contracts``) and later audits can see it. Refused reads are raised, not
recorded: they exposed no data.

Same journal pattern as ``rsi_adoption.AdoptionRegistry``: one flock'd writer,
JSONL receipts chained by ``canonical_hash`` and a durable head. A crash after the
log fsync but before the head update, or a torn unacknowledged last line, is
resumed when the writer reopens; any other disagreement fails closed. The chain is
local tamper evidence, not a signature: keep the returned head hash elsewhere for
a separate trust anchor. ``read_ledger`` is the lock-free, non-mutating view used
by audits. Use a local filesystem.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from research.control.rsi_contracts import canonical_hash


LEDGER_VERSION = "TRIAL-LEDGER-1"
EXPOSURE_PROTECTED = "protected_forward"
EXPOSURE_VIEWED = "previously_viewed"
_ZERO = "0" * 64
_SHA = re.compile(r"[0-9a-f]{64}")
_KINDS = {"seal": "holdout_id start end description",
          "freeze": "holdout_id plan_sha256 note",
          "open": "holdout_id cycle_id reader purpose",
          "trial": "cycle_id trial_number description"}


class LedgerError(ValueError):
    """The ledger is invalid, tampered, locked or a requested read is refused."""


def _object(value, keys, label):
    if type(value) is not dict or set(value) != set(keys.split()):
        raise LedgerError(f"{label} requires exactly: {keys}")
    return value


def _text(value, label):
    if type(value) is not str or not value.strip():
        raise LedgerError(f"{label} must be nonempty text")
    return value


def _day(value, label):
    try:
        if type(value) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError
        return date.fromisoformat(value)
    except ValueError as exc:
        raise LedgerError(f"{label} must be an ISO YYYY-MM-DD date") from exc


def seal_hash(payload):
    """Identity of a seal: the hash of its payload, independent of ledger position."""
    return canonical_hash(payload)


def _empty():
    return {"seals": {}, "trials": {}}


def _apply(event, state):
    """Pure transition; raises LedgerError so replay rejects invalid history."""
    _object(event, "kind created_utc payload", "event")
    stamp = event["created_utc"]
    if type(stamp) is not str or not stamp.endswith("+00:00"):
        raise LedgerError("Ledger UTC timestamp required")
    try:
        datetime.fromisoformat(stamp)
    except ValueError as exc:
        raise LedgerError("Invalid ledger timestamp") from exc
    kind, payload = event["kind"], event["payload"]
    if kind not in _KINDS:
        raise LedgerError("Unknown ledger event")
    _object(payload, _KINDS[kind], kind)
    state = deepcopy(state)
    if kind == "trial":
        cycle = _text(payload["cycle_id"], "cycle_id")
        _text(payload["description"], "description")
        expected = state["trials"].get(cycle, 0) + 1
        if type(payload["trial_number"]) is not int or payload["trial_number"] != expected:
            raise LedgerError("Trial number must advance the cycle count by exactly one")
        state["trials"][cycle] = expected
        return state
    holdout = _text(payload["holdout_id"], "holdout_id")
    seals = state["seals"]
    if kind == "seal":
        if holdout in seals:
            raise LedgerError("Holdout already sealed")
        _text(payload["description"], "description")
        if _day(payload["start"], "start") > _day(payload["end"], "end"):
            raise LedgerError("Holdout end precedes start")
        seals[holdout] = {"seal_hash": seal_hash(payload), "start": payload["start"],
                          "end": payload["end"], "frozen": False, "opens": 0}
        return state
    if holdout not in seals:
        raise LedgerError("Unknown holdout")
    entry = seals[holdout]
    if kind == "freeze":
        if entry["frozen"]:
            raise LedgerError("Holdout already frozen")
        if type(payload["plan_sha256"]) is not str or not _SHA.fullmatch(payload["plan_sha256"]):
            raise LedgerError("Freeze requires the frozen plan's lowercase SHA-256")
        _text(payload["note"], "note")
        entry["frozen"] = True
        return state
    if not entry["frozen"]:
        raise LedgerError("Sealed holdout cannot be read until it is frozen")
    for key in ("cycle_id", "reader", "purpose"):
        _text(payload[key], key)
    entry["opens"] += 1
    return state


def _encoded(value):
    canonical_hash(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise LedgerError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    try:
        value = json.loads(data, object_pairs_hook=pairs)
        canonical_hash(value)
        return value
    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        raise LedgerError("Invalid finite JSON record") from exc


def _regular_read(path, missing_ok=False):
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise LedgerError("Ledger authority must be a regular file")
        with os.fdopen(os.dup(descriptor), "rb") as stream:
            return stream.read()
    except FileNotFoundError:
        if missing_ok:
            return None
        raise LedgerError("Ledger file missing") from None
    except OSError as exc:
        raise LedgerError("Ledger file unsafe or unreadable") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _sync_directory(directory):
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class LedgerView:
    """Immutable-by-copy snapshot of a verified ledger."""

    def __init__(self, events, state, head_hash, torn_tail, head_lag):
        self._events, self._state = events, state
        self.head_hash = head_hash
        self.torn_tail = torn_tail      # unacknowledged partial last line (ignored)
        self.head_lag = head_lag        # last record durable but head not yet updated

    @property
    def events(self):
        return deepcopy(tuple(self._events))

    def seals(self):
        return deepcopy(self._state["seals"])

    def holdout_for_hash(self, digest):
        for holdout, entry in self._state["seals"].items():
            if entry["seal_hash"] == digest:
                return holdout
        return None

    def exposure(self, holdout_id):
        entry = self._entry(holdout_id)
        return EXPOSURE_VIEWED if entry["opens"] else EXPOSURE_PROTECTED

    def access_count(self, holdout_id):
        return self._entry(holdout_id)["opens"]

    def is_frozen(self, holdout_id):
        return self._entry(holdout_id)["frozen"]

    def trial_count(self, cycle_id):
        return self._state["trials"].get(cycle_id, 0)

    def opens(self, holdout_id=None, cycle_id=None):
        """Granted read events, optionally filtered by holdout and/or cycle."""
        return [deepcopy(record["event"]) for record in self._events
                if record["event"]["kind"] == "open"
                and holdout_id in (None, record["event"]["payload"]["holdout_id"])
                and cycle_id in (None, record["event"]["payload"]["cycle_id"])]

    def _entry(self, holdout_id):
        if holdout_id not in self._state["seals"]:
            raise LedgerError("Unknown holdout")
        return self._state["seals"][holdout_id]


def _scan(raw, head_raw):
    torn = b""
    if raw and not raw.endswith(b"\n"):
        cut = raw.rfind(b"\n") + 1
        raw, torn = raw[:cut], raw[cut:]
    events, state, previous, hashes = [], _empty(), _ZERO, [_ZERO]
    for line in raw.splitlines():
        record = _json(line)
        _object(record, "sequence previous_hash event event_hash", "receipt")
        body = {key: record[key] for key in ("sequence", "previous_hash", "event")}
        if (type(record["sequence"]) is not int or record["sequence"] != len(events) + 1
                or record["previous_hash"] != previous or record["event_hash"] != canonical_hash(body)):
            raise LedgerError("Broken ledger hash chain")
        state = _apply(record["event"], state)
        events.append(record)
        previous = record["event_hash"]
        hashes.append(previous)
    lag = False
    if head_raw is None:
        if events:
            if len(events) != 1:
                raise LedgerError("Ledger head missing; reconcile before continuing")
            lag = True
    else:
        head = _json(head_raw)
        _object(head, "sequence event_hash", "head")
        if type(head["sequence"]) is not int or not 0 <= head["sequence"] <= len(events):
            raise LedgerError("Ledger differs from durable head; possible truncation")
        if head["event_hash"] != hashes[head["sequence"]]:
            raise LedgerError("Ledger differs from durable head; reconcile before continuing")
        if head["sequence"] < len(events) - 1:
            raise LedgerError("Ledger differs from durable head; possible truncation")
        lag = head["sequence"] == len(events) - 1
    return LedgerView(events, state, previous, torn, lag), len(raw)


def read_ledger(directory):
    """Verify and return a lock-free snapshot; a missing directory/log is an empty ledger."""
    directory = Path(directory)
    if directory.is_symlink():
        raise LedgerError("Ledger directory cannot be a symlink")
    raw = _regular_read(directory / "ledger.jsonl", missing_ok=True) or b""
    head = _regular_read(directory / "head.json", missing_ok=True)
    return _scan(raw, head)[0]


class TrialLedger:
    """Single writer. Open as a context manager; a second concurrent writer is refused."""

    def __init__(self, directory):
        self.directory = Path(directory)
        if self.directory.is_symlink():
            raise LedgerError("Ledger directory cannot be a symlink")
        self.directory.mkdir(parents=True, exist_ok=True)
        self.log_path = self.directory / "ledger.jsonl"
        self.head_path = self.directory / "head.json"
        self._closed = False
        try:
            descriptor = os.open(self.directory / ".writer.lock",
                                 os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        except OSError as exc:
            raise LedgerError("Ledger lock is missing or unsafe") from exc
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise LedgerError("Ledger lock must be a regular file")
        self._lock = os.fdopen(descriptor, "r+")
        try:
            fcntl.flock(self._lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self._lock.close()
            self._closed = True
            raise LedgerError("Trial ledger already has a writer") from exc
        try:
            self._resume()
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        if not self._closed:
            fcntl.flock(self._lock.fileno(), fcntl.LOCK_UN)
            self._lock.close()
            self._closed = True

    def _resume(self):
        raw = _regular_read(self.log_path, missing_ok=True) or b""
        view, good = _scan(raw, _regular_read(self.head_path, missing_ok=True))
        if view.torn_tail:
            # Never acknowledged to a caller: drop it so the next append starts cleanly.
            with open(self.log_path, "r+b") as stream:
                stream.truncate(good)
                stream.flush()
                os.fsync(stream.fileno())
        if view.head_lag:
            self._write_head(view._events[-1])
        self._view = view

    def _refresh(self):
        if self._closed:
            raise LedgerError("Trial ledger is closed")
        view, good = _scan(_regular_read(self.log_path, missing_ok=True) or b"",
                           _regular_read(self.head_path, missing_ok=True))
        if view.torn_tail or view.head_lag or view.head_hash != self._view.head_hash:
            raise LedgerError("Ledger changed while writer is open")
        self._view = view

    @property
    def view(self):
        self._refresh()
        return self._view

    def _write_head(self, record):
        head = {"sequence": record["sequence"], "event_hash": record["event_hash"]}
        descriptor, temporary = tempfile.mkstemp(prefix=".head-", dir=self.directory)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(_encoded(head))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.head_path)
            _sync_directory(self.directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _append(self, kind, payload):
        self._refresh()
        view = self._view
        event = {"kind": kind, "created_utc": datetime.now(timezone.utc).isoformat(),
                 "payload": deepcopy(payload)}
        _apply(event, view._state)  # reject before anything touches disk
        body = {"sequence": len(view._events) + 1, "previous_hash": view.head_hash, "event": event}
        record = {**body, "event_hash": canonical_hash(body)}
        descriptor = os.open(self.log_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW
                             | os.O_NONBLOCK, 0o600)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise LedgerError("Ledger journal must be a regular file")
        with os.fdopen(descriptor, "ab") as stream:
            stream.write(_encoded(record) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        _sync_directory(self.directory)
        self._write_head(record)
        self._view = LedgerView(view._events + [record], _apply(event, view._state),
                                record["event_hash"], b"", False)
        return deepcopy(record)

    def seal(self, holdout_id, start, end, description):
        """Reserve [start, end] (inclusive ISO dates). Returns the seal hash."""
        payload = {"holdout_id": holdout_id, "start": start, "end": end, "description": description}
        self._append("seal", payload)
        return seal_hash(payload)

    def freeze(self, holdout_id, plan_sha256, note):
        """Bind the frozen plan; only now may the holdout be opened."""
        return self._append("freeze", {"holdout_id": holdout_id, "plan_sha256": plan_sha256,
                                       "note": note})

    def open(self, holdout_id, cycle_id, reader, purpose):
        """Gate and log a read. Raises LedgerError (nothing recorded) before freeze."""
        return self._append("open", {"holdout_id": holdout_id, "cycle_id": cycle_id,
                                     "reader": reader, "purpose": purpose})

    def trial(self, cycle_id, description):
        """Record one attempt; returns its 1-based per-cycle number."""
        self._refresh()
        number = self._view.trial_count(cycle_id) + 1
        self._append("trial", {"cycle_id": cycle_id, "trial_number": number,
                               "description": description})
        return number
