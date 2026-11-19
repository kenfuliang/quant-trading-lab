"""Yahoo chart raw snapshots: fetch once, receipt every request, never overwrite.

Parse rules follow research/spy_backtest.py:load_data (New York session dates, OHLC checks)
but are reimplemented here so the data layer imports nothing outside research/data.
"""
from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from research.data.manifest import SCHEMA, ManifestError, check_dataset_id, sha256_file, write_manifest

USER_AGENT = "research-snapshot/1"
BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"
RIGHTS = {"source": "yahoo", "use": "private offline research only",
          "redistribution": "not permitted", "ruling": "owner 2026-11-17"}
# Stock set ruling: private offline research only, not redistributed (owner 2026-11-18).
STOCK_RIGHTS = {"source": "yahoo", "use": "private offline research only",
                "redistribution": "not permitted", "ruling": "owner 2026-11-18",
                "scope": "stock symbols of the S&P 500 archive, 2016-2025"}
TIMEOUT = 30
SYMBOL_RE = re.compile(r"[A-Z][A-Z0-9.\-]{0,9}")


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


def fetch_snapshot(symbols, start, end, snapshot_id, root, opener=urllib.request.urlopen, now=None,
                   *, rights=None, symbol_map=None, pause=0, sleep=time.sleep,
                   max_consecutive_http_failures=None, notes_extra="") -> Path:
    """Fetch every symbol once. ``symbol_map`` maps a key symbol to the symbol requested from Yahoo;
    files and receipts are keyed by the key symbol. ``pause`` seconds separate requests. After
    ``max_consecutive_http_failures`` HTTP error statuses in a row the run stops; remaining symbols
    are recorded as ``not_attempted``. Nothing is retried."""
    root = Path(root)
    symbol_map = dict(symbol_map or {})
    check_dataset_id(snapshot_id)
    symbols = list(symbols)
    for symbol in symbols:
        if not isinstance(symbol, str) or not SYMBOL_RE.fullmatch(symbol):
            raise ValueError(f"invalid symbol: {symbol!r}")
    if len(set(symbols)) != len(symbols):
        raise ValueError(f"duplicate symbols: {sorted({s for s in symbols if symbols.count(s) > 1})}")
    manifest_path = root / "manifests" / f"{snapshot_id}.json"
    if manifest_path.exists():
        raise FileExistsError(errno.EEXIST, "manifest already exists", str(manifest_path))
    folder = root / "raw" / "yahoo" / snapshot_id
    folder.parent.mkdir(parents=True, exist_ok=True)
    folder.mkdir(exist_ok=False)  # an existing snapshot id is refused
    receipt = folder / "requests.json"
    rows = []
    consecutive, stopped = 0, False
    for attempt, symbol in enumerate(symbols, start=1):
        if stopped:
            rows.append({"attempt": attempt, "symbol": symbol, "url": None, "utc": None,
                         "status": "not_attempted", "http_status": None, "bytes": None, "sha256": None,
                         "error": "run stopped after consecutive HTTP failures", "rejected": None})
            continue
        if attempt > 1 and pause:
            sleep(pause)
        stamp = now if now is not None else datetime.now(timezone.utc)
        requested = symbol_map.get(symbol, symbol)
        url = chart_url(requested, start, end)
        row = {"attempt": attempt, "symbol": symbol, "request_symbol": requested, "url": url, "utc": _utc(stamp), "status": "reserved",
               "http_status": None, "bytes": None, "sha256": None, "error": None, "rejected": None}
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
            try:
                parse_chart(body, requested)
            except Exception:
                # keep the provider's unedited body as evidence, outside the manifest files
                with open(folder / f"rejected-{symbol}.json", "xb") as handle:
                    handle.write(body)
                row["rejected"] = f"raw/yahoo/{snapshot_id}/rejected-{symbol}.json"
                raise
        except Exception as error:  # recorded, never retried
            row["status"] = "failed"
            row["http_status"] = getattr(error, "code", row["http_status"])
            row["error"] = f"{type(error).__name__}: {error}"
            consecutive += 1  # HTTP statuses, URL errors, timeouts and rejected bodies all count
            if max_consecutive_http_failures and consecutive >= max_consecutive_http_failures:
                stopped = True
        else:
            consecutive = 0
            with open(folder / f"response-{symbol}.json", "xb") as handle:
                handle.write(body)
            row["status"] = "received"
        _write_receipt(receipt, rows)
    _write_receipt(receipt, rows)
    files = [{"path": f"raw/yahoo/{snapshot_id}/response-{r['symbol']}.json", "sha256": r["sha256"]}
             for r in rows if r["status"] == "received"]
    for entry in files:
        if sha256_file(root / entry["path"]) != entry["sha256"]:
            raise ManifestError(f"{entry['path']}: sha256 mismatch after write")
    failed = [r["symbol"] for r in rows if r["status"] in ("failed", "not_attempted")]
    skipped = [r["symbol"] for r in rows if r["status"] == "not_attempted"]
    stop_note = (f"; stopped after {max_consecutive_http_failures} consecutive HTTP failures, "
                 f"{len(skipped)} symbols not attempted" if skipped else "")
    write_manifest(root, {
        "schema": SCHEMA, "dataset_id": snapshot_id, "kind": "raw-snapshot",
        "created_utc": _utc(now if now is not None else datetime.now(timezone.utc)),
        "source": f"Yahoo Finance chart endpoint {BASE_URL}<SYMBOL>, interval 1d, {start}..{end}",
        "inputs": [], "recipe": None, "rights": dict(rights or RIGHTS), "files": files,
        "notes": f"requests.json is the request receipt; failed symbols: {failed or 'none'}"
                 f"{stop_note}{notes_extra}",
    })
    if failed:
        raise SnapshotIncomplete(f"failed symbols: {', '.join(failed)}", folder, failed)
    return folder
