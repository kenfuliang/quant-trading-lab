"""Deterministic synthetic market used by the engine parity check."""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.evaluation.market_model import Dividend, MarketData, Split

SESSION_COUNT = 250
START = "2024-01-02"
SPLIT_SESSION = 120
START_PRICES = {"AAA": 50.0, "BBB": 200.0, "CCC": 120.0}
DIVIDENDS = (("AAA", (30, 90, 150, 210), 0.40), ("CCC", (60, 180), 0.25))
PAY_LAG = 5


def synthetic_fixture(seed: int = 7) -> MarketData:
    sessions = tuple(d.strftime("%Y-%m-%d") for d in pd.bdate_range(START, periods=SESSION_COUNT))
    rng = np.random.default_rng(seed)
    bars = {name: _walk(name, start, sessions, rng) for name, start in START_PRICES.items()}
    dividends = tuple(
        Dividend(name, sessions[ex], sessions[ex + PAY_LAG], per_share)
        for name, exes, per_share in DIVIDENDS
        for ex in exes
    )
    splits = (Split("BBB", sessions[SPLIT_SESSION], 2),)
    return MarketData(sessions=sessions, bars=bars, dividends=dividends, splits=splits)


def _walk(name: str, start: float, sessions: tuple[str, ...], rng: np.random.Generator) -> pd.DataFrame:
    n = len(sessions)
    gaps = rng.normal(0.0, 0.004, n)
    moves = rng.normal(0.0003, 0.012, n)
    wick_up = rng.uniform(0.0, 0.006, n)
    wick_down = rng.uniform(0.0, 0.006, n)
    volume = rng.integers(100_000, 1_000_000, n)

    opens = np.empty(n)
    closes = np.empty(n)
    prev = start
    for i in range(n):
        opens[i] = prev * (1 + gaps[i])
        closes[i] = opens[i] * (1 + moves[i])
        prev = closes[i]
    opens, closes = np.round(opens, 2), np.round(closes, 2)
    if name == "BBB":
        # Continuous (pre-split basis) path; the 2:1 split halves raw prices from the effective session.
        closes[SPLIT_SESSION - 1] = _even_cents(closes[SPLIT_SESSION - 1])
        opens[SPLIT_SESSION:] = np.round(opens[SPLIT_SESSION:] / 2, 2)
        closes[SPLIT_SESSION:] = np.round(closes[SPLIT_SESSION:] / 2, 2)
        # The first post-split open is half the pre-split close exactly.
        opens[SPLIT_SESSION] = closes[SPLIT_SESSION - 1] / 2
    opens = np.maximum(opens, 0.01)
    closes = np.maximum(closes, 0.01)
    highs = np.round(np.maximum(opens, closes) * (1 + wick_up), 2)
    lows = np.round(np.minimum(opens, closes) * (1 - wick_down), 2)
    highs = np.maximum(highs, np.maximum(opens, closes))
    lows = np.maximum(np.minimum(lows, np.minimum(opens, closes)), 0.01)
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volume.astype(float)},
        index=pd.Index(sessions, name="date"),
    )


def _even_cents(price: float) -> float:
    cents = int(round(price * 100))
    return (cents + cents % 2) / 100
