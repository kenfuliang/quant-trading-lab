"""Shared market data model for the offline backtest engines.

Both the pandas screening engine and the NautilusTrader engine consume
``MarketData`` (raw, unadjusted prices on the cent grid, enforced by ``validate``)
and call the same ``TargetFn`` on the same ``history_view``.
Signals use data up to the close of day t; orders fill at the open of t+1.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

BAR_COLUMNS = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class Dividend:
    instrument: str
    ex_date: str
    pay_date: str
    per_share: float


@dataclass(frozen=True)
class Split:
    """Forward split only; ``ratio >= 2``."""

    instrument: str
    effective_date: str
    ratio: int


@dataclass(frozen=True)
class MarketData:
    sessions: tuple[str, ...]
    bars: dict[str, pd.DataFrame]
    dividends: tuple[Dividend, ...]
    splits: tuple[Split, ...]


class MarketDataError(ValueError):
    pass


@dataclass(frozen=True)
class MarketConfig:
    initial_cash: float = 100_000.0
    cost_bps: float = 5.0
    commission_usd: float = 1.0


@dataclass(frozen=True)
class Decision:
    targets: dict[str, int]
    signals: dict[tuple[str, str], float]


# (session date t, history_view(data, t): bars up to and including t with a causal
# ``split_factor`` column, current holdings, equity at close t)
TargetFn = Callable[[str, dict[str, pd.DataFrame], dict[str, int], float], Decision]


def history_view(data: MarketData, i: int) -> dict[str, pd.DataFrame]:
    """What both engines pass to ``TargetFn`` after the close of session ``i``.

    Bars up to and including session ``i`` (raw prices, copies) with an added
    ``split_factor`` column: the product of the ratios of splits effective after that row
    and on or before session ``i`` (1.0 otherwise). ``close / split_factor`` is the close
    on session ``i``'s share basis. Splits after session ``i`` never affect the view.
    """
    effective = {}
    for split in data.splits:
        k = data.sessions.index(split.effective_date)
        if k <= i:
            effective.setdefault(split.instrument, []).append((k, split.ratio))
    view = {}
    for name, frame in data.bars.items():
        factor = np.ones(i + 1)
        for k, ratio in effective.get(name, ()):
            factor[:k] *= ratio
        view[name] = frame.iloc[: i + 1].assign(split_factor=factor)
    return view


def execution_price(open_px: float, side: str, cost_bps: float) -> float:
    if side not in ("BUY", "SELL"):
        raise ValueError(f"side must be BUY or SELL, got {side!r}")
    sign = 1 if side == "BUY" else -1
    return round(open_px * (1 + sign * cost_bps / 10_000), 2)


def validate(data: MarketData) -> None:
    sessions = list(data.sessions)
    if not sessions:
        raise MarketDataError("no sessions")
    for earlier, later in zip(sessions, sessions[1:]):
        if later <= earlier:
            raise MarketDataError(f"sessions unsorted or duplicated at {earlier} -> {later}")
    for name, frame in data.bars.items():
        _validate_bars(name, frame, sessions)
    known = set(data.bars)
    session_set = set(sessions)
    for dividend in data.dividends:
        _require_known(dividend.instrument, known, "dividend")
        for label, day in (("ex_date", dividend.ex_date), ("pay_date", dividend.pay_date)):
            if day not in session_set:
                raise MarketDataError(f"dividend {label} {day} is not a session")
        if dividend.pay_date < dividend.ex_date:
            raise MarketDataError(f"dividend pay_date before ex_date for {dividend.instrument}")
        if dividend.per_share <= 0:
            raise MarketDataError(f"dividend per_share must be positive for {dividend.instrument}")
    for split in data.splits:
        _require_known(split.instrument, known, "split")
        if split.effective_date not in session_set:
            raise MarketDataError(f"split effective_date {split.effective_date} is not a session")
        if split.ratio < 2:
            raise MarketDataError(f"split ratio must be >= 2, got {split.ratio}")
        for dividend in data.dividends:
            if dividend.instrument == split.instrument and dividend.ex_date <= split.effective_date <= dividend.pay_date:
                raise MarketDataError(
                    f"split {split.instrument} {split.effective_date} falls inside dividend window "
                    f"{dividend.ex_date}..{dividend.pay_date}"
                )


def _require_known(instrument: str, known: set[str], kind: str) -> None:
    if instrument not in known:
        raise MarketDataError(f"{kind} names unknown instrument {instrument}")


def _validate_bars(name: str, frame: pd.DataFrame, sessions: list[str]) -> None:
    if list(frame.index) != sessions:
        raise MarketDataError(f"{name}: bar index does not match sessions exactly")
    missing = [c for c in BAR_COLUMNS if c not in frame.columns]
    if missing:
        raise MarketDataError(f"{name}: missing columns {missing}")
    if frame[list(BAR_COLUMNS)].isna().any().any():
        raise MarketDataError(f"{name}: NaN values")
    if (frame[["open", "high", "low", "close"]] <= 0).any().any():
        raise MarketDataError(f"{name}: non-positive price")
    prices = frame[["open", "high", "low", "close"]].to_numpy(dtype=float) * 100
    if (abs(prices - prices.round()) > 1e-6).any():
        raise MarketDataError(f"{name}: price not on the cent grid")
    top = frame[["open", "close", "low"]].max(axis=1)
    bottom = frame[["open", "close", "high"]].min(axis=1)
    if (frame["high"] < top).any() or (frame["low"] > bottom).any():
        raise MarketDataError(f"{name}: inconsistent OHLC")


def sma_trend_targets(window: int = 20, gross: float = 0.95) -> TargetFn:
    """Equal weight across instruments whose close is above their ``window``-session mean.

    Mean and signal use ``close / split_factor`` (``history_view``), so a split inside the
    window does not distort them; share counts use the raw last close.
    """

    def target_fn(session: str, bars: dict[str, pd.DataFrame], holdings: dict[str, int], equity: float) -> Decision:
        targets = {name: 0 for name in bars}
        signals: dict[tuple[str, str], float] = {}
        above = []
        last_close = {}
        for name, frame in bars.items():
            if len(frame) < window:
                continue
            adjusted = frame["close"] / frame["split_factor"]
            close = float(adjusted.iloc[-1])  # split_factor is 1.0 on the last row
            mean = float(adjusted.iloc[-window:].mean())
            last_close[name] = float(frame["close"].iloc[-1])
            signals[(name, "trend")] = close / mean - 1
            if close > mean:
                above.append(name)
        for name in above:
            targets[name] = math.floor(gross / len(above) * equity / last_close[name])
        return Decision(targets=targets, signals=signals)

    return target_fn
