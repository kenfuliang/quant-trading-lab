"""Shared per-session contract pieces for the screening and NautilusTrader engines.

Both engines import these so that target checking, the overspend rule, configuration
checks and the returns/positions tables are defined once. The session order itself is
documented in ``screening_engine``.
"""
from __future__ import annotations

import math
import numbers
from dataclasses import dataclass

import pandas as pd

from research.evaluation.market_model import Decision, MarketConfig
from research.evaluation.run_output import COLUMNS, DTYPES


class EngineError(RuntimeError):
    pass


@dataclass(frozen=True)
class EngineResult:
    engine: str
    returns: pd.DataFrame
    positions: pd.DataFrame
    signals: pd.DataFrame
    fills: pd.DataFrame
    cash: pd.Series


def check_config(config: MarketConfig) -> None:
    """``initial_cash > 0``, ``cost_bps >= 0``, ``commission_usd >= 0`` on the cent grid; all finite."""
    for field in ("initial_cash", "cost_bps", "commission_usd"):
        value = getattr(config, field)
        if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(value):
            raise EngineError(f"MarketConfig.{field} must be a finite number, got {value!r}")
    if config.initial_cash <= 0:
        raise EngineError(f"MarketConfig.initial_cash must be > 0, got {config.initial_cash}")
    if config.cost_bps < 0:
        raise EngineError(f"MarketConfig.cost_bps must be >= 0, got {config.cost_bps}")
    if config.commission_usd < 0:
        raise EngineError(f"MarketConfig.commission_usd must be >= 0, got {config.commission_usd}")
    cents = config.commission_usd * 100
    if abs(cents - round(cents)) > 1e-6:
        raise EngineError(f"MarketConfig.commission_usd must be on the cent grid, got {config.commission_usd}")


def checked_targets(decision: Decision, names) -> dict[str, int]:
    """Validated integer share targets. Rejects unknown instruments, negatives, bools,
    non-finite and non-integral values with ``EngineError``; never truncates."""
    known = set(names)
    out: dict[str, int] = {}
    for name, shares in decision.targets.items():
        if name not in known:
            raise EngineError(f"target for unknown instrument {name!r}")
        if isinstance(shares, bool) or not isinstance(shares, numbers.Real):
            raise EngineError(f"target for {name} must be an integer share count, got {shares!r}")
        if not math.isfinite(shares) or shares != math.floor(shares):
            raise EngineError(f"target for {name} must be an integer share count, got {shares!r}")
        if shares < 0:
            raise EngineError(f"negative target {shares} for {name}")
        out[name] = int(shares)
    return out


def check_buy(day: str, name: str, quantity: int, price: float, cash: float, commission: float) -> float:
    """Overspend rule: raise if the buy would leave cash below zero; return cash after it."""
    remaining = cash - (price * quantity + commission)
    if remaining < 0:
        raise EngineError(f"{day}: buy {quantity} {name} @ {price} overspends cash {cash:.2f}")
    return remaining


def mark(day: str, cash: float, qty: dict[str, int], closes: dict[str, float]) -> dict:
    """Close mark: equity = cash + sum(quantity x close)."""
    equity = cash + sum(q * closes[n] for n, q in qty.items())
    return {"date": day, "cash": cash, "qty": dict(qty), "closes": dict(closes), "equity": equity}


def table(name: str, rows: list) -> pd.DataFrame:
    """A run-output table with the ``run_output.DTYPES`` dtypes, also when empty."""
    return pd.DataFrame(rows, columns=list(COLUMNS[name])).astype(DTYPES[name])


def build_result(engine: str, marks: list[dict], fills: list[tuple], signals: list[tuple],
                 initial_cash: float) -> EngineResult:
    """Returns, positions and cash tables from per-session marks and fill rows.

    ``net_return = equity / previous equity - 1`` (previous equity is ``initial_cash`` on
    the first session), ``cost = session fill costs / previous equity``,
    ``gross_return = net_return + cost``; one position row per non-zero holding with
    ``weight = quantity x close / equity``.
    """
    session_cost: dict[str, float] = {}
    for day, *_rest, cost in fills:
        session_cost[day] = session_cost.get(day, 0.0) + cost
    returns, positions = [], []
    prev_equity = float(initial_cash)
    for m in marks:
        day, equity = m["date"], m["equity"]
        net = equity / prev_equity - 1
        cost_frac = session_cost.get(day, 0.0) / prev_equity
        returns.append((day, net + cost_frac, cost_frac, net, equity))
        for n in sorted(m["qty"]):
            q = m["qty"][n]
            if q != 0:
                positions.append((day, n, q, q * m["closes"][n] / equity))
        prev_equity = equity
    return EngineResult(
        engine=engine,
        returns=table("returns", returns),
        positions=table("positions", positions),
        signals=table("signals", signals),
        fills=table("fills", fills),
        cash=pd.Series([m["cash"] for m in marks], index=pd.Index([m["date"] for m in marks], name="date"),
                       name="cash", dtype=float),
    )
