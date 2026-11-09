"""Pure pre-submit risk gate for the bounded long-only paper session.

Broker-agnostic and offline: no I/O, no clock. The caller supplies the current
state, and acts on `trip` by engaging the kill switch. Limits are the pilot's
bounded test policy, configurable per run, not an approved investment risk budget.
Daily loss counts realized profit and loss only; unrealized loss needs a mark and
is not covered here.
"""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RiskLimits:
    max_notional: Decimal = Decimal("1000")
    max_position_qty: Decimal = Decimal(1)
    max_orders: int = 2
    max_daily_loss: Decimal = Decimal("25")


@dataclass(frozen=True)
class GateState:
    submissions: int
    position: Decimal
    realized_pnl: Decimal
    halted: bool


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reasons: tuple = ()
    trip: bool = False  # caller should engage the kill switch


def check(limits, side, qty, price, state):
    qty, price = Decimal(qty), Decimal(price)
    reasons = []
    trip = False
    if state.halted:
        reasons.append("halt_engaged")
    if state.realized_pnl <= -limits.max_daily_loss:
        reasons.append("daily_loss_limit")
        trip = True
    if state.submissions >= limits.max_orders:
        reasons.append("order_count_limit")
    if side not in ("buy", "sell") or qty <= 0 or not price.is_finite() or price <= 0:
        reasons.append("invalid_order")
    elif qty * price > limits.max_notional:
        reasons.append("notional_limit")
    else:
        after = state.position + (qty if side == "buy" else -qty)
        if not 0 <= after <= limits.max_position_qty:
            reasons.append("position_limit")
    return Decision(not reasons, tuple(reasons), trip)
