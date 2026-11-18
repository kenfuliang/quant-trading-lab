"""Truncate-and-compare lookahead check.

A causal strategy's decisions at session t depend only on data up to t. For each cutoff
session c the strategy is built (``target_fn_factory(data)``) and run on the data truncated
at c and on the full data. The factory receives the data of the run it serves, so features
precomputed from that data (a forward-looking indicator, a full-sample normalisation) are
rebuilt per run and a leak shows up as a difference.

Compared, with exact equality (NaN equals NaN):

* signals and positions for sessions strictly before c, from the two ``run_screen`` runs;
* the decision at c itself. ``run_screen`` makes no decision on its last session (nothing
  could fill), so the truncated run records none there; to catch one-step-ahead leaks the
  target fn is called directly at c with ``history_view`` of the truncated and of the full
  data, with the same holdings and equity (taken from the truncated run's close of c), and
  the returned targets and signals are compared (table ``decision``).

If a run or call raises, the cutoff is recorded as a difference with table ``error``
(``first_date`` is the cutoff, ``count`` 1, ``error`` the exception text) and the status is
"fail".

``truncate`` drops dividends whose pay date is after ``last``. A dividend with
``ex_date <= last < pay_date`` is therefore dropped as well (this also keeps ``validate``
satisfied); that removes a pending credit, so only cash after ``last`` could differ and
the comparison stops before that.
"""
from __future__ import annotations

from typing import Callable

import pandas as pd

from research.evaluation.market_model import MarketConfig, MarketData, TargetFn, history_view
from research.evaluation.screening_engine import run_screen

__all__ = ["check_lookahead", "truncate"]


def truncate(data: MarketData, last: str) -> MarketData:
    """Sessions up to ``last``; dividends paid and splits effective on or before ``last``."""
    if last not in data.sessions:
        raise ValueError(f"{last} is not a session")
    keep = data.sessions.index(last) + 1
    return MarketData(
        sessions=data.sessions[:keep],
        bars={name: frame.iloc[:keep].copy() for name, frame in data.bars.items()},
        dividends=tuple(d for d in data.dividends if d.pay_date <= last),
        splits=tuple(s for s in data.splits if s.effective_date <= last),
    )


def _cutoff_sessions(sessions: tuple[str, ...], count: int) -> list[str]:
    """Evenly spaced sessions, excluding the first and the last."""
    inner = list(range(1, len(sessions) - 1))
    if count < 1 or not inner:
        raise ValueError("need cutoffs >= 1 and at least three sessions")
    count = min(count, len(inner))
    picks = sorted({inner[(2 * k + 1) * len(inner) // (2 * count)] for k in range(count)})
    return [sessions[i] for i in picks]


def _difference(truncated: pd.DataFrame, full: pd.DataFrame, keys: list[str], value: str,
                cutoff: str, table: str) -> dict | None:
    a = truncated[truncated["date"] < cutoff][keys + [value]]
    b = full[full["date"] < cutoff][keys + [value]]
    merged = a.merge(b, on=keys, how="outer", suffixes=("_trunc", "_full"), indicator=True)
    left, right = merged[f"{value}_trunc"], merged[f"{value}_full"]
    bad = (merged["_merge"] != "both") | ~((left == right) | (left.isna() & right.isna()))
    if not bad.any():
        return None
    return {"cutoff": cutoff, "table": table, "first_date": str(merged.loc[bad, "date"].min()),
            "count": int(bad.sum())}


def _decision_difference(short: MarketData, full: MarketData, short_fn, full_fn, result, cutoff: str) -> dict | None:
    i = short.sessions.index(cutoff)
    held = result.positions[result.positions["date"] == cutoff].set_index("instrument")["quantity"]
    holdings = {name: int(held.get(name, 0)) for name in sorted(short.bars)}
    equity = float(result.cash.loc[cutoff]) + sum(
        q * float(short.bars[name]["close"].iloc[i]) for name, q in holdings.items())
    a = short_fn(cutoff, history_view(short, i), dict(holdings), equity)
    b = full_fn(cutoff, history_view(full, i), dict(holdings), equity)
    count = 0
    for left, right in ((a.signals, b.signals), (a.targets, b.targets)):
        for key in set(left) | set(right):
            x, y = left.get(key), right.get(key)
            if not (x == y or (x != x and y != y)):  # NaN-aware exact equality
                count += 1
    return {"cutoff": cutoff, "table": "decision", "first_date": cutoff, "count": count} if count else None


def check_lookahead(data: MarketData, target_fn_factory: Callable[[MarketData], TargetFn], market: MarketConfig,
                    cutoffs: int = 5) -> dict:
    """Run truncated vs full for evenly spaced cutoffs; report per-table differences."""
    chosen = _cutoff_sessions(data.sessions, cutoffs)
    differences = []
    for cutoff in chosen:
        try:
            short_data = truncate(data, cutoff)
            short_fn, full_fn = target_fn_factory(short_data), target_fn_factory(data)
            short = run_screen(short_data, target_fn_factory(short_data), market)
            full = run_screen(data, target_fn_factory(data), market)
            for table, keys, value in (("signals", ["date", "instrument", "stage"], "value"),
                                       ("positions", ["date", "instrument"], "quantity")):
                diff = _difference(getattr(short, table), getattr(full, table), keys, value, cutoff, table)
                if diff:
                    differences.append(diff)
            diff = _decision_difference(short_data, data, short_fn, full_fn, short, cutoff)
            if diff:
                differences.append(diff)
        except Exception as exc:  # a leaking fn may index past the truncated end
            differences.append({"cutoff": cutoff, "table": "error", "first_date": cutoff, "count": 1,
                                "error": f"{type(exc).__name__}: {exc}"})
    return {"status": "fail" if differences else "pass", "cutoffs": chosen, "differences": differences}
