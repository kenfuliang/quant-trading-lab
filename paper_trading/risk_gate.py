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


@dataclass(frozen=True)
class PilotLimits:
    """Account-level limits recorded in docs/goals.md for the first real-money pilot.

    Separate from `RiskLimits`, which keeps the bounded one-share paper session tiny. These are the
    user's chosen limits, not an approved risk budget; there is deliberately no per-position cap.
    Percentages are fractions of the figures the caller supplies. Unlike `check`, equity includes
    unrealized loss, so the caller must supply a mark.
    """
    capital: Decimal = Decimal("15000")
    daily_loss: Decimal = Decimal("0.02")
    weekly_loss: Decimal = Decimal("0.05")
    drawdown_warn: Decimal = Decimal("0.20")
    drawdown_halt: Decimal = Decimal("0.30")
    allowed_symbols: frozenset = None  # None: no list configured; the caller must still screen instruments


@dataclass(frozen=True)
class PilotState:
    equity: Decimal
    peak_equity: Decimal
    day_start_equity: Decimal
    week_start_equity: Decimal
    cash: Decimal
    position: Decimal  # shares held in the order's symbol
    halted: bool


@dataclass(frozen=True)
class PilotDecision:
    allowed: bool
    reasons: tuple = ()
    warnings: tuple = ()
    trip: bool = False  # caller should engage the kill switch; release stays manual


def account_check(limits, state):
    """Account-level part of the pilot policy: (reasons, warnings, trip). Equity must include unrealized loss."""
    reasons, warnings, trip = [], [], False
    if state.halted:
        reasons.append("halt_engaged")
    bad = [name for name, value in (("equity", state.equity), ("peak_equity", state.peak_equity),
                                    ("day_start_equity", state.day_start_equity),
                                    ("week_start_equity", state.week_start_equity))
           if not value.is_finite() or value <= 0]
    if bad:
        reasons.extend(f"invalid_state_{name}" for name in bad)
        return reasons, warnings, True
    drawdown = 1 - state.equity / state.peak_equity
    if drawdown >= limits.drawdown_halt:
        reasons.append("drawdown_halt")
        trip = True
    elif drawdown >= limits.drawdown_warn:
        warnings.append("drawdown_warning")
    if state.day_start_equity - state.equity >= limits.daily_loss * limits.capital:
        reasons.append("daily_loss_limit")
        trip = True
    if state.week_start_equity - state.equity >= limits.weekly_loss * limits.capital:
        reasons.append("weekly_loss_limit")
        trip = True
    return reasons, warnings, trip


def check_pilot(limits, symbol, side, qty, price, state):
    qty, price = Decimal(qty), Decimal(price)
    reasons, warnings, trip = account_check(limits, state)
    if side not in ("buy", "sell") or qty <= 0 or not price.is_finite() or price <= 0:
        reasons.append("invalid_order")
    else:
        if limits.allowed_symbols is not None and symbol not in limits.allowed_symbols:
            reasons.append("symbol_not_allowed")
        if side == "buy" and qty * price > state.cash:
            reasons.append("exceeds_cash")  # no margin
        if side == "sell" and qty > state.position:
            reasons.append("would_short")
    return PilotDecision(not reasons, tuple(reasons), tuple(warnings), trip)
