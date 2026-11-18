"""Dataset quality report ``quality-report/v1``.

Checks a normalised ETF dataset (source rows plus the ``Normalised`` result) and, when a Yahoo
snapshot is supplied, cross-checks closes. Lives under ``research/evaluation`` because it
consumes ``Normalised``; ``research/data`` may import only ``research/data``.

Statuses: each check is ``pass``, ``fail``, ``exception`` or ``blocked``. The report is
``fail`` if any check fails, else ``pass-with-exceptions`` if any is ``exception`` or
``blocked``, else ``pass``. Acceptance is left for the owner.
"""
from __future__ import annotations

import json
import math
import subprocess
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd

from research.evaluation.etf_normalise import RECIPE, Normalised
from research.evaluation.market_model import Split
from research.data.calendar import is_half_day, sessions as calendar_sessions

SCHEMA = "quality-report/v1"
CHECKS = ("sessions", "half_days", "duplicates", "non_finite", "non_positive", "zero_volume",
          "ohlc", "gaps", "cent_rounding", "actions_converted", "actions_excluded", "cross_source",
          "split_events")
MAX_ITEMS = 50
GAP_LIMIT = 0.25
ABS_TOLERANCE = 0.01
REL_TOLERANCE = 5e-4  # 5 bp
PRICE_KEYS = ("o", "h", "l", "c")
ALL_KEYS = PRICE_KEYS + ("v",)
ROOT = Path(__file__).resolve().parents[2]


def _check(name: str, status: str, items: list, detail: str, count: int | None = None, **extra) -> dict:
    entry = {"name": name, "status": status, "count": len(items) if count is None else count,
             "detail": detail, "items": items[:MAX_ITEMS], "omitted": max(0, len(items) - MAX_ITEMS)}
    entry.update(extra)
    return entry


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _check_sessions(rows: list[dict]) -> dict:
    days = sorted({r["session"] for r in rows if "session" in r})
    if not days:
        return _check("sessions", "fail", [{"problem": "no bars"}], "no bar sessions")
    try:
        expected = {d.strftime("%Y-%m-%d") for d in calendar_sessions(days[0], days[-1])}
    except ValueError as error:
        return _check("sessions", "fail", [{"problem": str(error)}], f"calendar unavailable: {error}")
    have = set(days)
    items = ([{"session": d, "problem": "missing"} for d in sorted(expected - have)] +
             [{"session": d, "problem": "extra"} for d in sorted(have - expected)])
    return _check("sessions", "fail" if items else "pass", items,
                  f"{len(expected)} calendar sessions {days[0]}..{days[-1]}, {len(have)} bar sessions")


def _check_half_days(rows: list[dict]) -> dict:
    items = []
    for day in sorted({r["session"] for r in rows if "session" in r}):
        try:
            early = is_half_day(day)
        except ValueError:
            continue
        if early:
            items.append({"session": day, "close_et": "13:00"})
    return _check("half_days", "pass", items, "early-close sessions in the bar range")


def _check_duplicates(rows: list[dict]) -> dict:
    seen, items = set(), []
    for r in rows:
        key = (r.get("symbol"), r.get("session"))
        if key in seen:
            items.append({"symbol": key[0], "session": key[1]})
        seen.add(key)
    return _check("duplicates", "fail" if items else "pass", items, "repeated (symbol, session) rows")


def _check_non_finite(rows: list[dict]) -> dict:
    items = []
    for r in rows:
        bad = [k for k in ALL_KEYS if _number(r.get(k)) is None]
        if bad:
            items.append({"symbol": r.get("symbol"), "session": r.get("session"), "fields": bad})
    return _check("non_finite", "fail" if items else "pass", items, "missing or non-finite OHLCV fields")


def _check_non_positive(rows: list[dict]) -> dict:
    items = []
    for r in rows:
        bad = [k for k in PRICE_KEYS if _number(r.get(k)) is not None and _number(r.get(k)) <= 0]
        volume = _number(r.get("v"))
        if volume is not None and volume < 0:
            bad.append("v")
        if bad:
            items.append({"symbol": r.get("symbol"), "session": r.get("session"), "fields": bad})
    return _check("non_positive", "fail" if items else "pass", items,
                  "prices <= 0 or negative volume (zero volume is reported by zero_volume)")


