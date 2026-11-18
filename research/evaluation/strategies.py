"""Strategy specs: plain dicts that ``build_target_fn`` turns into a ``TargetFn``.

Every strategy reads only ``history`` (bars up to and including the session, with a
causal ``split_factor`` column), sizes whole shares as ``floor(gross x cap x equity /
close)`` on the raw last close, and splits gross equally across instruments. Signals are
keyed ``(instrument, stage)`` with stages ``trend``, ``vol`` and ``state``.

The traffic light is the SPY EMA/volatility gate of the incumbent (price-peak component
disabled): red when volatility >= ``red_vol``; yellow when the trend is non-positive or
volatility >= ``yellow_vol``; green otherwise. Downgrades are immediate. Upgrades are
gated: red -> yellow after ``recover_sessions`` consecutive closes with volatility below
``recover_red_vol``; yellow -> green after ``recover_sessions`` consecutive closes with a
positive trend and volatility below ``recover_green_vol``. Until the slow EMA and the
volatility window exist the state is red. ``state`` signal: red 0, yellow 1, green 2.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from research.evaluation.market_model import Decision, TargetFn, sma_trend_targets

RED, YELLOW, GREEN = 0, 1, 2
INCUMBENT_SPEC: dict = {
    "name": "traffic_light",
    "fast": 50,
    "slow": 200,
    "vol_window": 20,
    "red_vol": 0.40,
    "yellow_vol": 0.25,
    "recover_red_vol": 0.35,
    "recover_green_vol": 0.20,
    "recover_sessions": 5,
    "caps": {"green": 1.0, "yellow": 0.5, "red": 0.0},
    "gross": 0.99,
}


def build_target_fn(spec: dict) -> TargetFn:
    name = spec.get("name")
    if name == "sma_trend":
        return sma_trend_targets(window=spec["window"], gross=spec["gross"])
    if name == "buy_hold":
        return _buy_hold(spec["gross"])
    if name == "ema_trend":
        return _ema_trend(spec["fast"], spec["slow"], spec["gross"])
    if name == "traffic_light":
        return _traffic_light(spec)
    raise ValueError(f"unknown strategy {name!r}")


def _shares(gross: float, cap: float, count: int, equity: float, close: float) -> int:
    return max(0, math.floor(gross * cap / count * equity / close))


def _buy_hold(gross: float) -> TargetFn:
    def target_fn(session, history, holdings, equity):
        targets = {name: _shares(gross, 1.0, len(history), equity, float(f["close"].iloc[-1]))
                   for name, f in history.items()}
        return Decision(targets=targets, signals={})

    return target_fn


def _emas(frame: pd.DataFrame, fast: int, slow: int) -> tuple[pd.Series, pd.Series]:
    close = frame["close"] / frame["split_factor"]
    return (close.ewm(span=fast, adjust=False, min_periods=fast).mean(),
            close.ewm(span=slow, adjust=False, min_periods=slow).mean())


def _ema_trend(fast: int, slow: int, gross: float) -> TargetFn:
    def target_fn(session, history, holdings, equity):
        targets, signals = {}, {}
        for name, frame in history.items():
            ema_fast, ema_slow = _emas(frame, fast, slow)
            f, s = float(ema_fast.iloc[-1]), float(ema_slow.iloc[-1])
            ready = not (math.isnan(f) or math.isnan(s))
            if ready:
                signals[(name, "trend")] = f / s - 1
            on = ready and f > s
            targets[name] = _shares(gross, 1.0 if on else 0.0, len(history), equity,
                                    float(frame["close"].iloc[-1]))
        return Decision(targets=targets, signals=signals)

    return target_fn


def _traffic_light(spec: dict) -> TargetFn:
    fast, slow, window = spec["fast"], spec["slow"], spec["vol_window"]
    need = spec["recover_sessions"]
    caps = {RED: spec["caps"]["red"], YELLOW: spec["caps"]["yellow"], GREEN: spec["caps"]["green"]}

    def final_state(frame: pd.DataFrame) -> tuple[int, float, float]:
        close = frame["close"] / frame["split_factor"]
        ema_fast, ema_slow = _emas(frame, fast, slow)
        vol = close.pct_change().rolling(window, min_periods=window).std(ddof=1) * math.sqrt(252)
        trend = (ema_fast - ema_slow).to_numpy()
        vols = vol.to_numpy()
        state, calm, good = RED, 0, 0
        for t in range(len(close)):
            if np.isnan(trend[t]) or np.isnan(vols[t]):
                state, calm, good = RED, 0, 0
                continue
            positive, v = trend[t] > 0, vols[t]
            calm = calm + 1 if v < spec["recover_red_vol"] else 0
            good = good + 1 if positive and v < spec["recover_green_vol"] else 0
            if v >= spec["red_vol"]:
                state = RED
            elif state == GREEN and (not positive or v >= spec["yellow_vol"]):
                state = YELLOW
            elif state == RED and calm >= need:
                state = YELLOW
            elif state == YELLOW and good >= need:
                state = GREEN
        return state, float(vols[-1]), float(ema_fast.iloc[-1] / ema_slow.iloc[-1] - 1)

    def target_fn(session, history, holdings, equity):
        targets, signals = {}, {}
        for name, frame in history.items():
            state, vol, trend = final_state(frame)
            signals[(name, "state")] = float(state)
            if not math.isnan(vol):
                signals[(name, "vol")] = vol
            if not math.isnan(trend):
                signals[(name, "trend")] = trend
            targets[name] = _shares(spec["gross"], caps[state], len(history), equity,
                                    float(frame["close"].iloc[-1]))
        return Decision(targets=targets, signals=signals)

    return target_fn
