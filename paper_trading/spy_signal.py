"""Pure SPY EMA50/200 target-position signal. No I/O, broker or engine imports.

Duplicates `ComparisonStrategy.on_bar`/`want_long` in
`research/studies/spy/spy_backtest.py` (reused by `BoundedSPY`), because
`paper_trading` cannot import `research`. `tests/test_spy_signal_parity.py` pins
the two against `run_engine` positions. Note: the executed strategy has no
separate volatility gate; this mirrors exactly what runs.
"""
from __future__ import annotations

FAST = 50
SLOW = 200


def _ema(closes, period):
    """Nautilus EMA: first value is the first price, alpha = 2 / (period + 1)."""
    alpha = 2.0 / (period + 1)
    value = None
    for close in closes:
        value = close if value is None else alpha * close + (1.0 - alpha) * value
    return value


def _clean(closes):
    # The engine feeds bars as Price with two decimals.
    return [round(float(c), 2) for c in closes]


def target_position(closes, fast=FAST, slow=SLOW):
    """Target for the next session open given completed closes: 1 long, 0 flat.

    Flat until the slow EMA is initialized (>= `slow` completed bars), matching
    the strategy's refusal to trade before warm-up.
    """
    if not 0 < fast < slow:
        raise ValueError("Need 0 < fast < slow.")
    closes = _clean(closes)
    if len(closes) < slow:
        return 0
    return int(_ema(closes, fast) > _ema(closes, slow))


def target_series(closes, fast=FAST, slow=SLOW):
    """Entry i is the target for the session after bar i (uses closes[:i+1])."""
    if not 0 < fast < slow:
        raise ValueError("Need 0 < fast < slow.")
    f_alpha, s_alpha = 2.0 / (fast + 1), 2.0 / (slow + 1)
    f = s = None
    result = []
    for i, close in enumerate(_clean(closes), 1):
        f = close if f is None else f_alpha * close + (1.0 - f_alpha) * f
        s = close if s is None else s_alpha * close + (1.0 - s_alpha) * s
        result.append(int(i >= slow and f > s))
    return result


def indicators(closes, fast=FAST, slow=SLOW):
    closes = _clean(closes)
    return {"fast_ema": _ema(closes, fast), "slow_ema": _ema(closes, slow), "bars": len(closes)}