def _check_zero_volume(rows: list[dict]) -> dict:
    items = [{"symbol": r.get("symbol"), "session": r.get("session")}
             for r in rows if _number(r.get("v")) == 0]
    return _check("zero_volume", "exception" if items else "pass", items, "sessions with zero volume")


def _check_ohlc(rows: list[dict]) -> dict:
    items = []
    for r in rows:
        values = [_number(r.get(k)) for k in PRICE_KEYS]
        if any(v is None for v in values):
            continue
        o, h, l, c = values
        if h < max(o, c, l) or l > min(o, c, h):
            items.append({"symbol": r.get("symbol"), "session": r.get("session"),
                          "o": r["o"], "h": r["h"], "l": r["l"], "c": r["c"]})
    return _check("ohlc", "fail" if items else "pass", items, "high below, or low above, another price")


def _check_gaps(norm: Normalised) -> dict:
    data, items = norm.data, []
    action_days = {(d.instrument, d.ex_date) for d in data.dividends}
    action_days |= {(s.instrument, s.effective_date) for s in data.splits}
    for name, frame in data.bars.items():
        change = frame["close"].astype(float).pct_change()
        for day, move in change.items():
            if pd.notna(move) and abs(move) > GAP_LIMIT and (name, day) not in action_days:
                items.append({"symbol": name, "session": day, "change": round(float(move), 6)})
    return _check("gaps", "exception" if items else "pass", items,
                  f"close-to-close move over {GAP_LIMIT:.0%} with no dividend or split that day")


def _check_rounding(norm: Normalised) -> dict:
    items = [{"symbol": s, "field": f, "changed": n}
             for s, counts in norm.rounding.items() for f, n in counts.items() if n]
    total = sum(i["changed"] for i in items)
    return _check("cent_rounding", "exception" if total else "pass", items,
                  f"{total} price values changed by half-even cent rounding", count=total)


def _check_events(name: str, events, detail: str) -> dict:
    items = list(events)
    return _check(name, "exception" if items else "pass", items, detail)


def _unadjusted(frame: pd.DataFrame, yahoo_splits: list[dict]) -> pd.Series:
    """Yahoo closes as traded: scale closes before each Yahoo split by numerator/denominator."""
    close = frame["close"].astype(float).copy()
    for split in yahoo_splits:
        close[close.index < split["date"]] *= split["numerator"] / split["denominator"]
    return close


def _check_cross_source(norm: Normalised, yahoo, yahoo_splits: dict) -> dict:
    if yahoo is None:
        return _check("cross_source", "blocked", [], "no Yahoo snapshot supplied")
    diffs, items, notes, per_symbol = [], [], [], {}
    for name, frame in norm.data.bars.items():
        if name not in yahoo:
            notes.append(f"{name}: not in snapshot")
            continue
        theirs = _unadjusted(yahoo[name], yahoo_splits.get(name, []))
        ours = frame["close"].astype(float)
        for missing in ours.index.difference(theirs.index):
            notes.append(f"{name} {missing}: not in snapshot")
        own = []
        for day in ours.index.intersection(theirs.index):
            diff = abs(float(theirs[day]) - float(ours[day]))
            diffs.append(diff)
            own.append(diff)
            if diff > max(ABS_TOLERANCE, REL_TOLERANCE * float(ours[day])):
                items.append({"symbol": name, "session": day, "alpaca_close": float(ours[day]),
                              "yahoo_close_unadjusted": round(float(theirs[day]), 6),
                              "abs_diff": round(diff, 6)})
        if own:
            per_symbol[name] = {"compared": len(own),
                                "breaches": sum(1 for i in items if i["symbol"] == name),
                                "max_abs_diff": round(float(max(own)), 6),
                                "p99_abs_diff": round(float(np.percentile(own, 99)), 6)}
    items.sort(key=lambda i: -i["abs_diff"])
    stats = {"compared": len(diffs), "breaches": len(items),
             "max_abs_diff": round(float(max(diffs)), 6) if diffs else 0.0,
             "p99_abs_diff": round(float(np.percentile(diffs, 99)), 6) if diffs else 0.0,
             "by_symbol": per_symbol,
             "not_compared": notes[:MAX_ITEMS], "not_compared_count": len(notes)}
    summary = "; ".join(f"{s} {v['breaches']}/{v['compared']} max {v['max_abs_diff']} p99 {v['p99_abs_diff']}"
                        for s, v in per_symbol.items())
    detail = (f"compared {stats['compared']} closes (Yahoo un-adjusted with Yahoo's own splits); "
              f"breaches {len(items)}; max {stats['max_abs_diff']}; p99 {stats['p99_abs_diff']}; "
              f"tolerance max({ABS_TOLERANCE}, 5 bp of close); not compared {len(notes)}. "
              f"Per symbol (breaches/compared): {summary}")
    if not diffs:
        status = "blocked"
        detail = "nothing compared: " + detail
    else:
        status = "exception" if items or notes else "pass"
    return _check("cross_source", status, items, detail, stats=stats)


