"""Strategy specs: plain dicts that ``build_target_fn`` turns into a ``TargetFn``.

Every strategy reads only ``history`` (bars up to and including the session, with a
causal ``split_factor`` column), sizes whole shares as ``floor(gross x weight x equity /
close)`` on the raw last close, and splits gross equally across instruments. Signals are
keyed ``(instrument, stage)`` with stages ``trend``, ``vol`` and ``state``.

The traffic light is the SPY EMA/volatility gate of the incumbent (price-peak component
disabled): red when volatility >= ``red_vol``; yellow when the trend is non-positive or
volatility >= ``yellow_vol``; green otherwise. Downgrades are immediate. Upgrades are
gated: red -> yellow after ``recover_sessions`` consecutive closes with volatility below
``recover_red_vol``; yellow -> green after ``recover_sessions`` consecutive closes with a
positive trend and volatility below ``recover_green_vol``. Until the slow EMA and the
volatility window exist there is no position: the state is red and the ``state`` signal is
emitted; only the ``vol`` and ``trend`` signals are omitted while they are undefined. At the
first assessed session the state is classified directly, as in the legacy gate (unassessed
-> yellow): red if volatility >= ``red_vol``, else yellow. Recovery counters follow the legacy
``risk_gate.states``: ``calm`` counts only while red, ``good`` only while yellow, ``good``
resets on red -> yellow, so the two recovery stages never share a confirmation close.
``state`` signal: red 0, yellow 1, green 2.

``proposal`` (traffic light only) sets the position the gate caps: ``"hold"`` (default)
holds the full cap (weight = cap: the legacy ``gate_hold``, gate-only structure of
legacy-058); ``"ema"`` proposes EMA fast > slow in/out (weight = min(1 if trend on else 0,
cap): the legacy ``gate_ema`` structure of legacy-030, ``research/policies/risk_gate.py``
``frames``).

Rebalance band: a decision keeps the current holding when its inputs (the state and the
proposal; always for ``buy_hold``) are unchanged since the previous session and
``|target - current| <= 2%`` of the current shares; otherwise it trades to the target. So
a constant-weight position does not trade for one-share drift. ``sma_trend`` is unbanded.

The EMA and volatility features are advanced incrementally per instrument (O(1) Python
work per new session) with recurrences that reproduce the pandas reference
(``ewm(span, adjust=False)``, ``pct_change().rolling(w).std(ddof=1)``) bit for bit; whether
pandas fuses a multiply-add is probed once against pandas. When the history is not an
extension of what was processed (a shorter or different prefix, a split that rescales
earlier closes) the features are recomputed from scratch. When the probe finds no exact
recurrence, or a volatility window holds only identical returns (pandas then takes a
special path), the pandas reference is used for that history instead.
"""
from __future__ import annotations

import math
from fractions import Fraction

import numpy as np
import pandas as pd

from research.evaluation.market_model import Decision, TargetFn, sma_trend_targets

