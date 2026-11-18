"""Performance metrics for ``run-output/v1`` tables.

Conventions (docs/conventions.md "Metrics"): fractions in data, 252 sessions a year,
Sharpe at a zero risk-free rate. ``max_drawdown`` is a positive magnitude (as the
experiment registry stores it) measured from the running peak that includes the
initial-capital baseline.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

__all__ = ["METRIC_KEYS", "summarize", "window"]

METRIC_KEYS = (
    "net_cagr",
    "max_drawdown",
    "sharpe",
    "calmar",
    "turnover",
    "longest_underwater_sessions",
    "longest_underwater_days",
)
SESSIONS_PER_YEAR = 252


def summarize(returns: pd.DataFrame, fills: pd.DataFrame, initial_cash: float) -> dict[str, float | int | None]:
    """Return exactly ``METRIC_KEYS`` for a run's ``returns`` and ``fills`` tables.

    - ``net_cagr``: ``(final equity / initial_cash) ** (252 / sessions) - 1`` (-1.0 if final equity <= 0).
    - ``max_drawdown``: largest ``1 - equity / running peak``; the peak starts at ``initial_cash``.
    - ``sharpe``: mean / std (ddof 1) of ``net_return`` times sqrt(252), zero risk-free rate;
      ``None`` when std is 0.
    - ``calmar``: ``net_cagr / max_drawdown``; ``None`` when max drawdown is 0.
    - ``turnover``: sum of ``|quantity * price|`` over fills / mean equity / years (sessions / 252).
    - ``longest_underwater_sessions``: longest run of consecutive sessions with equity below the
      prior (running, baseline-inclusive) peak.
    - ``longest_underwater_days``: calendar days of the longest underwater episode, from the date
      of the peak before it to the date equity regains that peak (the last date if never
      regained). A peak that is the initial-capital baseline is dated at the first session.
    """
    if len(returns) == 0:
        raise ValueError("returns is empty")
    if not initial_cash > 0:
        raise ValueError("initial_cash must be positive")
    equity = returns["equity"].to_numpy(dtype=float)
    dates = pd.to_datetime(returns["date"]).reset_index(drop=True)
    n = len(equity)
    years = n / SESSIONS_PER_YEAR

    final = float(equity[-1])
    cagr = (final / initial_cash) ** (1 / years) - 1 if final > 0 else -1.0

    peak = np.maximum.accumulate(np.concatenate(([initial_cash], equity)))[1:]
    max_dd = float(max(0.0, np.max(1.0 - equity / peak)))

    net = returns["net_return"].to_numpy(dtype=float)
    std = float(np.std(net, ddof=1)) if n > 1 else 0.0
    sharpe = float(np.mean(net) / std * math.sqrt(SESSIONS_PER_YEAR)) if std > 0 else None
    calmar = cagr / max_dd if max_dd > 0 else None

    traded = float((fills["quantity"].astype(float) * fills["price"].astype(float)).abs().sum()) if len(fills) else 0.0
    turnover = traded / float(np.mean(equity)) / years

    sessions, days = _longest_underwater(equity, peak, dates)
    return {
        "net_cagr": float(cagr),
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "calmar": None if calmar is None else float(calmar),
        "turnover": float(turnover),
        "longest_underwater_sessions": sessions,
        "longest_underwater_days": days,
    }


def _longest_underwater(equity, peak, dates: pd.Series) -> tuple[int, int]:
    best_sessions = best_days = 0
    start = None  # index of the first underwater session of the current run
    for i in range(len(equity)):
        if equity[i] < peak[i]:
            if start is None:
                start = i
            run = i - start + 1
            peak_date = dates.iloc[start - 1] if start > 0 else dates.iloc[0]
            span = (dates.iloc[i] - peak_date).days  # provisional: never regained so far
        else:
            if start is not None:
                run = i - start
                peak_date = dates.iloc[start - 1] if start > 0 else dates.iloc[0]
                span = (dates.iloc[i] - peak_date).days
                best_sessions, best_days = _better(best_sessions, best_days, run, span)
            start = None
            continue
        if i == len(equity) - 1:
            best_sessions, best_days = _better(best_sessions, best_days, run, span)
    return best_sessions, best_days


def _better(sessions: int, days: int, new_sessions: int, new_days: int) -> tuple[int, int]:
    if new_sessions > sessions or (new_sessions == sessions and new_days > days):
        return new_sessions, new_days
    return sessions, days


def window(returns: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """Slice ``returns`` to ``start <= date <= end`` and rebase equity.

    Equity is divided by the slice's first previous equity (``equity / (1 + net_return)`` of
    the first row), so the slice starts from 1.0; pass ``initial_cash=1.0`` to ``summarize``.
    Returns are unchanged. ``fills`` are not sliced here (filter them by date and rescale
    their prices yourself if you need windowed turnover).
    """
    dates = returns["date"]
    sliced = returns[(dates >= start) & (dates <= end)].reset_index(drop=True)
    if len(sliced) == 0:
        raise ValueError(f"no sessions between {start} and {end}")
    base = float(sliced["equity"].iloc[0]) / (1.0 + float(sliced["net_return"].iloc[0]))
    sliced = sliced.copy()
    sliced["equity"] = sliced["equity"].astype(float) / base
    return sliced