def _ratio_text(numerator, denominator) -> str:
    return f"{numerator:g}:{denominator:g}"


def _fraction(numerator, denominator) -> Fraction:
    """Yahoo carries split terms as floats; go through their decimal text for an exact ratio."""
    return Fraction(str(numerator)) / Fraction(str(denominator))


def _check_split_events(norm: Normalised, yahoo, splits: tuple[Split, ...], yahoo_splits: dict) -> dict:
    if yahoo is None:
        return _check("split_events", "blocked", [], "no Yahoo snapshot supplied")
    sessions = norm.data.sessions
    first, last = sessions[0], sessions[-1]
    in_kind = {(e["symbol"], e["ex_date"]): e for e in norm.converted}
    symbols = [name for name in norm.data.bars if name in yahoo]
    items = []
    for name in symbols:
        theirs = {}
        for event in yahoo_splits.get(name, []):
            if first <= event["date"] <= last:
                key = (event["date"], _fraction(event["numerator"], event["denominator"]))
                theirs[key] = event
        ours = {(s.effective_date, Fraction(s.ratio, 1)): s for s in splits if s.instrument == name}
        for key in sorted(set(theirs) - set(ours)):
            event = theirs[key]
            note = "Yahoo split event not in our split records"
            converted = in_kind.get((name, event["date"]))
            if converted:
                note = (f"corresponds to our in-kind event {converted['id']}, which we load as a "
                        "cash-equivalent dividend, not a split")
            items.append({"symbol": name, "date": event["date"], "source": "yahoo_only",
                          "ratio": _ratio_text(event["numerator"], event["denominator"]), "note": note})
        for key in sorted(set(ours) - set(theirs)):
            split = ours[key]
            items.append({"symbol": name, "date": split.effective_date, "source": "ours_only",
                          "ratio": _ratio_text(split.ratio, 1), "note": "our split record not in Yahoo's events"})
    items.sort(key=lambda i: (i["symbol"], i["date"], i["source"]))
    return _check("split_events", "exception" if items else "pass", items,
                  f"our split records vs Yahoo split events for {len(symbols)} symbols in {first}..{last}")


def _code_commit() -> str:
    """Git HEAD of the code that built the report, ``+dirty`` when the tree has changes."""
    def git(*args):
        try:
            out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True)
            return out.stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None
    commit = git("rev-parse", "HEAD") or "unknown"
    dirty = git("status", "--porcelain", "--untracked-files=normal")
    return commit if dirty == "" else f"{commit}+dirty"


def _status(checks: list[dict]) -> str:
    statuses = {c["status"] for c in checks}
    if "fail" in statuses:
        return "fail"
    return "pass-with-exceptions" if statuses & {"exception", "blocked"} else "pass"