RED, YELLOW, GREEN = 0, 1, 2
PROPOSALS = ("hold", "ema")
BAND = 0.02
SQRT_252 = math.sqrt(252)
INCUMBENT_SPEC: dict = {
    "name": "traffic_light",
    "proposal": "ema",
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
    return 0 if not close > 0 else max(0, math.floor(gross * cap / count * equity / close))


def _banded(target: int, current: int, unchanged: bool) -> int:
    """Keep ``current`` when the decision inputs are unchanged and the target is within the band."""
    return current if unchanged and abs(target - current) <= BAND * current else target


def _buy_hold(gross: float) -> TargetFn:
    def target_fn(session, history, holdings, equity):
        targets = {}
        for name, frame in history.items():
            target = _shares(gross, 1.0, len(history), equity, float(frame["close"].iloc[-1]))
            targets[name] = _banded(target, int(holdings.get(name, 0)), len(frame) > 1)
        return Decision(targets=targets, signals={})

    return target_fn


# --- features: pandas reference and exact incremental recurrences -------------------------

def _adjusted(frame: pd.DataFrame) -> np.ndarray:
    return (frame["close"] / frame["split_factor"]).to_numpy(dtype=float)


def _reference_features(adj: np.ndarray, fast: int, slow: int, window: int | None):
    close = pd.Series(adj)
    ema_fast = close.ewm(span=fast, adjust=False, min_periods=fast).mean().to_numpy()
    ema_slow = close.ewm(span=slow, adjust=False, min_periods=slow).mean().to_numpy()
    if window is None:
        vol = np.full(len(adj), np.nan)
    else:
        vol = (close.pct_change().rolling(window, min_periods=window).std(ddof=1) * SQRT_252).to_numpy()
    return ema_fast, ema_slow, vol


def _fma(a: float, b: float, c: float) -> float:
    """Correctly rounded ``a * b + c`` (math.fma needs Python 3.13)."""
    if not (math.isfinite(a) and math.isfinite(b) and math.isfinite(c)):
        return a * b + c
    return float(Fraction(a) * Fraction(b) + Fraction(c))


class _Ewm:
    """pandas ``ewm(span, adjust=False, min_periods=span).mean()``, one value at a time."""

    def __init__(self, span: int, fused: bool):
        self.alpha = 1.0 / (1.0 + (span - 1) / 2)
        self.factor = 1.0 - self.alpha
        self.minp = max(int(span), 1)
        self.fused = fused
        self.weighted, self.old_wt, self.nobs = None, 1.0, 0

    def push(self, cur: float) -> float:
        observed = cur == cur
        if self.weighted is None:
            self.weighted, self.nobs = cur, int(observed)
        else:
            self.nobs += observed
            w = self.weighted
            if w == w:
                self.old_wt *= self.factor
                if observed:
                    if w != cur:
                        old = self.old_wt
                        w = _fma(old, w, self.alpha * cur) if self.fused else old * w + self.alpha * cur
                        w /= old + self.alpha
                    self.old_wt = 1.0
                self.weighted = w
            elif observed:
                self.weighted = cur
        return self.weighted if self.nobs >= self.minp else math.nan


class _RollVar:
    """pandas ``rolling(window, min_periods=window).var(ddof=1)`` (Welford with Kahan terms)."""

    def __init__(self, window: int, fused: bool):
        self.window, self.minp, self.fused = window, max(int(window), 1), fused
        self.vals: list[float] = []
        self.exact = True  # False once a window of identical values appears (pandas special path)
        self._clear(math.nan)

    def _clear(self, prev: float) -> None:
        self.nobs = self.mean = self.ssq = self.c_add = self.c_remove = 0.0
        self.prev, self.same = prev, 0

    def _add(self, v: float) -> None:
        if v != v:
            return
        self.nobs += 1
        self.same = self.same + 1 if v == self.prev else 1
        self.prev = v
        prev_mean = self.mean - self.c_add
        y = v - self.c_add
        t = y - self.mean
        self.c_add = t + self.mean - y
        self.mean = self.mean + t / self.nobs
        a, b = v - prev_mean, v - self.mean
        self.ssq = _fma(a, b, self.ssq) if self.fused else self.ssq + a * b

    def _remove(self, v: float) -> None:
        if v != v:
            return
        self.nobs -= 1
        if self.nobs:
            prev_mean = self.mean - self.c_remove
            y = v - self.c_remove
            t = y - self.mean
            self.c_remove = t + self.mean - y
            self.mean = self.mean - t / self.nobs
            a, b = v - prev_mean, v - self.mean
            self.ssq = _fma(-a, b, self.ssq) if self.fused else self.ssq - a * b
        else:
            self.mean = self.ssq = 0.0

    def push(self, v: float) -> float:
        i = len(self.vals)
        self.vals.append(v)
        start = max(0, i - self.window + 1)
        if i == 0 or start >= i:
            self._clear(self.vals[start])
            for j in range(start, i + 1):
                self._add(self.vals[j])
        else:
            removed = range(max(0, i - self.window), start)
            for j in removed:
                self._remove(self.vals[j])
            if removed and self.nobs >= 1 and self.same >= self.nobs:
                self.exact = False
            self._add(v)
        if self.nobs >= 2 and self.same >= self.nobs:
            self.exact = False
        if self.nobs >= self.minp and self.nobs > 1:
            return 0.0 if self.same >= self.nobs else self.ssq / (self.nobs - 1)
        return math.nan


_MODES: dict = {}


def _modes() -> tuple[bool, bool] | None:
    """``(ewm fused, var fused)`` reproducing this pandas build exactly, or ``None``. Probed once."""
    if "modes" not in _MODES:
        rng = np.random.default_rng(20261118)
        vol = np.where(np.arange(400) < 200, 0.01, 0.03)
        adj = np.round(100 * np.cumprod(1 + rng.normal(0.0005, vol)), 2)
        found = None
        for ewm_fused in (True, False):
            for var_fused in (True, False):
                if _matches_reference(adj, ewm_fused, var_fused):
                    found = (ewm_fused, var_fused)
                    break
            if found:
                break
        _MODES["modes"] = found
    return _MODES["modes"]


def _matches_reference(adj: np.ndarray, ewm_fused: bool, var_fused: bool) -> bool:
    for fast, slow, window in ((5, 50, 20), (3, 10, 3)):
        ref = _reference_features(adj, fast, slow, window)
        tracker = _Features(fast, slow, window, (ewm_fused, var_fused))
        tracker.extend(adj)
        if not tracker.exact:
            return False
        for got, want in zip((tracker.ema_fast, tracker.ema_slow, tracker.vol), ref):
            if not np.array_equal(np.array(got), want, equal_nan=True):
                return False
    return True


class _Features:
    """Per-instrument EMA fast/slow and annualised volatility for every processed session."""

    def __init__(self, fast: int, slow: int, window: int | None, modes: tuple[bool, bool] | None):
        self.fast, self.slow, self.window, self.modes = fast, slow, window, modes
        self.reset()

    def reset(self) -> None:
        ewm_fused, var_fused = self.modes or (False, False)
        self.adj = np.empty(0)
        self.exact = self.modes is not None
        self._fast, self._slow = _Ewm(self.fast, ewm_fused), _Ewm(self.slow, ewm_fused)
        self._var = _RollVar(self.window, var_fused) if self.window else None
        self.ema_fast, self.ema_slow, self.vol = [], [], []

    def extend(self, adj: np.ndarray) -> int:
        """Process ``adj``: incrementally when it extends the processed prefix, else from scratch.

        Returns the first session index whose features may differ from before.
        """
        done = len(self.adj)
        if len(adj) < done or not np.array_equal(adj[:done], self.adj, equal_nan=True):
            self.reset()
            done = 0
        if self.exact:
            with np.errstate(divide="ignore", invalid="ignore"):
                for t in range(done, len(adj)):
                    x = float(adj[t])
                    self.ema_fast.append(self._fast.push(x))
                    self.ema_slow.append(self._slow.push(x))
                    if self._var is None:
                        self.vol.append(math.nan)
                        continue
                    ret = math.nan if t == 0 else float(adj[t] / adj[t - 1] - 1)
                    var = self._var.push(ret)
                    self.vol.append(var if var != var else float(np.sqrt(max(var, 0.0))) * SQRT_252)
                    if not self._var.exact:
                        self.exact = False
                        break
        if not self.exact:
            ema_fast, ema_slow, vol = _reference_features(adj, self.fast, self.slow, self.window)
            self.ema_fast, self.ema_slow, self.vol = list(ema_fast), list(ema_slow), list(vol)
            done = 0
        self.adj = adj
        return done


class _Gate:
    """The traffic-light state machine, one session at a time."""

    def __init__(self, spec: dict):
        self.spec = spec
        self.state, self.calm, self.good, self.assessed = RED, 0, 0, False

    def step(self, diff: float, v: float) -> int:
        spec, need = self.spec, self.spec["recover_sessions"]
        if math.isnan(diff) or math.isnan(v):
            self.state, self.calm, self.good, self.assessed = RED, 0, 0, False
            return self.state
        positive = diff > 0
        if not self.assessed:  # first assessed session classifies directly: yellow, or red below
            self.state, self.assessed = YELLOW, True
        if v >= spec["red_vol"]:
            self.state, self.calm, self.good = RED, 0, 0
        elif self.state == RED:
            self.calm = self.calm + 1 if v < spec["recover_red_vol"] else 0
            self.good = 0
            if self.calm >= need:
                self.state, self.calm = YELLOW, 0
        else:
            if self.state == GREEN and (not positive or v >= spec["yellow_vol"]):
                self.state, self.good = YELLOW, 0
            if self.state == YELLOW:
                self.good = self.good + 1 if positive and v < spec["recover_green_vol"] else 0
                if self.good >= need:
                    self.state, self.good = GREEN, 0
        return self.state


class _Tracker:
    """Features plus gate states per processed session for one instrument."""

    def __init__(self, fast: int, slow: int, window: int | None, gate_spec: dict | None):
        self.features = _Features(fast, slow, window, _modes())
        self.gate_spec = gate_spec
        self.states: list[int] = []
        self.gate = _Gate(gate_spec) if gate_spec else None

    def update(self, adj: np.ndarray) -> None:
        f = self.features
        changed = f.extend(adj)
        if self.gate is None:
            return
        if changed != len(self.states):  # earlier features were recomputed: replay the gate
            self.states, self.gate = [], _Gate(self.gate_spec)
        for t in range(len(self.states), len(f.ema_fast)):
            self.states.append(self.gate.step(f.ema_fast[t] - f.ema_slow[t], f.vol[t]))

    def trend(self, t: int) -> float:
        with np.errstate(divide="ignore", invalid="ignore"):  # numpy semantics, as the pandas reference
            return float(np.float64(self.features.ema_fast[t]) / np.float64(self.features.ema_slow[t]) - 1)

    def on(self, t: int) -> bool:
        return self.features.ema_fast[t] - self.features.ema_slow[t] > 0


def _ema_trend(fast: int, slow: int, gross: float) -> TargetFn:
    trackers: dict[str, _Tracker] = {}

    def target_fn(session, history, holdings, equity):
        targets, signals = {}, {}
        for name, frame in history.items():
            tracker = trackers.setdefault(name, _Tracker(fast, slow, None, None))
            tracker.update(_adjusted(frame))
            t = len(frame) - 1
            trend = tracker.trend(t)
            if not math.isnan(trend):
                signals[(name, "trend")] = trend
            on = tracker.on(t)
            target = _shares(gross, 1.0 if on else 0.0, len(history), equity, float(frame["close"].iloc[-1]))
            targets[name] = _banded(target, int(holdings.get(name, 0)), t >= 1 and tracker.on(t - 1) == on)
        return Decision(targets=targets, signals=signals)

    return target_fn


def _traffic_light(spec: dict) -> TargetFn:
    proposal = spec.get("proposal", "hold")
    if proposal not in PROPOSALS:
        raise ValueError(f"unknown traffic_light proposal {proposal!r}; expected one of {PROPOSALS}")
    caps = {RED: spec["caps"]["red"], YELLOW: spec["caps"]["yellow"], GREEN: spec["caps"]["green"]}
    trackers: dict[str, _Tracker] = {}

    def inputs(tracker: _Tracker, t: int) -> tuple:
        return (tracker.states[t], tracker.on(t) if proposal == "ema" else None)

    def target_fn(session, history, holdings, equity):
        targets, signals = {}, {}
        for name, frame in history.items():
            tracker = trackers.setdefault(name, _Tracker(spec["fast"], spec["slow"], spec["vol_window"], spec))
            tracker.update(_adjusted(frame))
            t = len(frame) - 1
            state, vol, trend = tracker.states[t], tracker.features.vol[t], tracker.trend(t)
            signals[(name, "state")] = float(state)
            if not math.isnan(vol):
                signals[(name, "vol")] = vol
            if not math.isnan(trend):
                signals[(name, "trend")] = trend
            weight = caps[state] if proposal == "hold" else min(1.0 if tracker.on(t) else 0.0, caps[state])
            target = _shares(spec["gross"], weight, len(history), equity, float(frame["close"].iloc[-1]))
            unchanged = t >= 1 and inputs(tracker, t) == inputs(tracker, t - 1)
            targets[name] = _banded(target, int(holdings.get(name, 0)), unchanged)
        return Decision(targets=targets, signals=signals)

    return target_fn


def traffic_light_states(adj: np.ndarray, spec: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """From-scratch reference: ``(states, vols, trends)`` per session from the pandas features."""
    ema_fast, ema_slow, vol = _reference_features(np.asarray(adj, dtype=float), spec["fast"], spec["slow"],
                                                  spec["vol_window"])
    gate = _Gate(spec)
    states = np.array([gate.step(f - s, v) for f, s, v in zip(ema_fast, ema_slow, vol)], dtype=int)
    return states, vol, ema_fast / ema_slow - 1
