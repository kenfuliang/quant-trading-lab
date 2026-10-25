"""Bounded offline research decisions; recording does not execute or verify a study.

Use ``with ResearchController(directory, context=..., budget=...)`` for one writer.
The hash-chained/fsynced append log is authoritative. A snapshot is replaced
atomically after append. A valid older/missing snapshot is reconstructed on resume;
a changed snapshot or malformed/partial log fails closed. This is crash recovery,
not a distributed transaction or cryptographic protection against rewriting both
files. Do not use network filesystems without validating their lock/fsync semantics.

Budget units are logical actions and caller-declared resource units. Financial
simulation limits and actual process metering remain the coordinator's authority.
Action observation_spec and question definitions must describe semantics (hashes,
rule/config/data/estimand), not titles. Exact canonical equality detects duplicates;
this module cannot infer semantic equivalence of arbitrary different descriptions.
Progress credit means a unique caller-supplied decision/evidence claim, not proof of
correct findings. Independent artifact verification remains external. ``select``
checks eligibility of the chosen action; the coordinator retains the full preview
trace and justifies selection/baseline/exploration choices from the candidate set.
"""
from __future__ import annotations

import copy
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any

from research.scoring import POLICY_HASH, rank_actions


class ControllerError(ValueError):
    """Invalid, incompatible or corrupted research state."""


class WriterBusy(ControllerError):
    """Another local writer holds this journal."""


def _json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ControllerError("Only finite JSON-ready records are supported") from exc


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ControllerError(f"{name} must be a nonempty string")
    return value


