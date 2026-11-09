"""Operator kill switch: a sentinel file read by, but not owned by, the trading process.

Broker-agnostic and offline. The switch is engaged by creating the sentinel (the
operator CLI does this from any shell, no running process needed). It fails closed:
a sentinel that cannot be read or parsed counts as engaged. Only an explicit
release with a named actor and a note removes it, and the release is journaled
before the sentinel is removed, so a crash in between leaves the switch engaged.
Engaging blocks all new orders, including exits; flattening an open position is a
manual broker action until a tested flatten procedure exists.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from .durable_journal import WriterLock, atomic_write_json

REPO = Path(__file__).resolve().parents[1]
DEFAULT_PATH = Path(os.environ.get("QTL_KILL_SWITCH") or REPO / ".local/kill-switch/HALT")


class KillSwitchError(RuntimeError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


class KillSwitch:
    def __init__(self, path=None):
        self.path = Path(path or DEFAULT_PATH)
        self.log_path = self.path.with_name(self.path.name + ".log.json")
        self.lock_path = self.path.with_name(self.path.name + ".lock")

    def status(self):
        """Return {'engaged': bool, ...}; any doubt about the sentinel means engaged."""
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError:
            return {"engaged": False}
        except OSError as error:
            return {"engaged": True, "reason": "unreadable_sentinel", "detail": str(error)}
        try:
            info = json.loads(raw)
            if not isinstance(info, dict):
                raise ValueError("sentinel is not an object")
        except ValueError as error:
            return {"engaged": True, "reason": "malformed_sentinel", "detail": str(error)}
        return {**info, "engaged": True}

    def engaged(self):
        return self.status()["engaged"]

    def engage(self, reason, actor="system"):
        """Idempotent. The sentinel is written first so the halt holds even if logging fails."""
        if self.status()["engaged"]:
            return self.status()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        info = {"reason": str(reason), "actor": str(actor), "engaged_at": _now()}
        atomic_write_json(self.path, info)
        self._append({"event": "engage", **info})
        return self.status()

    def release(self, actor, note):
        """Journal the release, then remove the sentinel. Requires a named actor and a note."""
        if not str(actor).strip() or not str(note).strip():
            raise KillSwitchError("Release needs a named actor and a note.")
        if not self.path.exists():
            raise KillSwitchError("Kill switch is not engaged.")
        self._append({"event": "release", "actor": str(actor), "note": str(note), "at": _now()})
        self.path.unlink()

    def history(self):
        try:
            return json.loads(self.log_path.read_text())
        except FileNotFoundError:
            return []

    def _append(self, event):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with WriterLock(self.lock_path):
            try:
                events = self.history()
            except ValueError as error:
                raise KillSwitchError(f"Kill-switch log is unreadable: {error}") from None
            atomic_write_json(self.log_path, events + [event])
