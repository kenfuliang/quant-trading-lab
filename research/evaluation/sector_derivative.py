"""Map the issuer-qualified sector-ETF derivative onto ``MarketData`` without changing it.

Inputs (see docs/tasks/2026-10-28-sector-issuer-qualification.md):

- bars: a JSON list of rows ``{symbol, session, o, h, l, c, v, ...}`` with decimal
  strings; raw, unadjusted daily prices.
- actions: a JSON object with ``cash_and_in_kind`` (``kind`` ``cash`` with ``ex_date``,
  ``pay_date`` and per-share ``amount``, or ``in_kind``) and ``splits`` (``ex_date``,
  ``ratio``). ``excluded_issuer_rows`` are explicit nonpayments and are not loaded.

Values are converted, never rounded or dropped. Anything ``MarketData`` cannot express
raises ``MarketDataError``: an in-kind distribution on a requested instrument (omitting
it would misstate a holder's equity), a non-integer split ratio, a missing instrument,
duplicate rows, or instruments whose session lists differ. Cent-grid and action-date
rules stay with ``market_model.validate``.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from research.evaluation.market_model import BAR_COLUMNS, Dividend, MarketData, MarketDataError, Split

SOURCE_COLUMNS = {"open": "o", "high": "h", "low": "l", "close": "c", "volume": "v"}


def load_sector_derivative(bars_path: Path, actions_path: Path, instruments: tuple[str, ...]) -> MarketData:
    names = tuple(instruments)
    if not names or len(set(names)) != len(names):
        raise MarketDataError(f"instruments must be non-empty and unique, got {names}")
    rows = json.loads(Path(bars_path).read_text(encoding="utf-8"))
    actions = json.loads(Path(actions_path).read_text(encoding="utf-8"))
    sessions, bars = _bars(rows, names)
    dividends, splits = _actions(actions, set(names))
    return MarketData(sessions=sessions, bars=bars, dividends=dividends, splits=splits)


def _bars(rows: list[dict], names: tuple[str, ...]) -> tuple[tuple[str, ...], dict[str, pd.DataFrame]]:
    by_name: dict[str, dict[str, dict]] = {name: {} for name in names}
    for row in rows:
        name = row["symbol"]
        if name not in by_name:
            continue
        if row["session"] in by_name[name]:
            raise MarketDataError(f"{name}: duplicate bar for session {row['session']}")
        by_name[name][row["session"]] = row
    missing = [name for name in names if not by_name[name]]
    if missing:
        raise MarketDataError(f"no bars for instruments {missing}")
    reference = sorted(by_name[names[0]])
    differing = [name for name in names[1:] if sorted(by_name[name]) != reference]
    if differing:
        raise MarketDataError(f"session lists differ from {names[0]} for instruments {differing}")
    frames = {}
    for name in names:
        frames[name] = pd.DataFrame(
            {col: [float(by_name[name][day][SOURCE_COLUMNS[col]]) for day in reference] for col in BAR_COLUMNS},
            index=pd.Index(reference, name="date"),
        )
    return tuple(reference), frames


def _actions(actions: dict, names: set[str]) -> tuple[tuple[Dividend, ...], tuple[Split, ...]]:
    dividends, unsupported = [], []
    for event in actions["cash_and_in_kind"]:
        if event["symbol"] not in names:
            continue
        if event["kind"] == "cash":
            dividends.append(Dividend(event["symbol"], event["ex_date"], event["pay_date"], float(event["amount"])))
        else:
            unsupported.append(f"{event['id']} ({event['kind']})")
    if unsupported:
        raise MarketDataError(f"actions not representable as cash dividends or splits: {unsupported}")
    splits = []
    for event in actions["splits"]:
        if event["symbol"] not in names:
            continue
        ratio = float(event["ratio"])
        if ratio != int(ratio):
            raise MarketDataError(f"split {event['id']} has non-integer ratio {event['ratio']}")
        splits.append(Split(event["symbol"], event["ex_date"], int(ratio)))
    dividends.sort(key=lambda d: (d.ex_date, d.instrument))
    splits.sort(key=lambda s: (s.effective_date, s.instrument))
    return tuple(dividends), tuple(splits)
