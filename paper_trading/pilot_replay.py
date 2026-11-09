"""Offline replay of the SPY EMA50/200 position through the pilot account limits. No I/O, no broker.

Asks one question: on past data, how often would the recorded pilot limits (`PilotLimits`) have fired
if the strategy had kept trading? Close-to-close approximation: the position decided at close i-1
(`spy_signal.target_position`) earns session i's close-to-close return, with no cost, slippage or
dividends beyond what the supplied closes carry. It does not halt after a trip, so it counts how
often a limit is breached on the unhalted path, not what a halted account would have done afterwards.
Development history only; not evidence of an edge and not a forecast.
"""
from datetime import date
from decimal import Decimal

from paper_trading.risk_gate import PilotLimits, PilotState, account_check
from paper_trading.spy_signal import FAST, SLOW, target_position


def replay(closes, limits=PilotLimits(), start=None):
    """closes: {YYYY-MM-DD: close}. Returns per-limit event dates and the equity summary."""
    dates = sorted(closes)
    values = [float(closes[d]) for d in dates]
    first = max(SLOW, 1)
    if len(dates) <= first:
        raise ValueError("Need more than the slow-EMA warm-up of sessions.")
    equity = float(limits.capital)
    peak, week_key, week_start = equity, None, equity
    events = {"drawdown_warning": [], "drawdown_halt": [], "daily_loss_limit": [], "weekly_loss_limit": []}
    long_days, rows = 0, 0
    worst_dd = 0.0
    for i in range(first, len(dates)):
        day = dates[i]
        if start and day < start:
            continue
        position = target_position(values[:i])  # decided at the previous close
        long_days += position
        day_start = equity
        equity *= 1 + position * (values[i] / values[i - 1] - 1)
        iso = date.fromisoformat(day).isocalendar()[:2]
        if iso != week_key:
            week_key, week_start = iso, day_start
        peak = max(peak, equity)
        worst_dd = min(worst_dd, equity / peak - 1)
        state = PilotState(Decimal(repr(equity)), Decimal(repr(peak)), Decimal(repr(day_start)),
                           Decimal(repr(week_start)), Decimal(repr(equity)), Decimal(0), False)
        reasons, warnings, _ = account_check(limits, state)
        for name in (*reasons, *warnings):
            events[name].append(day)
        rows += 1
    return {"sessions": rows, "long_share": long_days / rows if rows else None,
            "final_equity": round(equity, 2), "max_drawdown": round(worst_dd, 4),
            "events": events, "counts": {k: len(v) for k, v in events.items()}}
