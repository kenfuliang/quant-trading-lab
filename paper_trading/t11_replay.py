"""Prototype replay of the T11 policy over saved daily bars. Pure and offline: no I/O, no broker.

For every completed session d it recomputes the prototype's decision from data up to d only, then
simulates fills at the NEXT session's open with a cost per traded notional. This matches the timing
seen in the saved cloud paths (decide at one close, fill near the next open) but it is the repo's
UNQUALIFIED prototype: indicator parity with the original is unproven, the gate seed differs from the
original, drawdown is not fed to the gate, adjusted prices change share counts, and fills and costs are
assumptions. Use `parity()` against a saved export before trusting any number.
"""
from datetime import datetime
import math
from zoneinfo import ZoneInfo

import pandas as pd

from paper_trading.t11_pilot import SYMBOLS
from paper_trading.t11_preview import features
from research.policies.risk_gate import states

NY = ZoneInfo("America/New_York")
MIN_SESSIONS = 215


def parse_bars(payloads, allowed):
    """Return {symbol: {day: (open, high, low, close)}} from Alpaca bar pages; strict on shape."""
    out = {s: {} for s in allowed}
    for payload in payloads:
        if not isinstance(payload.get("bars"), dict):
            raise ValueError("Missing bars container.")
        for symbol, bars in payload["bars"].items():
            if symbol not in out:
                raise ValueError(f"Unexpected symbol {symbol}.")
            for bar in bars:
                local = datetime.fromisoformat(bar["t"].replace("Z", "+00:00")).astimezone(NY)
                if local.strftime("%H:%M:%S") != "00:00:00":
                    raise ValueError("Daily bar is not at midnight New York.")
                day = local.date().isoformat()
                o, h, l, c = (float(bar[k]) for k in ("o", "h", "l", "c"))
                if not all(math.isfinite(v) and v > 0 for v in (o, h, l, c)) or not l <= min(o, c) <= max(o, c) <= h:
                    raise ValueError("Invalid OHLC.")
                if day in out[symbol]:
                    raise ValueError("Duplicate bar.")
                out[symbol][day] = (o, h, l, c)
    return out


def gate_series(raw_spy):
    """Per-day gate (state, cap) for every raw SPY session; same calculation as t11_preview.gate_preview."""
    items = sorted(raw_spy.items())
    if len(items) < 500:
        raise ValueError("Need at least 500 raw sessions.")
    close = pd.Series([round(float(v), 2) for _, v in items], index=[d for d, _ in items])
    fast = close.ewm(span=50, adjust=False).mean()
    slow = close.ewm(span=200, adjust=False).mean()
    vol = close.pct_change().rolling(20).std(ddof=1) * math.sqrt(252)
    fast.iloc[:199] = float("nan")
    slow.iloc[:199] = float("nan")
    scored = states(pd.DataFrame({"fast": fast, "slow": slow, "vol": vol, "dd": 0.0}))
    return {d: (str(scored.iloc[i]["state"]), float(scored.iloc[i]["cap"])) for i, d in enumerate(close.index)}


def common_sessions(bars):
    days = None
    for symbol in SYMBOLS:
        have = set(bars[symbol])
        days = have if days is None else days & have
    return sorted(days)


def decisions(bars, raw_spy, policy, start_day):
    """{session: {state, cap, reason, weights}} for each completed session >= start_day."""
    sessions = common_sessions(bars)
    gate = gate_series(raw_spy)
    closes = {s: {d: bars[s][d][3] for d in sessions} for s in SYMBOLS}
    out = {}
    for k, day in enumerate(sessions):
        if day < start_day or k + 1 < MIN_SESSIONS or day not in gate:
            continue
        state, cap = gate[day]
        if cap != cap:  # NaN cap while the gate warms up
            continue
        result = policy(features(closes, sessions[:k + 1]), cap)
        out[day] = {"state": state, "cap": cap, "reason": result["reason"],
                    "weights": {s: w for s, w in result["gated_weights"].items() if w > 0}}
    return out