def _strings(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise ControllerError(f"{name} must be a list of nonempty strings")
    return sorted(set(value))


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ControllerError(f"{name} must be finite and nonnegative")
    return float(value)


def _integer(value: Any, name: str, minimum: int = 1) -> int:
    if type(value) is not int or value < minimum:
        raise ControllerError(f"{name} must be an integer >= {minimum}")
    return value


class ResearchController:
    """Preview, reserve, then record external observations with explicit provenance."""

    def __init__(self, directory: str | Path, *, context: dict, budget: dict, child_limit: int = 2):
        if not isinstance(context, dict) or not context:
            raise ControllerError("context must include a nonempty frozen identity")
        _text(context.get("score_version"), "context.score_version")
        _json(context)
        if not isinstance(budget, dict):
            raise ControllerError("budget must be explicit")
        expected = {"max_attempts", "max_resource_units", "resource_unit", "max_active_branches"}
        if set(budget) != expected:
            raise ControllerError(f"budget fields must be exactly {sorted(expected)}")
        _integer(budget["max_attempts"], "max_attempts")
        _integer(budget["max_active_branches"], "max_active_branches")
        _number(budget["max_resource_units"], "max_resource_units")
        _text(budget["resource_unit"], "resource_unit")
        _integer(child_limit, "child_limit")
        self.config = json.loads(_json({"context": context, "budget": budget, "child_limit": child_limit, "scoring_policy_hash": POLICY_HASH}))
        self.context_id = _hash(context)
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.log_path = self.directory / "events.jsonl"
        self.snapshot_path = self.directory / "snapshot.json"
        self._lock = (self.directory / ".writer.lock").open("a+")
        try:
            fcntl.flock(self._lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self._lock.close()
            raise WriterBusy("Research journal already has a writer") from exc
        self._closed = False
        try:
            self._load()
            if not self._events:
                self._commit("__init__", "init", self.config)
            elif self._state["config"] != self.config:
                raise ControllerError("Context, score version, budget or child limit changed; use a new journal")
        except BaseException:
            self.close()
            raise

    @property
    def state(self) -> dict:
        """Detached inspection copy; mutations must go through journal operations."""
        return copy.deepcopy(self._state)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        if not self._closed:
            fcntl.flock(self._lock.fileno(), fcntl.LOCK_UN)
            self._lock.close()
            self._closed = True

    def _open(self):
        if self._closed:
            raise ControllerError("Controller is closed")

    @staticmethod
    def _empty() -> dict:
        return {"config": None, "questions": {}, "branches": {}, "attempts": {},
                "operations": {}, "resolved_questions": [], "credited_evidence": [],
                "resource_bound_breached": False}

    def _load(self):
        self._state = self._empty()
        self._events = []
        prefixes = []
        head = "0" * 64
        if self.log_path.exists():
            raw = self.log_path.read_bytes()
            if raw and not raw.endswith(b"\n"):
                raise ControllerError("Partial final log record; manual recovery required")
            try:
                for line in raw.splitlines():
                    record = json.loads(line)
                    if set(record) != {"sequence", "previous_hash", "event", "event_hash"}:
                        raise ControllerError("Unexpected log record fields")
                    body = {k: record[k] for k in ("sequence", "previous_hash", "event")}
                    if record["sequence"] != len(self._events) + 1 or record["previous_hash"] != head or record["event_hash"] != _hash(body):
                        raise ControllerError("Broken research event hash chain")
                    self._state, _ = self._apply(self._state, record["event"])
                    self._events.append(record)
                    head = record["event_hash"]
                    prefixes.append(_hash(self._state))
            except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
                raise ControllerError("Invalid research log") from exc
        if self.snapshot_path.exists():
            try:
                snapshot = json.loads(self.snapshot_path.read_text())
                seq = snapshot["sequence"]
                if type(seq) is not int or not 1 <= seq <= len(self._events):
                    raise ControllerError("Snapshot has impossible sequence")
                if set(snapshot) != {"sequence", "head_hash", "state"} or snapshot["head_hash"] != self._events[seq - 1]["event_hash"] or _hash(snapshot["state"]) != prefixes[seq - 1]:
                    raise ControllerError("Snapshot differs from append log")
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                raise ControllerError("Invalid research snapshot") from exc
        if self._events:
            self._snapshot()

    def _snapshot(self):
        snapshot = {"sequence": len(self._events), "head_hash": self._events[-1]["event_hash"], "state": self._state}
        fd, name = tempfile.mkstemp(prefix=".snapshot-", dir=self.directory)
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(_json(snapshot) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.snapshot_path)
            directory_fd = os.open(self.directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def _commit(self, operation_id: str, kind: str, payload: dict) -> dict:
        self._open()
        _text(operation_id, "operation_id")
        request = {"kind": kind, "payload": payload}
        request_hash = _hash(request)
        previous = self._state["operations"].get(operation_id)
        if previous:
            if previous["request_hash"] != request_hash:
                raise ControllerError("Operation ID reused with a changed payload")
            return copy.deepcopy(previous["result"])
        event = {"operation_id": operation_id, **request,
                 "recorded_at_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
        state, result = self._apply(self._state, event)
        body = {"sequence": len(self._events) + 1,
                "previous_hash": self._events[-1]["event_hash"] if self._events else "0" * 64,
                "event": event}
        record = {**body, "event_hash": _hash(body)}
        try:
            with self.log_path.open("ab") as stream:
                stream.write((_json(record) + "\n").encode())
                stream.flush()
                os.fsync(stream.fileno())
            self._state = state
            self._events.append(record)
            self._snapshot()
        except OSError:
            self.close()  # caller must reopen and reconcile the authoritative log
            raise
        return copy.deepcopy(result)

    def _canonical_question(self, state: dict, question_id: str) -> str:
        if question_id not in state["questions"]:
            raise ControllerError(f"Unregistered question: {question_id}")
        return state["questions"][question_id]["canonical_id"]

    def register_question(self, operation_id: str, question_id: str, definition: dict) -> dict:
        return self._commit(operation_id, "question", {"question_id": question_id, "definition": definition})

    def register_branch(self, operation_id: str, *, branch_id: str, question_id: str,
                        mechanism: str, parent_branch_id: str | None = None) -> dict:
        return self._commit(operation_id, "branch", {"branch_id": branch_id, "question_id": question_id,
                            "mechanism": mechanism, "parent_branch_id": parent_branch_id})

    def set_branch(self, operation_id: str, *, branch_id: str, status: str,
                   reason: str, evidence: list[str]) -> dict:
        return self._commit(operation_id, "branch_status", {"branch_id": branch_id, "status": status,
                            "reason": reason, "evidence": evidence})

    def _usage(self, state: dict) -> dict:
        units = sum(a["outcome"]["actual_resource_units"] if a.get("outcome") else a["action"]["cost_upper_bound"] for a in state["attempts"].values())
        return {"attempts": len(state["attempts"]), "resource_units_committed": units,
                "resource_unit": self.config["budget"]["resource_unit"]}

    def usage(self) -> dict:
        self._open()
        return self._usage(self._state)

    def _prepare_action(self, state: dict, action: dict) -> dict:
        a = json.loads(_json(action))
        _text(a.get("id"), "action.id")
        if a.get("context_id") != self.context_id:
            raise ControllerError("Action context differs from frozen controller context")
        branch = state["branches"].get(a.get("branch_id"))
        if branch is None:
            raise ControllerError("Action branch is unregistered")
        a["question_id"] = self._canonical_question(state, a.get("question_id"))
        if a["question_id"] != branch["question_id"]:
            raise ControllerError("Action question differs from its branch")
        a["shared_questions"] = sorted({self._canonical_question(state, q) for q in a.get("shared_questions", [])})
        _text(a.get("observation_key"), "observation_key")
        spec = a.get("observation_spec")
        if not isinstance(spec, dict) or not spec:
            raise ControllerError("observation_spec must identify actual observation semantics")
        a["observation_identity"] = _hash({"context_id": self.context_id, "spec": spec})
        a["observation_label"] = a["observation_key"]
        a["observation_key"] = a["observation_identity"]
        a["evidence"] = _strings(a.get("evidence", []), "evidence")
        if branch["status"] != "active":
            a["blocked_reason"] = f"Branch is {branch['status']}: {branch['reason']}"
        attempts = list(state["attempts"].values())
        if any(x["action"]["observation_identity"] == a["observation_identity"] for x in attempts):
            a["blocked_reason"] = "Observation already reserved or attempted; no fresh credit for renaming/retry"
        if any(x["status"] == "reserved" and
               ({x["action"]["question_id"], *x["action"]["shared_questions"]} & {a["question_id"], *a["shared_questions"]})
               for x in attempts):
            a["blocked_reason"] = "Question already has an outstanding action"
        if any(x["action"]["id"] == a["id"] for x in attempts):
            a["blocked_reason"] = "Action ID already attempted"
        if a["question_id"] in state["resolved_questions"]:
            a["blocked_reason"] = "Question already resolved; register a materially different question"
        return a

    def preview(self, actions: list[dict], *, policy: str = "priority") -> dict:
        """Read-only selection trace; selection itself reserves no resources."""
        self._open()
        return self._preview(self._state, actions, policy)

    def _preview(self, state: dict, actions: list[dict], policy: str) -> dict:
        if policy not in {"priority", "breadth_first"}:
            raise ControllerError("Unknown selection policy")
        if not isinstance(actions, list):
            raise ControllerError("actions must be a list")
        prepared, declined = [], []
        for action in actions:
            try:
                prepared.append(self._prepare_action(state, action))
            except ControllerError as exc:
                declined.append({"id": action.get("id") if isinstance(action, dict) else None,
                                 "state": "invalid", "reason": str(exc)})
        usage = self._usage(state)
        stop = None
        budget = self.config["budget"]
        if usage["attempts"] >= budget["max_attempts"]:
            stop = "Logical attempt budget exhausted (failures included)"
        if state["resource_bound_breached"]:
            stop = "An observed action exceeded its frozen resource bound"
        remaining = max(0.0, budget["max_resource_units"] - usage["resource_units_committed"])
        ranking = rank_actions(prepared, context_id=self.context_id, budget_remaining=remaining)
        ranked = ranking["ranked"]
        if policy == "breadth_first":
            def depth(action):
                branch, count = state["branches"][action["branch_id"]], 0
                while branch["parent_branch_id"] is not None:
                    count += 1
                    branch = state["branches"][branch["parent_branch_id"]]
                return count, action["id"]
            ranked = sorted(ranked, key=depth)
        selection = ranked[0] if ranked and stop is None else None
        prior_mechanisms = [state["branches"][a["action"]["branch_id"]]["mechanism"] for a in state["attempts"].values()]
        mechanism = state["branches"][selection["branch_id"]]["mechanism"] if selection else None
        return {**ranking, "ranked": ranked, "excluded": ranking["excluded"] + declined,
                "selected": selection, "policy": policy, "stop_reason": stop,
                "state": "stopped" if stop is not None else ranking["state"],
                "usage": usage, "resource_remaining": remaining,
                "distinct_mechanism_in_first_two": None if not selection or len(prior_mechanisms) != 1 else mechanism != prior_mechanisms[0],
                "exploration_note": "Distinct-mechanism reservation is coordinator policy; this trace does not silently override it"}

    def select(self, operation_id: str, action: dict) -> dict:
        """Reserve before external work. Does not invoke a process or simulation."""
        return self._commit(operation_id, "select", {"action": action})

    def record(self, operation_id: str, attempt_id: str, outcome: dict) -> dict:
        """Record caller-supplied findings; execution/financial verification is external."""
        return self._commit(operation_id, "outcome", {"attempt_id": attempt_id, "outcome": outcome})

    def _apply(self, old: dict, event: dict) -> tuple[dict, dict]:
        state = copy.deepcopy(old)
        kind, p, op = event["kind"], event["payload"], event["operation_id"]
        if op in state["operations"]:
            raise ControllerError("Duplicate operation in append log")
        if state["config"] is None and kind != "init":
            raise ControllerError("Missing journal initialization")
        if kind == "init":
            if state["config"] is not None or p != self.config:
                raise ControllerError("Invalid initialization/config context")
            state["config"] = p
            result = {"context_id": self.context_id, "status": "initialized"}
        elif kind == "question":
            q = _text(p["question_id"], "question_id")
            definition = p["definition"]
            if q in state["questions"] or not isinstance(definition, dict) or not definition:
                raise ControllerError("Question ID already exists or definition missing")
            identity = _hash(definition)
            canonical = next((v["canonical_id"] for v in state["questions"].values() if v["definition_hash"] == identity), q)
            state["questions"][q] = {"definition": definition, "definition_hash": identity, "canonical_id": canonical}
            result = {"question_id": q, "canonical_id": canonical, "new_question": canonical == q}
        elif kind == "branch":
            b = _text(p["branch_id"], "branch_id")
            if b in state["branches"]:
                raise ControllerError("Branch ID already exists")
            question = self._canonical_question(state, p["question_id"])
            mechanism = _text(p["mechanism"], "mechanism")
            parent = p["parent_branch_id"]
            if parent is not None:
                if parent not in state["branches"]:
                    raise ControllerError("Unknown parent branch")
                if sum(x["parent_branch_id"] == parent for x in state["branches"].values()) >= self.config["child_limit"]:
                    raise ControllerError("Parent branch child limit reached")
            if sum(b["status"] == "active" for b in state["branches"].values()) >= self.config["budget"]["max_active_branches"]:
                raise ControllerError("Active branch budget exhausted")
            state["branches"][b] = {"question_id": question, "mechanism": mechanism,
                                   "parent_branch_id": parent, "status": "active", "reason": "registered", "evidence": [],
                                   "seen_evidence": [], "status_history": [{"status": "active", "reason": "registered", "evidence": []}]}
            result = {"branch_id": b, "status": "active"}
        elif kind == "branch_status":
            b = state["branches"].get(p["branch_id"])
            if b is None or p["status"] not in {"active", "paused", "blocked", "retired"}:
                raise ControllerError("Unknown branch or status")
            reason, evidence = _text(p["reason"], "reason"), _strings(p["evidence"], "evidence")
            if any(a["status"] == "reserved" and a["action"]["branch_id"] == p["branch_id"] for a in state["attempts"].values()):
                raise ControllerError("Record outstanding attempt before changing branch status")
            if p["status"] == "active" and b["status"] != "active":
                if reason in {h["reason"] for h in b["status_history"]} or not set(evidence) - set(b["seen_evidence"]):
                    raise ControllerError("Reopening requires changed reason and new evidence")
                if sum(v["status"] == "active" for v in state["branches"].values()) >= self.config["budget"]["max_active_branches"]:
                    raise ControllerError("Active branch budget exhausted")
            b["seen_evidence"] = sorted(set(b["seen_evidence"]) | set(evidence))
            b["status_history"].append({"status": p["status"], "reason": reason, "evidence": evidence})
            b.update(status=p["status"], reason=reason, evidence=evidence)
            result = {"branch_id": p["branch_id"], "status": p["status"], "reason": reason}
        elif kind == "select":
            trace = self._preview(state, [p["action"]], "priority")
            if trace["selected"] is None:
                raise ControllerError(f"Action cannot be reserved: {trace['stop_reason'] or trace['excluded']}")
            a = self._prepare_action(state, p["action"])
            attempt = f"attempt-{len(state['attempts']) + 1:04d}"
            state["attempts"][attempt] = {"action": a, "status": "reserved", "outcome": None}
            result = {"attempt_id": attempt, "status": "reserved", "execution_verified": False,
                      "observation_identity": a["observation_identity"]}
        elif kind == "outcome":
            attempt = state["attempts"].get(p["attempt_id"])
            if attempt is None or attempt["status"] != "reserved":
                raise ControllerError("Unknown or already finalized attempt")
            outcome = json.loads(_json(p["outcome"]))
            if outcome.get("status") not in {"completed", "failed"}:
                raise ControllerError("Outcome must be completed or failed")
            _text(outcome.get("summary"), "outcome.summary")
            evidence = _strings(outcome.get("evidence", []), "outcome.evidence")
            trace = _strings(outcome.get("inspection_trace"), "inspection_trace")
            if not trace:
                raise ControllerError("Outcome requires an inspection trace")
            units = _number(outcome.get("actual_resource_units"), "actual_resource_units")
            observation_kind = outcome.get("observation_kind")
            if observation_kind not in {"read_only_analysis", "fresh_simulation", "cache_reuse", "synthetic_fixture"}:
                raise ControllerError("Explicit observation_kind required")
            resolutions = outcome.get("resolutions", [])
            if not isinstance(resolutions, list):
                raise ControllerError("resolutions must be a list")
            allowed = {attempt["action"]["question_id"], *attempt["action"]["shared_questions"]}
            fresh, credited = set(evidence) - set(state["credited_evidence"]), []
            for resolution in resolutions:
                q = self._canonical_question(state, resolution.get("question_id"))
                if q not in allowed:
                    raise ControllerError("Resolution is outside the reserved decision questions")
                _text(resolution.get("decision"), "resolution.decision")
                _text(resolution.get("finding"), "resolution.finding")
                pointers = set(_strings(resolution.get("evidence"), "resolution.evidence"))
                if not pointers or not pointers <= set(evidence):
                    raise ControllerError("Resolution must link actual outcome evidence")
                if outcome["status"] == "completed" and observation_kind != "cache_reuse" and pointers & fresh and q not in state["resolved_questions"] and q not in credited:
                    credited.append(q)
            if credited:
                state["resolved_questions"] = sorted(set(state["resolved_questions"]) | set(credited))
                state["credited_evidence"] = sorted(set(state["credited_evidence"]) | set(evidence))
            exceeded = units > attempt["action"]["cost_upper_bound"]
            state["resource_bound_breached"] |= exceeded
            outcome.update(evidence=evidence, inspection_trace=trace, actual_resource_units=units)
            attempt.update(status=outcome["status"], outcome=outcome)
            result = {"attempt_id": p["attempt_id"], "status": "outcome_recorded", "claimed_outcome": outcome["status"],
                      "execution_verified": False, "credited_questions": credited,
                      "credit_reason": "Distinct decision evidence recorded" if credited else "No new credited decision evidence",
                      "resource_bound_breached": exceeded, "inspection_trace": trace}
        else:
            raise ControllerError(f"Unknown event kind: {kind}")
        state["operations"][op] = {"request_hash": _hash({"kind": kind, "payload": p}), "result": result}
        return state, result
