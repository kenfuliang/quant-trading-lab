"""Offline, versioned artifact attestation and synthetic research adoption.

Freeze a validated cycle and numerical gate before submitting its result. A result
must bind the exact frozen plan, incumbent/challenger, code/data/score identities,
declared evaluator and chronological exposure. ``evaluate_and_record`` always
rereads the saved artifact and recomputes the gate; a caller's ``passed`` flag is
never authority. Numeric metrics and integrity checks remain declarations: this
module verifies bytes and their consistency, not accounting/economic truth,
authenticated evaluator provenance, unseen alpha or operational readiness.

Only ``synthetic_engineering`` can adopt a research version. Financial research
passes remain provisional; no financial/production promotion is implemented.
Rollback appends a new decision and preserves every previous record.

The single-writer JSONL journal and durable head receipt reject altered/replayed
events, tail truncation and incomplete appends. An interrupted append/head update
fails closed and needs manual reconciliation. This local hash chain is not a
signature or protection against rewriting both files; retain returned receipts
outside this directory for a separate trust anchor. Use a local filesystem.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile

from research.rsi_contracts import canonical_hash, validate_cycle, verify_artifacts


REGISTRY_VERSION = "RSI-ADOPTION-1"
EVALUATION_VERSION = "RSI-EVALUATION-1"
_ZERO = "0" * 64


class AdoptionError(ValueError):
    """A frozen identity, saved result or registry is invalid/unsupported."""


def _object(value, keys, label):
    if type(value) is not dict or set(value) != set(keys.split()):
        raise AdoptionError(f"{label} requires exactly: {keys}")
    return value


def _text(value, label):
    if type(value) is not str or not value.strip():
        raise AdoptionError(f"{label} must be nonempty text")
    return value


def _sha(value):
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise AdoptionError("Expected lowercase SHA-256")
    return value


def _identity(value, *, evaluator=False):
    key = "id" if evaluator else "version"
    _object(value, f"{key} sha256", "identity")
    _text(value[key], key)
    _sha(value["sha256"])
    return deepcopy(value)


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise AdoptionError("Metrics and limits must be finite numbers, not booleans")
    return value


def _gate(value, cycle):
    _object(value, "metric direction incumbent_value meaningful_effect tolerance guardrails", "gate")
    _text(value["metric"], "primary metric")
    if value["direction"] not in ("higher", "lower"):
        raise AdoptionError("Gate direction must be higher or lower")
    for key in ("incumbent_value", "meaningful_effect", "tolerance"):
        _number(value[key])
    if (value["meaningful_effect"] <= 0 or value["tolerance"] < 0
            or value["tolerance"] >= value["meaningful_effect"]):
        raise AdoptionError("Gate requires a meaningful positive effect above tolerance")
    for key in ("meaningful_effect", "tolerance"):
        if value[key] != cycle["criteria"][key]:
            raise AdoptionError("Gate must preserve the cycle's frozen effect and tolerance")
    guardrails = value["guardrails"]
    if type(guardrails) is not dict or not guardrails:
        raise AdoptionError("Numerical guardrails are required")
    for name, bounds in guardrails.items():
        _text(name, "guardrail metric")
        if type(bounds) is not dict or not bounds or set(bounds) - {"min", "max"}:
            raise AdoptionError("Guardrails require min and/or max")
        for limit in bounds.values():
            _number(limit)
        if bounds.get("min", -math.inf) > bounds.get("max", math.inf):
            raise AdoptionError("Inverted guardrail range")
    canonical_hash(value)
    return deepcopy(value)


def _json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise AdoptionError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    try:
        value = json.loads(data, object_pairs_hook=pairs)
        canonical_hash(value)
        return value
    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        raise AdoptionError("Invalid finite JSON record") from exc


def _encoded(value):
    canonical_hash(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _same(left, right):
    """JSON identity must distinguish booleans, integers and float spellings."""
    return canonical_hash(left) == canonical_hash(right)


def _artifact_json(artifact, root):
    """Verify twice around a no-follow read, avoiding path replacement escapes."""
    entry = verify_artifacts([artifact], root)[0]
    descriptors = []
    try:
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        descriptors.append(directory)
        parts = entry["path"].split("/")
        for part in parts[:-1]:
            directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=directory)
            descriptors.append(directory)
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=directory)
        descriptors.append(descriptor)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise AdoptionError("Result artifact must be a regular file")
        with os.fdopen(os.dup(descriptor), "rb") as stream:
            data = stream.read()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise AdoptionError("Result artifact changed while reading")
        return _json(data)
    except OSError as exc:
        raise AdoptionError("Result artifact is unsafe or unreadable") from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


@dataclass(frozen=True)
class IndependentEvaluation:
    """Typed artifact attestation; fields are rechecked, never trusted as a pass."""
    context: dict
    artifact: dict
    metrics: dict
    checks: dict
    synthetic: bool
    passed: bool


class AdoptionRegistry:
    """One local writer; protected context is immutable after initialization."""

    def __init__(self, directory, *, artifact_root, incumbent, evaluator,
                 scope="synthetic_engineering"):
        if scope not in ("synthetic_engineering", "financial_research"):
            raise AdoptionError("Unknown adoption scope")
        self.root = Path(artifact_root).resolve(strict=True)
        self.config = {"schema_version": REGISTRY_VERSION,
                       "artifact_root": str(self.root),
                       "incumbent": _identity(incumbent),
                       "evaluator": _identity(evaluator, evaluator=True),
                       "scope": scope}
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.log_path = self.directory / "adoption.jsonl"
        self.head_path = self.directory / "head.json"
        self._closed = False
        self._lock = (self.directory / ".writer.lock").open("a+")
        try:
            fcntl.flock(self._lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self._lock.close()
            self._closed = True
            raise AdoptionError("Adoption registry already has a writer") from exc
        try:
            self._load()
            if not self._events:
                self._append("init", self.config)
            elif self._state["config"] != self.config:
                raise AdoptionError("Protected registry context changed")
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

    @property
    def state(self):
        self._load()
        return deepcopy(self._state)

    @property
    def receipts(self):
        self._load()
        return deepcopy(tuple(self._events))

    def _validate_plan(self, plan, state):
        _object(plan, "schema_version cycle candidate proposer_id code_sha256 data_sha256 "
                "score_sha256 evaluator scope gate", "adoption plan")
        if plan["schema_version"] != "RSI-ADOPTION-PLAN-1":
            raise AdoptionError("Unknown adoption plan version")
        cycle = validate_cycle(plan["cycle"])
        if cycle["incumbent"] != state["current"]:
            raise AdoptionError("Plan incumbent is no longer current")
        candidate = _identity(plan["candidate"])
        if (candidate["version"] in state["versions"]
                or candidate["sha256"] == cycle["incumbent"]["sha256"]):
            raise AdoptionError("Candidate version reused or identical to incumbent")
        if cycle["cycle_id"] in state["cycle_ids"]:
            raise AdoptionError("Cycle ID already frozen")
        _text(plan["proposer_id"], "proposer_id")
        if plan["proposer_id"] == self.config["evaluator"]["id"]:
            raise AdoptionError("Proposer and declared evaluator must differ")
        if plan["evaluator"] != self.config["evaluator"] or plan["scope"] != self.config["scope"]:
            raise AdoptionError("Protected evaluator or scope changed")
        for key in ("code_sha256", "data_sha256", "score_sha256"):
            _sha(plan[key])
        _gate(plan["gate"], cycle)
        verify_artifacts(cycle["artifacts"], self.root)

    def freeze_plan(self, cycle, *, candidate, proposer_id, code_sha256,
                    data_sha256, score_sha256, gate):
        """Persist protected identities/criteria before accepting a saved result."""
        self._load()
        plan = {"schema_version": "RSI-ADOPTION-PLAN-1", "cycle": validate_cycle(cycle),
                "candidate": deepcopy(candidate), "proposer_id": proposer_id,
                "code_sha256": code_sha256, "data_sha256": data_sha256,
                "score_sha256": score_sha256, "gate": deepcopy(gate),
                "evaluator": deepcopy(self.config["evaluator"]), "scope": self.config["scope"]}
        self._append("freeze", plan)
        return canonical_hash(plan)

    def _context(self, plan_hash, state):
        _sha(plan_hash)
        if plan_hash not in state["plans"]:
            raise AdoptionError("Unknown frozen plan")
        plan = state["plans"][plan_hash]
        return {"plan_sha256": plan_hash, "cycle_sha256": canonical_hash(plan["cycle"]),
                "incumbent": deepcopy(plan["cycle"]["incumbent"]),
                "candidate": deepcopy(plan["candidate"]),
                **{key: deepcopy(plan[key]) for key in
                   ("code_sha256", "data_sha256", "score_sha256", "evaluator", "scope")},
                "evaluation": deepcopy(plan["cycle"]["evaluation"])}

    def context_for(self, plan_hash):
        self._load()
        return self._context(plan_hash, self._state)

    def _evaluate(self, plan_hash, artifact, state):
        context = self._context(plan_hash, state)
        plan = state["plans"][plan_hash]
        verify_artifacts(plan["cycle"]["artifacts"], self.root)
        artifact = verify_artifacts([artifact], self.root)[0]
        if artifact["path"] in {item["path"] for item in plan["cycle"]["artifacts"]}:
            raise AdoptionError("Result must be distinct from pre-result input artifacts")
        result = _artifact_json(artifact, self.root)
        _object(result, "schema_version context metrics checks synthetic", "evaluation artifact")
        if result["schema_version"] != EVALUATION_VERSION or not _same(result["context"], context):
            raise AdoptionError("Evaluation identity/context mismatch")
        if type(result["synthetic"]) is not bool or result["synthetic"] != (self.config["scope"] == "synthetic_engineering"):
            raise AdoptionError("Evaluation synthetic status mismatches protected scope")
        checks = _object(result["checks"], "integrity accounting controls chronology", "checks")
        if any(type(value) is not bool for value in checks.values()):
            raise AdoptionError("Checks must be explicit booleans")
        gate = plan["gate"]
        metric_names = set(gate["guardrails"]) | {gate["metric"]}
        if type(result["metrics"]) is not dict or set(result["metrics"]) != metric_names:
            raise AdoptionError("Metrics must exactly match the frozen gate")
        metrics = result["metrics"]
        for value in metrics.values():
            _number(value)
        effect = metrics[gate["metric"]] - gate["incumbent_value"]
        if gate["direction"] == "lower":
            effect = -effect
        _number(effect)
        passed = all(checks.values()) and effect >= gate["meaningful_effect"]
        for metric, bounds in gate["guardrails"].items():
            value, tolerance = metrics[metric], gate["tolerance"]
            passed = passed and value >= bounds.get("min", -math.inf) - tolerance
            passed = passed and value <= bounds.get("max", math.inf) + tolerance
        return IndependentEvaluation(context, deepcopy(artifact), deepcopy(metrics),
                                     deepcopy(checks), result["synthetic"], passed)

    def evaluate_artifact(self, plan_hash, artifact):
        """Independently compute the frozen numerical gate from verified JSON bytes."""
        self._load()
        return self._evaluate(plan_hash, artifact, self._state)

    def evaluate_and_record(self, plan_hash, evaluation, *, decision_id, reason):
        self._load()
        if type(evaluation) is not IndependentEvaluation:
            raise AdoptionError("A typed IndependentEvaluation is required")
        # Recompute even for an object originally returned by this registry.
        expected = self._evaluate(plan_hash, evaluation.artifact, self._state)
        if not _same(asdict(evaluation), asdict(expected)):
            raise AdoptionError("Supplied evaluation differs from verified artifact/gate")
        status = ("adopted" if self.config["scope"] == "synthetic_engineering"
                  else "provisional") if expected.passed else "rejected"
        candidate = self._state["plans"][plan_hash]["candidate"]
        payload = {"decision_id": decision_id, "reason": reason, "plan_sha256": plan_hash,
                   "evaluation": asdict(expected), "status": status,
                   "prior": deepcopy(self._state["current"]),
                   "new": deepcopy(candidate if status == "adopted" else self._state["current"])}
        return self._append("evaluation", payload)

    def rollback(self, version, *, decision_id, reason):
        self._load()
        if version not in self._state["adopted_versions"]:
            raise AdoptionError("Rollback target was never adopted")
        return self._append("rollback", {"decision_id": decision_id, "reason": reason,
                            "prior": deepcopy(self._state["current"]),
                            "new": deepcopy(self._state["adopted_versions"][version])})

    def _apply(self, event, state):
        _object(event, "kind created_utc payload", "event")
        stamp = event["created_utc"]
        if type(stamp) is not str or not stamp.endswith("+00:00"):
            raise AdoptionError("Registry UTC timestamp required")
        try:
            datetime.fromisoformat(stamp)
        except ValueError as exc:
            raise AdoptionError("Invalid registry timestamp") from exc
        kind, payload = event["kind"], event["payload"]
        state = deepcopy(state)
        if kind == "init":
            if state or payload != self.config:
                raise AdoptionError("Invalid registry initialization/context")
            return {"config": deepcopy(payload), "current": deepcopy(payload["incumbent"]),
                    "plans": {}, "cycle_ids": [], "versions": {payload["incumbent"]["version"]: payload["incumbent"]},
                    "adopted_versions": {payload["incumbent"]["version"]: payload["incumbent"]},
                    "dispositions": {}, "decision_ids": []}
        if not state:
            raise AdoptionError("Registry initialization is missing")
        if kind == "freeze":
            self._validate_plan(payload, state)
            digest = canonical_hash(payload)
            if digest in state["plans"]:
                raise AdoptionError("Duplicate frozen plan")
            state["plans"][digest] = deepcopy(payload)
            state["cycle_ids"].append(payload["cycle"]["cycle_id"])
            state["versions"][payload["candidate"]["version"]] = deepcopy(payload["candidate"])
            return state
        if kind not in ("evaluation", "rollback"):
            raise AdoptionError("Unknown registry event")
        keys = "decision_id reason prior new"
        if kind == "evaluation":
            keys += " plan_sha256 evaluation status"
        _object(payload, keys, "decision")
        _text(payload["decision_id"], "decision_id")
        _text(payload["reason"], "decision reason")
        if payload["decision_id"] in state["decision_ids"]:
            raise AdoptionError("Decision ID already recorded")
        if payload["prior"] != state["current"]:
            raise AdoptionError("Decision prior version differs from current incumbent")
        if kind == "evaluation":
            plan_hash = payload["plan_sha256"]
            if plan_hash in state["dispositions"]:
                raise AdoptionError("Plan already has a decision")
            context = self._context(plan_hash, state)
            if context["incumbent"] != state["current"]:
                raise AdoptionError("Evaluation references a superseded incumbent")
            _object(payload["evaluation"], "context artifact metrics checks synthetic passed", "attestation")
            result = self._evaluate(plan_hash, payload["evaluation"]["artifact"], state)
            if not _same(payload["evaluation"], asdict(result)):
                raise AdoptionError("Recorded attestation differs from verified gate")
            status = ("adopted" if self.config["scope"] == "synthetic_engineering"
                      else "provisional") if result.passed else "rejected"
            new = context["candidate"] if status == "adopted" else state["current"]
            if payload["status"] != status or payload["new"] != new:
                raise AdoptionError("Recorded disposition violates the protected gate")
            state["dispositions"][plan_hash] = deepcopy(payload)
            if status == "adopted":
                state["adopted_versions"][new["version"]] = deepcopy(new)
        else:
            new = _identity(payload["new"])
            if state["adopted_versions"].get(new["version"]) != new or new == state["current"]:
                raise AdoptionError("Rollback requires a different previously adopted version")
        state["current"] = deepcopy(payload["new"])
        state["decision_ids"].append(payload["decision_id"])
        return state

    def _load(self):
        if self._closed:
            raise AdoptionError("Adoption registry is closed")
        if self.log_path.is_symlink() or self.head_path.is_symlink():
            raise AdoptionError("Registry files cannot be symlinks")
        self._events, self._state = [], {}
        if not self.log_path.exists() and not self.head_path.exists():
            return
        if not self.log_path.exists() or not self.head_path.exists():
            raise AdoptionError("Incomplete registry/head; manual reconciliation required")
        raw = self.log_path.read_bytes()
        if not raw or not raw.endswith(b"\n"):
            raise AdoptionError("Incomplete registry append")
        previous = _ZERO
        for line in raw.splitlines():
            record = _json(line)
            _object(record, "sequence previous_hash event event_hash", "receipt")
            body = {key: record[key] for key in ("sequence", "previous_hash", "event")}
            if (type(record["sequence"]) is not int or record["sequence"] != len(self._events) + 1
                    or record["previous_hash"] != previous or record["event_hash"] != canonical_hash(body)):
                raise AdoptionError("Broken registry receipt hash chain")
            self._state = self._apply(record["event"], self._state)
            self._events.append(record)
            previous = record["event_hash"]
        head = _json(self.head_path.read_bytes())
        _object(head, "sequence event_hash", "head receipt")
        if type(head["sequence"]) is not int or head != {"sequence": len(self._events), "event_hash": previous}:
            raise AdoptionError("Registry differs from durable head; reconcile before continuing")

    def _append(self, kind, payload):
        event = {"kind": kind, "created_utc": datetime.now(timezone.utc).isoformat(),
                 "payload": deepcopy(payload)}
        state = self._apply(event, self._state)
        body = {"sequence": len(self._events) + 1,
                "previous_hash": self._events[-1]["event_hash"] if self._events else _ZERO,
                "event": event}
        record = {**body, "event_hash": canonical_hash(body)}
        with self.log_path.open("ab") as stream:
            stream.write(_encoded(record) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        head = {"sequence": record["sequence"], "event_hash": record["event_hash"]}
        descriptor, temporary = tempfile.mkstemp(prefix=".head-", dir=self.directory)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(_encoded(head))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.head_path)
            directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        self._events.append(record)
        self._state = state
        return deepcopy(record)
