"""Shadow decisions: hypothetical SPY positions with no order fields.

Pure and offline. A shadow decision records what the strategy would hold; it is
not an order and carries no side, quantity or client id. Nothing here submits,
imports an execution client or touches a broker.
"""
from __future__ import annotations

from datetime import datetime
import json
import math
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from paper_trading.spy_signal import FAST, SLOW, indicators, target_position

NY = ZoneInfo("America/New_York")
RECORD_ORIGIN = "shadow"
SIGNAL_VERSION = "spy-ema50-200-v1"
FORBIDDEN_FIELDS = frozenset({
    "side", "quantity", "qty", "order_id", "client_id", "client_order_id", "order_type",
    "type", "limit_price", "price", "notional", "time_in_force", "account", "account_id"})
REQUIRED_FIELDS = ("record_origin", "signal_version", "observed_close_date", "session",
                   "hypothetical_position", "fast_ema", "slow_ema", "bars_used")


def parse_spy_closes(payloads, symbol="SPY"):
    """{session: close} from Alpaca-style daily-bar pages; refuses anything malformed."""
    closes = {}
    for payload in payloads:
        if not isinstance(payload.get("bars"), dict):
            raise ValueError("Missing bars container.")
        for name, bars in payload["bars"].items():
            if name != symbol:
                raise ValueError("Unexpected symbol.")
            for bar in bars:
                stamp = datetime.fromisoformat(bar["t"].replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    raise ValueError("Timezone required.")
                local = stamp.astimezone(NY)
                day = local.date().isoformat()
                if local.strftime("%H:%M:%S") != "00:00:00" or day in closes:
                    raise ValueError("Unexpected/duplicate bar session.")
                o, h, l, c, v = (float(bar[k]) for k in ("o", "h", "l", "c", "v"))
                if not all(math.isfinite(x) for x in (o, h, l, c, v)) or min(o, h, l, c) <= 0 or v < 0:
                    raise ValueError("Invalid OHLCV.")
                if not l <= min(o, c) <= max(o, c) <= h:
                    raise ValueError("Invalid OHLC ordering.")
                closes[day] = c
    if not closes:
        raise ValueError("No bars.")
    return dict(sorted(closes.items()))


def build_decisions(closes, *, days=20, fast=FAST, slow=SLOW):
    """One record per completed close; the last is pending (`session` is None).

    Record i is the position held from the open after close i, using closes up to
    and including i only.
    """
    dates = sorted(closes)
    if len(dates) < slow + 1:
        raise ValueError("Insufficient history for the slow EMA.")
    values = [closes[d] for d in dates]
    records = []
    for i in range(max(slow - 1, len(dates) - days), len(dates)):
        info = indicators(values[:i + 1], fast, slow)
        records.append({
            "record_origin": RECORD_ORIGIN, "signal_version": SIGNAL_VERSION,
            "observed_close_date": dates[i],
            "session": dates[i + 1] if i + 1 < len(dates) else None,
            "hypothetical_position": target_position(values[:i + 1], fast, slow),
            "fast_ema": round(info["fast_ema"], 6), "slow_ema": round(info["slow_ema"], 6),
            "bars_used": info["bars"]})
    for record in records:
        assert_shadow_record(record)
    return records


def assert_shadow_record(record):
    missing = [k for k in REQUIRED_FIELDS if k not in record]
    if missing:
        raise ValueError(f"Shadow record missing fields: {missing}")
    if record["record_origin"] != RECORD_ORIGIN:
        raise ValueError("Not a shadow record.")
    if FORBIDDEN_FIELDS & set(record):
        raise ValueError("Shadow records must not carry order fields.")
    if record["hypothetical_position"] not in (0, 1):
        raise ValueError("Hypothetical position must be 0 or 1.")


class DecisionStore:
    """Append-only-by-key JSONL keyed by observed close; reruns are idempotent."""

    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        if not self.path.exists():
            return {}
        rows = [json.loads(line) for line in self.path.read_text().splitlines() if line]
        keys = [r["observed_close_date"] for r in rows]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate keys in decision store.")
        return {r["observed_close_date"]: r for r in rows}

    def add(self, records):
        stored = self.load()
        counts = {"added": 0, "unchanged": 0, "resolved": 0}
        for record in records:
            assert_shadow_record(record)
            key = record["observed_close_date"]
            old = stored.get(key)
            if old is None:
                stored[key] = record
                counts["added"] += 1
            elif old == record:
                counts["unchanged"] += 1
            elif (old["session"] is None and record["session"] is not None
                  and {**old, "session": record["session"]} == record):
                stored[key] = record
                counts["resolved"] += 1
            else:
                raise ValueError(f"Conflicting shadow decision for {key}; refusing to rewrite history.")
        if counts["added"] or counts["resolved"]:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            text = "".join(json.dumps(stored[k], sort_keys=True, allow_nan=False) + "\n" for k in sorted(stored))
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(text)
            os.replace(tmp, self.path)
        return counts