def _inputs(inputs: dict | None) -> dict:
    base = {"manifest_sha256": None, "yahoo_snapshot_id": None, "yahoo_manifest_sha256": None}
    base.update(inputs or {})
    return base


def build_report(dataset_id: str, rows: list[dict], norm: Normalised, yahoo, splits: tuple[Split, ...],
                 created_utc: str | None = None, yahoo_splits: dict | None = None,
                 inputs: dict | None = None, code_commit: str | None = None) -> dict:
    """``splits`` are our split records; ``yahoo_splits`` maps symbol to Yahoo's split events."""
    created = created_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    yahoo_splits = yahoo_splits or {}
    built = {
        "sessions": _check_sessions(rows),
        "half_days": _check_half_days(rows),
        "duplicates": _check_duplicates(rows),
        "non_finite": _check_non_finite(rows),
        "non_positive": _check_non_positive(rows),
        "zero_volume": _check_zero_volume(rows),
        "ohlc": _check_ohlc(rows),
        "gaps": _check_gaps(norm),
        "cent_rounding": _check_rounding(norm),
        "actions_converted": _check_events("actions_converted", norm.converted,
                                           "in-kind distributions converted to cash equivalents"),
        "actions_excluded": _check_events("actions_excluded", norm.excluded,
                                          "cash events outside the bar sessions"),
        "cross_source": _check_cross_source(norm, yahoo, yahoo_splits),
        "split_events": _check_split_events(norm, yahoo, splits, yahoo_splits),
    }
    checks = [built[name] for name in CHECKS]
    return {"schema": SCHEMA, "dataset_id": dataset_id, "recipe": RECIPE, "created_utc": created,
            "status": _status(checks), "checks": checks, "inputs": _inputs(inputs),
            "code_commit": code_commit or _code_commit(),
            "acceptance": {"accepted_by": None, "accepted_utc": None}}


def build_failure_report(dataset_id: str, recipe: str, error: str, created_utc: str | None = None,
                         inputs: dict | None = None, code_commit: str | None = None) -> dict:
    """A ``fail`` report for a dataset the recipe could not normalise at all."""
    created = created_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    check = _check("normalise", "fail", [{"error": error}], "the normalisation recipe raised an error")
    return {"schema": SCHEMA, "dataset_id": dataset_id, "recipe": recipe, "created_utc": created,
            "status": "fail", "checks": [check], "inputs": _inputs(inputs),
            "code_commit": code_commit or _code_commit(),
            "acceptance": {"accepted_by": None, "accepted_utc": None}}


def render_report(report: dict) -> str:
    lines = [f"# Quality report: {report['dataset_id']}", "",
             f"- schema: {report['schema']}", f"- recipe: {report['recipe']}",
             f"- created: {report['created_utc']}", f"- status: **{report['status']}**",
             f"- accepted by: {report['acceptance']['accepted_by']}", "",
             "| check | status | count |", "| --- | --- | --- |"]
    lines += [f"| {c['name']} | {c['status']} | {c['count']} |" for c in report["checks"]]
    for c in report["checks"]:
        if c["status"] == "pass" and c["name"] != "half_days":
            continue
        lines += ["", f"## {c['name']} ({c['status']})", "", c["detail"], ""]
        lines += [f"- {item}" for item in c["items"]]
        if c.get("omitted", 0) > 0:
            lines.append(f"- ... {c['omitted']} more in report.json")
    return "\n".join(lines) + "\n"


def write_report(root: Path, report: dict) -> Path:
    """Write report.json and report.md in a new folder; never overwrite."""
    stamp = report["created_utc"].replace("-", "").replace(":", "")
    folder = Path(root) / "quality" / report["dataset_id"] / stamp
    folder.parent.mkdir(parents=True, exist_ok=True)
    folder.mkdir(exist_ok=False)
    with open(folder / "report.json", "x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    with open(folder / "report.md", "x", encoding="utf-8") as handle:
        handle.write(render_report(report))
    return folder
