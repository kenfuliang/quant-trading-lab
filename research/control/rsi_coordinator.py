"""One local, bounded OFFLINE execution program around ResearchController.

Only two registered adapters exist: a synthetic subprocess fixture and the existing
saved-C001 checker's read-only preflight. Financial execution is unsupported.
No caller-provided argv, financial count, evaluator or shell is accepted. This is
research infrastructure, not an operating-system sandbox or broker state authority.

The controller owns the writer lock and logical decisions. Under that same lock,
execution.jsonl owns reservations, launch evidence, captured output and audits.
Every reservation consumes one program slot even if launch fails or never occurs.
An interrupted launch intent is ambiguous and stops the entire program; it is never
automatically relaunched. These files need local flock/fsync semantics. Hash chains
detect accidental edits, not an attacker rewriting both a log and its evidence.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

from research.control.research_controller import ControllerError, ResearchController, WriterBusy


ROOT = Path(__file__).resolve().parents[2]
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")
ADAPTER_VERSION = "rsi-current-offline-adapters-2"
TERMINAL = {"completed", "failed", "timed_out", "interrupted_before_launch",
            "interrupted_after_launch", "integrity_failed", "ambiguous"}
# Deliberately fixed child code: it cannot import a strategy or accept source code.
FIXTURE_SOURCE = '''import json,pathlib,sys,time
p=json.loads(sys.argv[1]); d=pathlib.Path(sys.argv[2]); d.mkdir(parents=True,exist_ok=False)
print(p["stdout"],flush=True); print(p["stderr"],file=sys.stderr,flush=True)
(d/"partial.txt").write_text("synthetic partial evidence\\n")
time.sleep(p["sleep_seconds"])
if p["behavior"]=="fail": sys.exit(7)
if p["behavior"]=="missing": sys.exit(0)
(d/"result.json").write_text(json.dumps({"synthetic_fixture":True,"passed":True,"payload":p["payload"]},sort_keys=True,separators=(",",":"),allow_nan=False)+"\\n")
'''


class RSIError(ControllerError):
    """Invalid program, exhausted bound or unverified execution evidence."""


class _LaunchDeadline(RSIError):
    """Durable reservation exists, but no child was launched before deadline."""


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise RSIError("Only finite JSON-ready records are supported") from exc


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _hash(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _name(value, label):
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise RSIError(f"{label} must be a safe nonempty ID")
    return value


def _positive(value, label, *, zero=False, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < (0 if zero else 1e-12) or (integer and type(value) is not int):
        raise RSIError(f"{label} must be a finite {'nonnegative' if zero else 'positive'} {'integer' if integer else 'number'}")
    return value


def synthetic_case(case_id, *, payload=None, behavior="success", sleep_seconds=0,
                   stdout="synthetic stdout", stderr="synthetic stderr", timeout_seconds=10):
    """Build a synthetic, zero-financial-slot adapter request; not arbitrary code."""
    return {"case_id": case_id, "adapter": "synthetic_fixture", "timeout_seconds": timeout_seconds,
            "parameters": {"payload": {} if payload is None else payload, "behavior": behavior,
                           "sleep_seconds": sleep_seconds, "stdout": stdout, "stderr": stderr}}


def saved_preflight_case(case_id, *, timeout_seconds=30):
    """Build the exact saved checker preflight; --execute/--case are never allowed."""
    return {"case_id": case_id, "adapter": "saved_c001_preflight",
            "timeout_seconds": timeout_seconds, "parameters": {}}


def _case_request(raw):
    if not isinstance(raw, dict) or set(raw) != {"case_id", "adapter", "timeout_seconds", "parameters"}:
        raise RSIError("Unsupported case schema; arbitrary argv/financial counts are forbidden")
    case = json.loads(canonical(raw))
    _name(case["case_id"], "case_id")
    _positive(case["timeout_seconds"], "timeout_seconds")
    p = case["parameters"]
    if case["adapter"] == "synthetic_fixture":
        if not isinstance(p, dict) or set(p) != {"payload", "behavior", "sleep_seconds", "stdout", "stderr"} or p["behavior"] not in {"success", "fail", "missing"}:
            raise RSIError("Unsupported synthetic fixture contract")
        _positive(p["sleep_seconds"], "sleep_seconds", zero=True)
        if not isinstance(p["stdout"], str) or not isinstance(p["stderr"], str):
            raise RSIError("Fixture output must be text")
    elif case["adapter"] == "saved_c001_preflight":
        if p != {}:
            raise RSIError("Preflight takes no options; financial execution unsupported")
    else:
        raise RSIError("Unregistered adapter; financial execution unsupported")
    return case


def _argv(case, artifact_directory):
    if case["adapter"] == "synthetic_fixture":
        return [sys.executable, "-I", "-c", FIXTURE_SOURCE, canonical(case["parameters"]), str(artifact_directory)]
    return [sys.executable, str(ROOT / "scripts/current/rsi_foundation.py"), "preflight", "--attest"]


def _code_paths():
    # Freeze the local transitive source universe rather than accepting a caller's
    # incomplete list. Dependency *locks* identify configuration, not binary proof.
    paths = [p for folder in ("research", "reporting", "scripts") for p in (ROOT / folder).rglob("*.py")]
    paths += [ROOT / "requirements.txt", ROOT / "requirements.lock.txt"]
    return sorted(paths)


def _parents(raw):
    if not isinstance(raw, dict):
        raise RSIError("parent_identities must map local paths to SHA256")
    result = {}
    for path, expected in raw.items():
        p = Path(path)
        if not p.is_absolute():
            p = ROOT / p
        if p.is_symlink() or not p.is_file() or not re.fullmatch(r"[0-9a-f]{64}", str(expected)) or digest(p) != expected:
            raise RSIError(f"Parent identity missing or changed: {path}")
        result[str(p.resolve())] = expected
    return result


def _saved_preflight_inputs():
    from research.control.rsi_contracts import preflight_known_c001, _C001_RECEIPT
    # Authenticate the entire historical closure before a reservation can exist.
    preflight_known_c001(ROOT)
    receipt_path = ROOT / _C001_RECEIPT["path"]
    receipt = json.loads(receipt_path.read_text())
    plan_path = ROOT / receipt["plan"]
    plan = json.loads(plan_path.read_text())
    identities = {str(receipt_path): _C001_RECEIPT["sha256"], str(plan_path): receipt["plan_sha256"],
                  str(ROOT / plan["design_path"]): plan["design_sha256"],
                  str(ROOT / plan["source"]["path"]): plan["source"]["sha256"],
                  str(ROOT / "docs/research-standard.md"): plan["golden_standard_sha256"],
                  str(ROOT / receipt["engineering_followup"]["source"]): receipt["engineering_followup"]["sha256"]}
    identities.update({str(ROOT / p): h for p, h in plan["code_hashes"].items()})
    manifests = dict(plan["parent_manifests"])
    manifests[receipt["artifacts"]] = receipt["manifest_sha256"]
    for directory, expected in manifests.items():
        manifest = ROOT / directory / "manifest.json"
        identities[str(manifest)] = expected
        saved = json.loads(manifest.read_text())
        for relative, sha in saved["artifact_hashes"].items():
            p = Path(relative)
            if p.is_absolute() or ".." in p.parts:
                raise RSIError("Unsafe saved parent artifact path")
            identities[str(manifest.parent / p)] = sha
    return _parents(identities)


def freeze_program(directory, *, program_id, cycles, bounds):
    """Return a JSON-ready immutable whole-program plan without executing/writing.

    cycles contain cycle_id, parent_identities, criteria and all cases. An optional
    ``contract`` is validated by RSI-CYCLE-1 and frozen verbatim. All future cycles
    must already be listed: a new ID cannot replenish the aggregate budget.
    """
    _name(program_id, "program_id")
    if not isinstance(bounds, dict) or set(bounds) != {"max_launches", "max_financial_slots", "wall_seconds"}:
        raise RSIError("Expected explicit aggregate launch, financial-slot and wall bounds")
    _positive(bounds["max_launches"], "max_launches", integer=True)
    _positive(bounds["max_financial_slots"], "max_financial_slots", zero=True, integer=True)
    _positive(bounds["wall_seconds"], "wall_seconds")
    if not isinstance(cycles, list) or not cycles:
        raise RSIError("Register every cycle and case before the first launch")
    execution_root = Path(directory).resolve()
    frozen_cycles, seen = [], set()
    for raw in cycles:
        if not isinstance(raw, dict) or set(raw) not in ({"cycle_id", "parent_identities", "criteria", "cases"}, {"cycle_id", "parent_identities", "criteria", "cases", "contract"}):
            raise RSIError("Expected immutable cycle identity, parents, criteria and cases")
        cycle = json.loads(canonical(raw))
        cid = _name(cycle["cycle_id"], "cycle_id")
        if cid in seen or not isinstance(cycle["criteria"], dict) or not cycle["criteria"] or not isinstance(cycle["cases"], list) or not cycle["cases"]:
            raise RSIError("Duplicate cycle or missing frozen criteria/cases")
        seen.add(cid)
        cycle["parent_identities"] = _parents(cycle["parent_identities"])
        if "contract" in cycle:
            from research.control.rsi_contracts import validate_cycle, verify_artifacts
            contract = validate_cycle(cycle["contract"])
            if contract["program_id"] != program_id or contract["cycle_id"] != cid or contract["criteria"] != cycle["criteria"]:
                raise RSIError("Cycle contract identity/criteria differ from program")
            if len(cycle["cases"]) > contract["budget"]["max_attempts"] or bounds["wall_seconds"] > contract["budget"]["wall_seconds"]:
                raise RSIError("Registered cases/program wall bound exceed cycle contract budget")
            verified = verify_artifacts(contract["artifacts"], ROOT)
            cycle["parent_identities"].update({str(ROOT / entry["path"]): entry["sha256"] for entry in verified})
            cycle["contract"] = contract
        frozen_cases, names = [], set()
        for request in cycle["cases"]:
            case = _case_request(request)
            if case["case_id"] in names:
                raise RSIError("Duplicate case ID")
            names.add(case["case_id"])
            case["financial_slots"] = 0  # Registered adapter fact, never caller supplied.
            case["argv"] = _argv(case, execution_root / "cases" / cid / case["case_id"] / "artifacts")
            case["adapter_source_sha256"] = hashlib.sha256(FIXTURE_SOURCE.encode()).hexdigest() if case["adapter"] == "synthetic_fixture" else digest(ROOT / "scripts/current/rsi_foundation.py")
            frozen_cases.append(case)
        cycle["cases"] = frozen_cases
        frozen_cycles.append(cycle)
    preflight = any(c["adapter"] == "saved_c001_preflight" for cy in frozen_cycles for c in cy["cases"])
    return {"schema_version": 1, "mode": "offline", "program_id": program_id,
            "directory": str(execution_root), "repository": str(ROOT), "adapter_version": ADAPTER_VERSION,
            "bounds": json.loads(canonical(bounds)), "cycles": frozen_cycles,
            "code_hashes": {str(p.relative_to(ROOT)): digest(p) for p in _code_paths()},
            "interpreter": {"path": sys.executable, "sha256": digest(Path(sys.executable).resolve()), "version": sys.version},
            "saved_preflight_inputs": _saved_preflight_inputs() if preflight else {}}


def _validate_spec(spec, directory):
    if not isinstance(spec, dict) or set(spec) != {"schema_version", "mode", "program_id", "directory", "repository", "adapter_version", "bounds", "cycles", "code_hashes", "interpreter", "saved_preflight_inputs"}:
        raise RSIError("Invalid frozen program schema")
    requests = []
    for cy in spec["cycles"]:
        request = {k: copy.deepcopy(v) for k, v in cy.items() if k != "cases"}
        request["cases"] = [{k: copy.deepcopy(c[k]) for k in ("case_id", "adapter", "parameters", "timeout_seconds")} for c in cy["cases"]]
        requests.append(request)
    expected = freeze_program(directory, program_id=spec["program_id"], cycles=requests, bounds=spec["bounds"])
    if expected != spec:
        raise RSIError("Frozen program, exact command, code, interpreter or input identity changed")
    return json.loads(canonical(spec))


def _atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".rsi-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _bytes(value):
    return value if isinstance(value, bytes) else (value or "").encode()


class RSIProgram:
    """One writer, immutable program, finite attempts, verified idempotent resume."""

    def __init__(self, directory, *, spec):
        self.directory = Path(directory).resolve()
        self.spec = _validate_spec(spec, self.directory)
        self.program_hash = _hash(self.spec)
        self._cases = {(cy["cycle_id"], c["case_id"]): (cy, c) for cy in self.spec["cycles"] for c in cy["cases"]}
        for path in (self.directory / "controller", self.directory / "controller/events.jsonl",
                     self.directory / "controller/snapshot.json", self.directory / "controller/.writer.lock",
                     self.directory / "cases"):
            if path.is_symlink():
                raise RSIError("Symlink cannot own coordinator state")
        controller_preexisted = (self.directory / "controller/events.jsonl").exists()
        try:
            self._controller = ResearchController(self.directory / "controller", context={
                "score_version": ADAPTER_VERSION, "program_id": self.spec["program_id"], "program_sha256": self.program_hash},
                budget={"max_attempts": self.spec["bounds"]["max_launches"],
                        "max_resource_units": self.spec["bounds"]["max_launches"], "resource_unit": "launch_reservations",
                        "max_active_branches": len(self._cases)}, child_limit=max(1, len(self._cases)))
        except WriterBusy:
            raise
        except ControllerError as exc:
            raise RSIError("Frozen program context/budget changed or controller evidence invalid: " + str(exc)) from exc
        self._seal_controller()
        self.log_path = self.directory / "execution.jsonl"
        self.snapshot_path = self.directory / "execution-state.json"
        self._closed = False
        try:
            self._load()
            if not self._events:
                if controller_preexisted or self._controller.state["attempts"] or self._controller.state["questions"]:
                    raise RSIError("Missing execution authority for existing program; reconcile before resume")
                now = time.time()
                self._append("init", {"program_sha256": self.program_hash, "started_epoch": now,
                                      "deadline_epoch": now + self.spec["bounds"]["wall_seconds"]})
            self._opened_monotonic = time.monotonic()
            self._opening_remaining = max(0, self._state["deadline_epoch"] - time.time())
            if time.time() < self._state["last_epoch"]:
                raise RSIError("Wall clock moved backward; reconcile clock before resume")
            for cy, case in self._cases.values():
                key = self._key(cy["cycle_id"], case["case_id"])
                self._controller_call("register_question", "question:" + key, key, {"adapter": case["adapter"], "parameters": case["parameters"], "criteria": cy["criteria"], "parents": cy["parent_identities"]})
                self._controller_call("register_branch", "branch:" + key, branch_id=key, question_id=key, mechanism=case["adapter"])
            self._reconcile()
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _key(cycle_id, case_id):
        return cycle_id + "/" + case_id

    @property
    def state(self):
        return copy.deepcopy(self._state)

    @property
    def controller_state(self):
        return self._controller.state

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        if not self._closed:
            self._controller.close()
            self._closed = True

    def _open(self):
        if self._closed:
            raise RSIError("Program is closed")

    def _apply(self, old, event):
        state = copy.deepcopy(old)
        kind, p = event["kind"], event["payload"]
        if kind == "init":
            if state or p["program_sha256"] != self.program_hash:
                raise RSIError("Execution program identity changed")
            state = {**p, "attempts": {}, "stopped_reason": None}
        elif kind == "stop":
            state["stopped_reason"] = p["reason"]
        elif kind == "reserved":
            if p["key"] in state["attempts"] or p["key"] not in {self._key(*k) for k in self._cases}:
                raise RSIError("Invalid duplicate execution reservation")
            state["attempts"][p["key"]] = {**p, "status": "reserved"}
        elif kind in {"logical_reserved", "launch_intent", "launched", "captured", "finalized", "controller_recorded"}:
            attempt = state["attempts"][p["key"]]
            allowed = {"logical_reserved": {"reserved"}, "launch_intent": {"logical_reserved"},
                       "launched": {"launch_intent"}, "captured": {"launch_intent", "launched"},
                       "finalized": {"reserved", "logical_reserved", "launch_intent", "launched", "captured"},
                       "controller_recorded": TERMINAL}
            if attempt["status"] not in allowed[kind]:
                raise RSIError("Invalid execution transition")
            attempt.update(p)
            if kind == "finalized":
                if p["status"] not in TERMINAL:
                    raise RSIError("Invalid terminal execution status")
                # A stop is inseparable from the outcome; a crash cannot lose it
                # between a terminal result and a separate stop-log append.
                if p["status"] in {"integrity_failed", "interrupted_after_launch", "ambiguous"}:
                    state["stopped_reason"] = ("Ambiguous interrupted launch; manual process reconciliation required" if p["status"] == "ambiguous" else p["status"] + ": " + p.get("reason", ""))
            elif kind != "controller_recorded":
                attempt["status"] = kind
        else:
            raise RSIError("Unknown execution event")
        state["last_epoch"] = event["epoch"]
        return state

    def _load(self):
        self._state, self._events, prefixes = {}, [], []
        head = "0" * 64
        if self.log_path.is_symlink() or self.snapshot_path.is_symlink():
            raise RSIError("Symlink cannot own execution evidence")
        if self.log_path.exists():
            raw = self.log_path.read_bytes()
            if raw and not raw.endswith(b"\n"):
                raise RSIError("Partial execution log; manual reconciliation required")
            try:
                for line in raw.splitlines():
                    record = json.loads(line)
                    body = {k: record[k] for k in ("sequence", "previous_hash", "event")}
                    if set(record) != {*body, "event_hash"} or body["sequence"] != len(self._events) + 1 or body["previous_hash"] != head or record["event_hash"] != _hash(body):
                        raise RSIError("Broken execution hash chain")
                    if self._events and record["event"]["epoch"] < self._state["last_epoch"]:
                        raise RSIError("Execution time moved backwards")
                    self._state = self._apply(self._state, record["event"])
                    self._events.append(record); head = record["event_hash"]; prefixes.append(_hash(self._state))
            except (KeyError, TypeError, json.JSONDecodeError) as exc:
                raise RSIError("Invalid execution log") from exc
        if self.snapshot_path.exists():
            try:
                saved = json.loads(self.snapshot_path.read_text()); seq = saved["sequence"]
                if type(seq) is not int or not 1 <= seq <= len(self._events) or set(saved) != {"sequence", "head_hash", "state"} or saved["head_hash"] != self._events[seq - 1]["event_hash"] or _hash(saved["state"]) != prefixes[seq - 1]:
                    raise RSIError("Execution snapshot differs from authoritative log")
            except (KeyError, TypeError, json.JSONDecodeError) as exc:
                raise RSIError("Invalid execution snapshot") from exc
        if self._events:
            self._snapshot()

    def _snapshot(self):
        _atomic(self.snapshot_path, (canonical({"sequence": len(self._events), "head_hash": self._events[-1]["event_hash"], "state": self._state}) + "\n").encode())

    def _append(self, kind, payload):
        self._open()
        if self._events:
            self._assert_execution_durable()
        event = {"kind": kind, "payload": payload, "epoch": time.time(), "utc": datetime.now(timezone.utc).isoformat()}
        state = self._apply(self._state, event)
        body = {"sequence": len(self._events) + 1, "previous_hash": self._events[-1]["event_hash"] if self._events else "0" * 64, "event": event}
        record = {**body, "event_hash": _hash(body)}
        try:
            with self.log_path.open("ab") as stream:
                stream.write((canonical(record) + "\n").encode()); stream.flush(); os.fsync(stream.fileno())
            self._state = state; self._events.append(record); self._snapshot()
        except OSError:
            self.close()
            raise

    def usage(self):
        self._open()
        attempts = list(self._state["attempts"].values())
        return {"launch_reservations": len(attempts), "launches_observed": sum("pid" in a for a in attempts),
                "financial_slots_reserved": sum(a["financial_slots"] for a in attempts),
                "financial_execution_supported": False, "deadline_epoch": self._state["deadline_epoch"],
                "remaining_seconds": self._remaining()}

    def _remaining(self):
        return max(0, min(self._state["deadline_epoch"] - time.time(), self._opening_remaining - (time.monotonic() - self._opened_monotonic)))

    def _action(self, cy, case):
        key = self._key(cy["cycle_id"], case["case_id"])
        return {"id": key, "branch_id": key, "question_id": key, "context_id": self._controller.context_id,
                "observation_key": key, "observation_spec": {"adapter": case["adapter"], "parameters": case["parameters"], "criteria": cy["criteria"], "parents": cy["parent_identities"]},
                "class": 3, "decision_value": 1, "shared_questions": [], "cost_upper_bound": 1,
                "evidence": ["frozen-program:sha256:" + self.program_hash],
                "witness": [{"observation": "artifact contract verified or rejected", "decision": "record this fixed offline check"}]}

    def _logical_reserve(self, key, cy, case):
        result = self._controller_call("select", "reserve:" + key, self._action(cy, case))
        if self._state["attempts"][key]["status"] == "reserved":
            self._append("logical_reserved", {"key": key, "attempt_id": result["attempt_id"]})

    def _folder(self, key):
        return self.directory / "cases" / key

    def _inventory(self, key):
        folder = self._folder(key)
        inventory = {}
        for path in (folder, *folder.parents):
            if path == self.directory:
                break
            if path.is_symlink():
                raise RSIError("Symlink output directory cannot authenticate evidence")
        if folder.exists():
            for path in sorted(folder.rglob("*")):
                if path.is_symlink() or (not path.is_file() and not path.is_dir()):
                    raise RSIError("Symlink or special output cannot authenticate evidence")
                if path.is_file():
                    inventory[str(path.relative_to(folder))] = digest(path)
        return inventory

    def _authenticate(self, attempt):
        if self._inventory(attempt["key"]) != attempt.get("artifact_hashes", {}):
            raise RSIError("Captured output/artifact missing, added or tampered")

    def _audit(self, key, case):
        folder = self._folder(key)
        if case["adapter"] == "synthetic_fixture":
            expected = {"synthetic_fixture": True, "passed": True, "payload": case["parameters"]["payload"]}
            result = folder / "artifacts/result.json"
            expected_bytes = (canonical(expected) + "\n").encode()
            if not result.is_file() or result.read_bytes() != expected_bytes:
                raise RSIError("Expected synthetic artifact is missing or contradicts frozen contract")
            if set(self._inventory(key)) != {"stdout.txt", "stderr.txt", "artifacts/result.json", "artifacts/partial.txt"}:
                raise RSIError("Unexpected synthetic output set")
        elif (folder / "stdout.txt").read_text().strip() != "Preflight passed; zero financial attempts":
            raise RSIError("Saved runner did not attest the exact read-only preflight result")
        return {"passed": True, "adapter": case["adapter"], "financial_execution_verified": False,
                "scope": "synthetic fixture integrity" if case["adapter"] == "synthetic_fixture" else "existing runner read-only preflight"}

    def _record_controller(self, key):
        attempt = self._state["attempts"][key]
        if attempt.get("controller_recorded"):
            return
        self._authenticate(attempt)
        cy, case = self._cases[tuple(key.split("/"))]
        passed = attempt["status"] == "completed"
        if passed:
            self._verify_frozen()
            self._audit(key, case)
        evidence = [str(self._folder(key) / p) + "#sha256=" + h for p, h in attempt.get("artifact_hashes", {}).items()]
        if not evidence:
            evidence = ["execution-log:" + str(self.log_path) + "#" + key]
        resolution = [{"question_id": key, "decision": "verified-offline-check", "finding": attempt["audit"]["scope"], "evidence": evidence}] if passed else []
        self._controller_call("record", "outcome:" + key, attempt["attempt_id"], {
            "status": "completed" if passed else "failed", "summary": attempt["status"] + ": " + attempt.get("reason", "registered output contract verified"),
            "evidence": evidence, "inspection_trace": ["Authenticated sealed output hashes", "Applied registered adapter output contract"],
            "actual_resource_units": 1, "observation_kind": "synthetic_fixture" if case["adapter"] == "synthetic_fixture" else "read_only_analysis", "resolutions": resolution})
        self._append("controller_recorded", {"key": key, "controller_recorded": True})

    def _finalize_captured(self, key, case):
        attempt = self._state["attempts"][key]
        self._authenticate(attempt)
        status, reason, audit = attempt["process_status"], attempt.get("process_reason", ""), None
        if status == "exited" and attempt["returncode"] == 0:
            try:
                self._verify_frozen()
                audit = self._audit(key, case); status = "completed"
            except (OSError, ValueError) as exc:
                status, reason = "integrity_failed", str(exc)
        elif status == "exited":
            status, reason = "failed", f"Child exit {attempt['returncode']}"
        self._append("finalized", {"key": key, "status": status, "reason": reason, "audit": audit})
        self._record_controller(key)

    def _reconcile(self):
        for key in list(self._state["attempts"]):
            attempt = self._state["attempts"][key]
            cy, case = self._cases[tuple(key.split("/"))]
            if attempt["status"] in {"reserved", "logical_reserved"}:
                self._logical_reserve(key, cy, case)
                # Durable protocol proves Popen cannot have been reached yet.
                self._append("finalized", {"key": key, "status": "interrupted_before_launch", "reason": "Reservation survived without launch intent; consumed, no retry", "artifact_hashes": self._inventory(key)})
            elif attempt["status"] in {"launch_intent", "launched"}:
                self._append("finalized", {"key": key, "status": "ambiguous", "reason": "Launch intent survived without sealed exit/output; manual process reconciliation required", "artifact_hashes": self._inventory(key)})
            elif attempt["status"] == "captured":
                self._finalize_captured(key, case)
            self._authenticate(self._state["attempts"][key])
            if self._state["attempts"][key]["status"] == "completed":
                self._audit(key, case)
            self._record_controller(key)
        logical_ids = {a.get("attempt_id") for a in self._state["attempts"].values()}
        if set(self._controller.state["attempts"]) != logical_ids:
            raise RSIError("Logical and execution reservations disagree; manual reconciliation required")

    def _run_process(self, key, argv, timeout):
        self._verify_frozen()
        timeout = min(timeout, self._remaining())
        if timeout <= 0:
            raise _LaunchDeadline("Aggregate deadline expired during reservation; no child launched")
        environment = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
        child = subprocess.Popen(argv, cwd=ROOT, env=environment, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        try:
            self._append("launched", {"key": key, "pid": child.pid})
            stdout, stderr = child.communicate(timeout=min(timeout, self._remaining()))
        except BaseException as exc:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = child.communicate()
            if isinstance(exc, subprocess.TimeoutExpired):
                exc.output, exc.stderr = stdout, stderr
            else:
                exc.rsi_stdout, exc.rsi_stderr = stdout, stderr
            exc.rsi_pid = child.pid
            raise
        return subprocess.CompletedProcess(argv, child.returncode, stdout, stderr)

    def _verify_frozen(self):
        self._assert_execution_durable()
        self._assert_controller_durable()
        if _hash(self.spec) != self.program_hash:
            raise RSIError("Program changed after immutable registration")
        _validate_spec(self.spec, self.directory)

    def _seal_controller(self):
        self._controller_seal = {str(p): p.read_bytes() for p in (self._controller.log_path, self._controller.snapshot_path)}

    def _assert_controller_durable(self):
        for name, expected in self._controller_seal.items():
            path = Path(name)
            if not path.is_file() or path.is_symlink() or path.read_bytes() != expected:
                raise RSIError("Controller journal changed while writer is open")

    def _controller_call(self, method, *args, **kwargs):
        self._assert_controller_durable()
        result = getattr(self._controller, method)(*args, **kwargs)
        self._seal_controller()
        return result

    def _assert_execution_durable(self):
        expected_log = b"".join((canonical(r) + "\n").encode() for r in self._events)
        expected_snapshot = (canonical({"sequence": len(self._events), "head_hash": self._events[-1]["event_hash"], "state": self._state}) + "\n").encode()
        for path, expected in ((self.log_path, expected_log), (self.snapshot_path, expected_snapshot)):
            if not path.is_file() or path.is_symlink() or path.read_bytes() != expected:
                raise RSIError("Execution journal changed while writer is open")

    def execute(self, cycle_id, case_id):
        """Execute once or return authenticated cached evidence; never retry a case."""
        self._open()
        self._verify_frozen()
        if (cycle_id, case_id) not in self._cases:
            raise RSIError("Case was not registered in immutable program")
        cy, case = self._cases[(cycle_id, case_id)]
        key = self._key(cycle_id, case_id)
        if key in self._state["attempts"]:
            attempt = self._state["attempts"][key]
            if attempt["status"] not in TERMINAL:
                raise RSIError("Outstanding execution requires reopening/reconciliation")
            self._authenticate(attempt)
            if attempt["status"] == "completed":
                self._audit(key, case)
            return {**copy.deepcopy(attempt), "cached": True, "program_sha256": self.program_hash,
                    "code_hashes": copy.deepcopy(self.spec["code_hashes"]), "interpreter": self.spec["interpreter"]}
        if self._state["stopped_reason"]:
            raise RSIError(self._state["stopped_reason"])
        if len(self._state["attempts"]) >= self.spec["bounds"]["max_launches"]:
            raise RSIError("Aggregate launch reservation budget exhausted, failures included")
        if self.usage()["financial_slots_reserved"] + case["financial_slots"] > self.spec["bounds"]["max_financial_slots"]:
            raise RSIError("Aggregate financial-slot budget exhausted")
        if self._remaining() <= 0:
            raise RSIError("Aggregate program deadline exhausted")
        self._inventory(key)  # Reject a symlink ancestor even before output exists.
        if self._folder(key).exists():
            raise RSIError("Orphan output exists without execution reservation; manual reconciliation required")
        # Controller preflight prevents a semantic duplicate from consuming a new slot.
        if self._controller.preview([self._action(cy, case)])["selected"] is None:
            raise RSIError("Logical controller rejected duplicate/resolved/ineligible observation")
        self._append("reserved", {"key": key, "cycle_id": cycle_id, "case_id": case_id,
                                  "financial_slots": case["financial_slots"], "argv": case["argv"],
                                  "adapter": case["adapter"], "adapter_source_sha256": case["adapter_source_sha256"]})
        self._logical_reserve(key, cy, case)
        self._folder(key).mkdir(parents=True, exist_ok=False)
        self._append("launch_intent", {"key": key})
        interrupted = None
        try:
            child = self._run_process(key, case["argv"], min(self._remaining(), case["timeout_seconds"]))
            stdout, stderr, returncode, status, reason = child.stdout, child.stderr, child.returncode, "exited", ""
        except _LaunchDeadline as exc:
            stdout, stderr, returncode, status, reason = b"", b"", None, "interrupted_before_launch", str(exc)
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, returncode, status, reason = exc.output, exc.stderr, None, "timed_out", "Child exceeded remaining aggregate/per-case deadline"
        except (KeyboardInterrupt, SystemExit) as exc:
            stdout, stderr = getattr(exc, "rsi_stdout", b""), getattr(exc, "rsi_stderr", b"")
            returncode, status, reason, interrupted = None, "interrupted_after_launch", "Caller interrupted after launch intent; process group termination attempted", exc
        except OSError as exc:
            stdout, stderr = getattr(exc, "rsi_stdout", b""), getattr(exc, "rsi_stderr", str(exc).encode())
            if hasattr(exc, "rsi_pid"):
                returncode, status, reason, interrupted = None, "interrupted_after_launch", f"Post-launch journaling/process error: {type(exc).__name__}", exc
            else:
                returncode, status, reason = None, "failed", f"Process launch failed: {type(exc).__name__}"
        except BaseException as exc:
            stdout, stderr = getattr(exc, "rsi_stdout", b""), getattr(exc, "rsi_stderr", b"")
            returncode, status, reason, interrupted = None, "interrupted_after_launch", f"Unexpected interruption: {type(exc).__name__}", exc
        _atomic(self._folder(key) / "stdout.txt", _bytes(stdout))
        _atomic(self._folder(key) / "stderr.txt", _bytes(stderr))
        # Partial artifacts and both streams are sealed before any adapter audit.
        self._append("captured", {"key": key, "returncode": returncode, "process_status": status,
                                  "process_reason": reason, "artifact_hashes": self._inventory(key),
                                  **({"pid": interrupted.rsi_pid} if interrupted is not None and hasattr(interrupted, "rsi_pid") else {})})
        self._finalize_captured(key, case)
        if interrupted is not None:
            raise interrupted
        return self.execute(cycle_id, case_id) | {"cached": False}
