"""ETF normalisation recipe ``etf-normalise/v1`` and own backward adjustment ``adjust/v1``.

Raw source rows and issuer actions go in; a validated ``MarketData`` comes out. This lives
under ``research/evaluation`` (not ``research/data``) because it needs the market-model
types and ``data`` may not import ``evaluation``.

Recipe:

- Bars follow the rules of ``sector_derivative``: duplicate rows, instruments with no
  bars, and differing session lists raise ``MarketDataError``.
- OHLC are rounded half-even to the cent with ``decimal``; every changed value is counted
  per instrument and field. Volume is unchanged. A price that rounds to <= 0 is an error.
- Cash events whose ``ex_date`` or ``pay_date`` falls outside the bar range are excluded and
  listed with a reason (paid after window end, before window start, after window end); a
  date inside the range that is not a session is a data error.
- An in-kind event on a requested instrument becomes a cash-equivalent dividend:
  ``per_share = round(ratio * child close on ex_date, 6)``, paid on its pay date and
  labelled ``in_kind_cash_equivalent``. A child with no bar on the ex-date is an error.
- Splits need an integer ratio; the result must pass ``market_model.validate``.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

import pandas as pd

from research.evaluation.market_model import (
    BAR_COLUMNS, Dividend, MarketData, MarketDataError, Split, validate)

RECIPE = "etf-normalise/v1"
ADJUST_RECIPE = "adjust/v1"
LABEL_IN_KIND = "in_kind_cash_equivalent"
SOURCE_COLUMNS = {"open": "o", "high": "h", "low": "l", "close": "c", "volume": "v"}
PRICE_FIELDS = ("open", "high", "low", "close")
CENT = Decimal("0.01")
MICRO = Decimal("0.000001")


@dataclass(frozen=True)
class Normalised:
    data: MarketData
    rounding: dict[str, dict[str, int]]
    converted: tuple[dict, ...]
    excluded: tuple[dict, ...]


def _decimal(value, what: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise MarketDataError(f"{what}: not a decimal: {value!r}") from None
    if not number.is_finite():
        raise MarketDataError(f"{what}: not finite: {value!r}")
    return number


def _bars(rows: list[dict], names: tuple[str, ...]):
    by_name: dict[str, dict[str, dict]] = {name: {} for name in names}
    for row in rows:
        name = row.get("symbol")
        if name not in by_name:
            continue
        if "session" not in row:
            raise MarketDataError(f"{name}: row without session")
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
    frames, rounding, closes = {}, {}, {}
    for name in names:
        columns = {col: [] for col in BAR_COLUMNS}
        counts = {field: 0 for field in PRICE_FIELDS}
        closes[name] = {}
        for day in reference:
            row = by_name[name][day]
            for col in BAR_COLUMNS:
                try:
                    raw = row[SOURCE_COLUMNS[col]]
                except KeyError:
                    raise MarketDataError(f"{name} {day}: missing field {SOURCE_COLUMNS[col]}") from None
                number = _decimal(raw, f"{name} {day} {col}")
                if col == "volume":
                    columns[col].append(float(number))
                    continue
                cents = number.quantize(CENT, rounding=ROUND_HALF_EVEN)
                if cents <= 0:
                    raise MarketDataError(f"{name} {day} {col}: non-positive price after rounding ({raw})")
                if cents != number:
                    counts[col] += 1
                columns[col].append(float(cents))
                if col == "close":
                    closes[name][day] = cents
        frames[name] = pd.DataFrame(columns, index=pd.Index(reference, name="date"))
        rounding[name] = counts
    return tuple(reference), frames, rounding, closes


def _excluded(event: dict, reason: str) -> dict:
    entry = {"id": event.get("id"), "symbol": event["symbol"], "kind": event["kind"],
             "ex_date": event["ex_date"], "pay_date": event["pay_date"], "reason": reason}
    for key in ("amount", "ratio", "child_symbol"):
        if key in event:
            entry[key] = event[key]
    return entry


def _child_close(rows: list[dict], child: str, day: str, closes, label: str) -> Decimal:
    known = closes.get(child, {}).get(day)
    if known is not None:
        return known
    for row in rows:
        if row.get("symbol") == child and row.get("session") == day:
            cents = _decimal(row.get("c"), f"{label}: child {child} {day} close").quantize(
                CENT, rounding=ROUND_HALF_EVEN)
            if cents <= 0:
                raise MarketDataError(f"{label}: child {child} {day} close non-positive after rounding")
            return cents
    raise MarketDataError(f"{label}: child {child} has no bar on ex_date {day}")


def _window_reason(event: dict, sessions: tuple[str, ...], session_set: set, label: str) -> str | None:
    """Why an event cannot be loaded, or None when both dates are bar sessions.

    A date inside the bar range that is not a session is a data error; dates outside the
    range are window effects and are listed with a reason that says which side.
    """
    first, last = sessions[0], sessions[-1]
    where = {}
    for key in ("ex_date", "pay_date"):
        day = event[key]
        if day in session_set:
            where[key] = "in"
        elif day < first:
            where[key] = "before"
        elif day > last:
            where[key] = "after"
        else:
            raise MarketDataError(f"{label}: {key} {day} is inside the bar range but not a session")
    if set(where.values()) == {"in"}:
        return None
    if where["ex_date"] == "in" and where["pay_date"] == "after":
        return "paid after window end; total return understated by the dividend"
    detail = ", ".join(f"{k} {event[k]}" for k in ("ex_date", "pay_date") if where[k] != "in")
    if "before" in where.values():
        return f"before window start: {detail}"
    return f"after window end: {detail}"


def _actions(actions: dict, names: tuple[str, ...], sessions: tuple[str, ...], closes, rows):
    session_set, wanted = set(sessions), set(names)
    dividends, converted, excluded, splits = [], [], [], []
    for event in actions["cash_and_in_kind"]:
        if event.get("symbol") not in wanted:
            continue
        label = event.get("id") or event["symbol"]
        try:
            if event["kind"] not in ("cash", "in_kind"):
                raise MarketDataError(f"{label}: unsupported event kind {event['kind']!r}")
            reason = _window_reason(event, sessions, session_set, label)
            if reason:
                excluded.append(_excluded(event, reason))
                continue
            symbol = event["symbol"]
            if event["kind"] == "cash":
                per_share = _decimal(event["amount"], f"{label} amount")
            else:
                child = event["child_symbol"]
                child_close = _child_close(rows, child, event["ex_date"], closes, label)
                ratio = _decimal(event["ratio"], f"{label} ratio")
                per_share = (ratio * child_close).quantize(MICRO, rounding=ROUND_HALF_EVEN)
                converted.append({"id": label, "symbol": symbol, "ex_date": event["ex_date"],
                                  "pay_date": event["pay_date"], "child_symbol": child,
                                  "ratio": str(event["ratio"]), "child_close": str(child_close),
                                  "per_share": str(per_share), "label": LABEL_IN_KIND})
        except KeyError as error:
            raise MarketDataError(f"{label}: missing field {error}") from None
        dividends.append(Dividend(symbol, event["ex_date"], event["pay_date"], float(per_share)))
    for event in actions["splits"]:
        if event.get("symbol") not in wanted:
            continue
        label = event.get("id") or event["symbol"]
        try:
            ratio = _decimal(event["ratio"], f"{label} ratio")
            if ratio != int(ratio):
                raise MarketDataError(f"split {label} has non-integer ratio {event['ratio']}")
            splits.append(Split(event["symbol"], event["ex_date"], int(ratio)))
        except KeyError as error:
            raise MarketDataError(f"{label}: missing field {error}") from None
    dividends.sort(key=lambda d: (d.ex_date, d.instrument))
    splits.sort(key=lambda s: (s.effective_date, s.instrument))
    return tuple(dividends), tuple(splits), tuple(converted), tuple(excluded)


def normalise(rows: list[dict], actions: dict, instruments: tuple[str, ...]) -> Normalised:
    names = tuple(instruments)
    if not names or len(set(names)) != len(names):
        raise MarketDataError(f"instruments must be non-empty and unique, got {names}")
    sessions, bars, rounding, closes = _bars(rows, names)
    dividends, splits, converted, excluded = _actions(actions, names, sessions, closes, rows)
    data = MarketData(sessions=sessions, bars=bars, dividends=dividends, splits=splits)
    validate(data)
    return Normalised(data=data, rounding=rounding, converted=converted, excluded=excluded)


def adjusted_close(data: MarketData) -> dict[str, pd.Series]:
    """Backward-adjusted closes (analysis and cross-checks only; raw prices stay raw).

    Closes before a split's effective date are divided by its ratio. Closes before a
    dividend's ex-date are multiplied by ``1 - per_share / close on the previous session``.
    A dividend on the first session has no earlier close to adjust and is ignored.
    """
    position = {day: i for i, day in enumerate(data.sessions)}
    result = {}
    for name, frame in data.bars.items():
        close = frame["close"].astype(float)
        factor = pd.Series(1.0, index=close.index)
        for split in data.splits:
            if split.instrument == name:
                factor.iloc[: position[split.effective_date]] /= split.ratio
        for dividend in data.dividends:
            if dividend.instrument != name:
                continue
            k = position[dividend.ex_date]
            if k == 0:
                continue
            factor.iloc[:k] *= 1 - dividend.per_share / float(close.iloc[k - 1])
        result[name] = close * factor
    return result