def simulate(decided, bars, capital=10000.0, deployment=0.9, cost_bp=25.0):
    """Hold the decided weights from the next open. Returns the profile dataset for the holdings page."""
    days = sorted(d for d in common_sessions(bars) if d >= min(decided))
    cash, shares, last = float(capital), {}, {}
    nav, expo, orders, decide_log, pos = [], [], {}, {}, {}
    pending = None
    for day in days:
        if pending is not None:
            weights, decided_on = pending
            equity_open = cash + sum(q * bars[s][day][0] for s, q in shares.items())
            target = {s: math.floor(equity_open * deployment * w / bars[s][day][0]) for s, w in weights.items()}
            trades = []
            for s in sorted(set(shares) | set(target)):
                delta = target.get(s, 0) - shares.get(s, 0)
                if delta:
                    trades.append((s, delta, bars[s][day][0]))
            for s, delta, price in sorted(trades, key=lambda t: t[1] > 0):  # sells first
                cash -= delta * price + abs(delta) * price * cost_bp / 10000.0
                shares[s] = shares.get(s, 0) + delta
                if shares[s] == 0:
                    del shares[s]
                last[s] = [round(price, 4), day]
                orders.setdefault(day, []).append([s, float(delta), round(price, 4), "replay:buy" if delta > 0 else "replay:reduce"])
            if trades:
                decide_log.setdefault(decided_on, []).extend(
                    [s, float(d), round(p, 4), "replay:buy" if d > 0 else "replay:reduce"] for s, d, p in trades)
                pos[day] = {s: [float(q), last[s][0], last[s][1]] for s, q in shares.items()}
            pending = None
        value = cash + sum(q * bars[s][day][3] for s, q in shares.items())
        nav.append(round(value, 4))
        expo.append(round(sum(q * bars[s][day][3] for s, q in shares.items()) / value, 6))
        if day in decided:
            pending = (decided[day]["weights"], day)
    return {"dates": days, "nav": nav, "expo": expo, "turn": [None] * len(days), "orders": orders,
            "decided": decide_log, "trades": {}, "pos": pos, "unmatched_orders": 0}


def parity(replay, reference):
    """Agreement with a saved reference dataset (same shape) over their overlapping sessions."""
    ref_idx = {d: k for k, d in enumerate(reference["dates"])}
    rep_idx = {d: k for k, d in enumerate(replay["dates"])}
    common = [d for d in replay["dates"] if d in ref_idx]

    def held(dataset, day):
        snap, latest = {}, None
        for d in sorted(dataset["pos"]):
            if d <= day:
                latest = d
        if latest:
            snap = dataset["pos"][latest]
        return {s for s, v in snap.items() if abs(v[0]) > 1e-9}

    same = sum(1 for d in common if held(replay, d) == held(reference, d))
    overlap_nonempty = [d for d in common if held(reference, d)]
    sym_same = sum(1 for d in overlap_nonempty if held(replay, d) == held(reference, d))
    rets = lambda ds, nav, idx: [(d, nav[idx[d]] / nav[idx[d] - 1] - 1) for d in common if idx[d] > 0]
    a = pd.Series(dict(rets(replay, replay["nav"], rep_idx)))
    b = pd.Series(dict(rets(reference, reference["nav"], ref_idx)))
    both = pd.concat([a, b], axis=1).dropna()
    corr = float(both.corr().iloc[0, 1]) if len(both) > 2 else None
    return {"overlap_sessions": len(common), "same_held_set": same,
            "same_held_set_share": same / len(common) if common else None,
            "same_held_set_when_reference_invested": (sym_same / len(overlap_nonempty)) if overlap_nonempty else None,
            "daily_return_correlation": corr, "first": common[0] if common else None, "last": common[-1] if common else None}
