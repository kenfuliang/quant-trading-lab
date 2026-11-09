"""Restart recovery for the bounded native session journal.

Broker-agnostic and offline: the broker is any object with `by_client_id(id)` that
returns an order dict, raises `OrderNotFound` for a definitive absence, or raises
anything else for an unknown outcome. This reconciles the session journal only; it
does not restore the Nautilus cache or general positions, which stay unsupported.

Rules: an unknown outcome is never treated as absent; only an explicit `OrderNotFound`
on an entry that never got an acknowledgement resolves it as never sent. Anything
unresolved keeps the session disarmed. Slots used by never-sent orders stay counted
so the submission cap holds across restarts. Terminal entries are not re-queried,
so recovery is idempotent.
"""
from dataclasses import dataclass, field
from decimal import Decimal
import json
from pathlib import Path

from .durable_journal import atomic_write_json

TERMINAL = {"filled", "rejected", "canceled", "expired", "never_sent"}
OPEN_BROKER = {"new", "accepted", "pending_new", "partially_filled", "pending_cancel"}


class OrderNotFound(Exception):
    """The broker definitively has no order with this client id."""


class RecoveryError(RuntimeError):
    pass


@dataclass
class RecoveryReport:
    resolved: list = field(default_factory=list)
    unresolved: list = field(default_factory=list)
    submissions: int = 0
    position: Decimal = Decimal(0)
    journal: list = field(default_factory=list)

    @property
    def halt(self):
        return bool(self.unresolved)


def _load(path):
    try:
        journal = json.loads(Path(path).read_text())
    except FileNotFoundError:
        return []
    except ValueError as error:
        raise RecoveryError(f"Journal is unreadable: {error}") from None
    if not isinstance(journal, list) or any(
            not isinstance(e, dict) or "client_order_id" not in e or e.get("side") not in ("buy", "sell")
            for e in journal):
        raise RecoveryError("Journal has an unexpected shape; manual review required.")
    return journal


def _classify(entry, api):
    """Return (new_status, reason) or (None, reason) when the outcome stays unknown."""
    client = entry["client_order_id"]
    try:
        order = api.by_client_id(client)
    except OrderNotFound:
        if entry["status"] == "reserved":
            return "never_sent", "broker has no order and none was acknowledged"
        return None, "broker has no record of an acknowledged order"
    except Exception as error:
        return None, f"broker query failed: {type(error).__name__}"
    if not isinstance(order, dict) or order.get("client_order_id") != client \
            or order.get("symbol") != "SPY" or order.get("side") != entry["side"]:
        return None, "broker order identity mismatch"
    try:
        filled = Decimal(str(order.get("filled_qty", "0")))
    except Exception:
        return None, "unreadable fill quantity"
    status = order.get("status")
    if status == "filled":
        return ("filled", "broker reports a complete fill") if filled == 1 else (None, "terminal fill quantity mismatch")
    if status in ("rejected", "canceled", "expired"):
        return (status, "broker reports no fill") if filled == 0 else (None, "terminal state with fills")
    if status in OPEN_BROKER:
        return None, "order is still working or partially filled"
    return None, "unknown broker status"


def recover(journal_path, api):
    """Reconcile every nonterminal journal entry; rewrite the journal atomically."""
    journal = _load(journal_path)
    report = RecoveryReport(submissions=len(journal), journal=journal)
    changed = False
    for entry in journal:
        if entry.get("status") not in TERMINAL:
            status, reason = _classify(entry, api)
            if status is None:
                report.unresolved.append({"client_order_id": entry["client_order_id"], "reason": reason})
                continue
            entry["status"], entry["recovery"] = status, reason
            changed = True
            report.resolved.append({"client_order_id": entry["client_order_id"], "status": status})
        if entry["status"] == "filled":
            report.position += 1 if entry["side"] == "buy" else -1
    if changed:
        atomic_write_json(journal_path, journal)
    return report
