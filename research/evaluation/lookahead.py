"""Truncate-and-compare lookahead check.

A causal strategy's decisions at session t depend only on data up to t. For each cutoff
session c the strategy is run on the data truncated at c and on the full data; signals and
positions for sessions strictly before c must be identical (exact equality). The truncated
run's own last session is excluded because its orders cannot fill, so the comparison stops
one session earlier.

``truncate`` drops dividends whose pay date is after ``last``. A dividend with
``ex_date <= last < pay_date`` is therefore dropped as well (this also keeps ``validate``
satisfied); that removes a pending credit, so only cash after ``last`` could differ and
the comparison stops before that.
"""
from __future__ import annotations

from typing import Callable

import pandas as pd

from research.evaluation.market_model import MarketConfig, MarketData, TargetFn
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


def check_lookahead(data: MarketData, target_fn_factory: Callable[[], TargetFn], market: MarketConfig,
                    cutoffs: int = 5) -> dict:
    """Run truncated vs full for evenly spaced cutoffs; report per-table differences."""
    chosen = _cutoff_sessions(data.sessions, cutoffs)
    full = run_screen(data, target_fn_factory(), market)
    differences = []
    for cutoff in chosen:
        short = run_screen(truncate(data, cutoff), target_fn_factory(), market)
        for table, keys, value in (("signals", ["date", "instrument", "stage"], "value"),
                                   ("positions", ["date", "instrument"], "quantity")):
            diff = _difference(getattr(short, table), getattr(full, table), keys, value, cutoff, table)
            if diff:
                differences.append(diff)
    return {"status": "fail" if differences else "pass", "cutoffs": chosen, "differences": differences}
