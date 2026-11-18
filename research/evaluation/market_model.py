"""Shared market data model for the offline backtest engines.

Both the pandas screening engine and the NautilusTrader engine consume
``MarketData`` (raw, unadjusted prices) and call the same ``TargetFn``.
Signals use data up to the close of day t; orders fill at the open of t+1.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

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


# (session date t, bars up to and including t, current holdings, equity at close t)
TargetFn = Callable[[str, dict[str, pd.DataFrame], dict[str, int], float], Decision]


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
    top = frame[["open", "close", "low"]].max(axis=1)
    bottom = frame[["open", "close", "high"]].min(axis=1)
    if (frame["high"] < top).any() or (frame["low"] > bottom).any():
        raise MarketDataError(f"{name}: inconsistent OHLC")


def sma_trend_targets(window: int = 20, gross: float = 0.95) -> TargetFn:
    """Equal weight across instruments whose close is above their ``window``-session mean."""

    def target_fn(session: str, bars: dict[str, pd.DataFrame], holdings: dict[str, int], equity: float) -> Decision:
        targets = {name: 0 for name in bars}
        signals: dict[tuple[str, str], float] = {}
        above = []
        last_close = {}
        for name, frame in bars.items():
            if len(frame) < window:
                continue
            close = float(frame["close"].iloc[-1])
            mean = float(frame["close"].iloc[-window:].mean())
            last_close[name] = close
            signals[(name, "trend")] = close / mean - 1
            if close > mean:
                above.append(name)
        for name in above:
            targets[name] = math.floor(gross / len(above) * equity / last_close[name])
        return Decision(targets=targets, signals=signals)

    return target_fn
