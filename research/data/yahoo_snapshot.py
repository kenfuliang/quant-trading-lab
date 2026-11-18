"""Yahoo chart raw snapshots: fetch once, receipt every request, never overwrite.

Parse rules follow research/spy_backtest.py:load_data (New York session dates, OHLC checks)
but are reimplemented here so the data layer imports nothing outside research/data.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from research.data.manifest import SCHEMA, sha256_file, write_manifest

USER_AGENT = "research-snapshot/1"
BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"
RIGHTS = {"source": "yahoo", "use": "private offline research only",
          "redistribution": "not permitted", "ruling": "owner 2026-11-17"}
TIMEOUT = 30


class SnapshotIncomplete(RuntimeError):
    """At least one symbol failed; the manifest and receipt were still written."""

    def __init__(self, message, snapshot_dir, failed):
        super().__init__(message)
        self.snapshot_dir = snapshot_dir
        self.failed = failed


def _epoch(day: str, plus_days: int = 0) -> int:
    d = date.fromisoformat(day) + timedelta(days=plus_days)
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


def chart_url(symbol: str, start: str, end: str) -> str:
    return (f"{BASE_URL}{symbol}?period1={_epoch(start)}&period2={_epoch(end, 1)}"
            "&interval=1d&events=div%2Csplits")


def _ny_date(epoch) -> str:
    return pd.Timestamp(epoch, unit="s", tz="UTC").tz_convert("America/New_York").strftime("%Y-%m-%d")


def parse_chart(raw: bytes, symbol: str):
    payload = json.loads(raw)["chart"]
    if payload.get("error"):
        raise ValueError(f"chart error: {payload['error']}")
    result = payload["result"][0]
    if result["meta"]["symbol"] != symbol:
        raise ValueError(f"Expected {symbol} data, got {result['meta']['symbol']}.")
    dates = pd.to_datetime(result["timestamp"], unit="s", utc=True).tz_convert("America/New_York").strftime("%Y-%m-%d")
    frame = pd.DataFrame(result["indicators"]["quote"][0], index=pd.Index(dates, name="date"))
    frame = frame[["open", "high", "low", "close", "volume"]]
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError("Dates must be unique and sorted.")
    if frame.isna().any().any() or not np.isfinite(frame.to_numpy()).all():
        raise ValueError("Missing or non-finite OHLCV data.")
    # A raw snapshot keeps zero-volume sessions (Yahoo has them, e.g. early XLRE); the
    # quality layer reports them. Prices must still be positive and volume non-negative.
    if (frame[["open", "high", "low", "close"]] <= 0).any().any() or (frame.volume < 0).any():
        raise ValueError("Prices must be positive and volume non-negative.")
    if ((frame.high < frame[["open", "close", "low"]].max(axis=1)) |
            (frame.low > frame[["open", "close", "high"]].min(axis=1))).any():
        raise ValueError("Invalid OHLC ordering.")
    events = result.get("events") or {}
    dividends = []
    for item in events.get("dividends", {}).values():
        if item["amount"] <= 0:
            raise ValueError("Invalid dividend amount.")
        dividends.append({"date": _ny_date(item["date"]), "amount": item["amount"]})
    splits = []
    for item in events.get("splits", {}).values():
        if item["numerator"] <= 0 or item["denominator"] <= 0:
            raise ValueError("Invalid split ratio.")
        splits.append({"date": _ny_date(item["date"]), "numerator": item["numerator"],
                       "denominator": item["denominator"], "ratio": item.get("splitRatio")})
    return frame, sorted(dividends, key=lambda e: e["date"]), sorted(splits, key=lambda e: e["date"])


def _write_receipt(path: Path, rows: list) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def _utc(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_snapshot(symbols, start, end, snapshot_id, root, opener=urllib.request.urlopen, now=None) -> Path:
    root = Path(root)
    folder = root / "raw" / "yahoo" / snapshot_id
    folder.parent.mkdir(parents=True, exist_ok=True)
    folder.mkdir(exist_ok=False)  # an existing snapshot id is refused
    receipt = folder / "requests.json"
    rows = []
    for attempt, symbol in enumerate(symbols, start=1):
        stamp = now if now is not None else datetime.now(timezone.utc)
        url = chart_url(symbol, start, end)
        row = {"attempt": attempt, "symbol": symbol, "url": url, "utc": _utc(stamp), "status": "reserved",
               "http_status": None, "bytes": None, "sha256": None, "error": None}
        rows.append(row)
        _write_receipt(receipt, rows)
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with opener(request, timeout=TIMEOUT) as response:
                row["http_status"] = getattr(response, "status", None)
                body = response.read()
            row["bytes"] = len(body)
            row["sha256"] = hashlib.sha256(body).hexdigest()
            if row["http_status"] != 200:
                raise ValueError(f"HTTP status {row['http_status']}")
            parse_chart(body, symbol)
        except Exception as error:  # recorded, never retried
            row["status"] = "failed"
            row["http_status"] = getattr(error, "code", row["http_status"])
            row["error"] = f"{type(error).__name__}: {error}"
        else:
            with open(folder / f"response-{symbol}.json", "xb") as handle:
                handle.write(body)
            row["status"] = "received"
        _write_receipt(receipt, rows)
    files = [{"path": f"raw/yahoo/{snapshot_id}/response-{r['symbol']}.json", "sha256": r["sha256"]}
             for r in rows if r["status"] == "received"]
    for entry in files:
        assert sha256_file(root / entry["path"]) == entry["sha256"]
    failed = [r["symbol"] for r in rows if r["status"] == "failed"]
    write_manifest(root, {
        "schema": SCHEMA, "dataset_id": snapshot_id, "kind": "raw-snapshot",
        "created_utc": _utc(now if now is not None else datetime.now(timezone.utc)),
        "source": f"Yahoo Finance chart endpoint {BASE_URL}<SYMBOL>, interval 1d, {start}..{end}",
        "inputs": [], "recipe": None, "rights": dict(RIGHTS), "files": files,
        "notes": f"requests.json is the request receipt; failed symbols: {failed or 'none'}",
    })
    if failed:
        raise SnapshotIncomplete(f"failed symbols: {', '.join(failed)}", folder, failed)
    return folder
