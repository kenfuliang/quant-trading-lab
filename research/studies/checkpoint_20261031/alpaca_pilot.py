"""Bounded, data-only Alpaca pilot and native catalog validation.

No trading client or SDK is installed. Original HTTP response bytes are retained;
the small stdlib transport exists because the screened SDK does not promise raw
wire-response preservation. Only the fixed historical-bars HTTPS route is used.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

from research.studies.checkpoint_20261031.us_etf_calendar import sessions

SYMBOLS = ("AAPL", "JPM", "MSFT", "SPY")
WINDOWS = (("2016-01-01", "2016-01-31"), ("2025-12-01", "2025-12-31"))
ENDPOINT = "https://data.alpaca.markets/v2/stocks/bars"
NY = ZoneInfo("America/New_York")
MAX_REQUESTS, MAX_BYTES, MAX_SECONDS = 20, 100_000_000, 600


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def credentials(env_file=None):
    """Read only named keys; never execute/source a shell file or print values."""
    values = dict(os.environ)
    if env_file:
        p = Path(env_file)
        if p.is_file():
            if p.stat().st_mode & 0o077:
                raise ValueError("Credential file must be owner-only (chmod 600).")
            for line in p.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                name, sep, value = line.partition("=")
                if sep and name.strip() in ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY"):
                    values[name.strip()] = value.strip().strip("\"'")
    key = values.get("APCA_API_KEY_ID", "")
    secret = values.get("APCA_API_SECRET_KEY", "")
    if not key or not secret:
        raise ValueError("Missing local Alpaca credentials; no HTTP request made.")
    if any(c.isspace() for c in key + secret):
        raise ValueError("Malformed local credentials; no HTTP request made.")
    return key, secret


def number(value, *, positive=False):
    if isinstance(value, bool):
        raise ValueError("Boolean market value.")
    try:
        d = Decimal(str(value))
    except InvalidOperation as e:
        raise ValueError("Malformed market value.") from e
    if not d.is_finite() or d < 0 or (positive and d == 0):
        raise ValueError("Nonfinite or invalid market value.")
    if d.normalize().as_tuple().exponent < -9:
        raise ValueError("Market value exceeds native encoding precision.")
    return format(d, "f")


def validate_pages(pages, windows=WINDOWS, symbols=SYMBOLS):
    """Exact per-symbol session coverage; no forward filling or repair."""
    expected = {d.strftime("%Y-%m-%d") for a, b in windows for d in sessions(a, b)}
    observed = {s: {} for s in symbols}
    for payload in pages:
        if not isinstance(payload, dict) or not isinstance(payload.get("bars"), dict):
            raise ValueError("Response is not a bars payload.")
        for symbol, bars in payload["bars"].items():
            if symbol not in observed or not isinstance(bars, list):
                raise ValueError("Unexpected instrument or bar container.")
            previous = None
            for raw in bars:
                if not isinstance(raw, dict):
                    raise ValueError("Invalid bar record.")
                try:
                    stamp = datetime.fromisoformat(raw["t"].replace("Z", "+00:00"))
                except (KeyError, TypeError, ValueError, AttributeError) as e:
                    raise ValueError("Invalid source timestamp.") from e
                if stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
                    raise ValueError("Source timestamps must be explicit UTC.")
                local = stamp.astimezone(NY)
                # Daily bars are session-start labelled. Never expose the day's
                # OHLC at midnight start or pretend they are regular-hours bars.
                if (local.hour, local.minute, local.second, local.microsecond) != (0, 0, 0, 0):
                    raise ValueError("Daily bar is not labelled at New York midnight.")
                day = local.date().isoformat()
                if day not in expected or day in observed[symbol]:
                    raise ValueError("Unexpected session or duplicate bar.")
                if previous is not None and stamp <= previous:
                    raise ValueError("Source page is not chronological per instrument.")
                previous = stamp
                fields = {k: number(raw.get(k), positive=(k != "v")) for k in ("o", "h", "l", "c", "v")}
                o, h, l, c = (Decimal(fields[k]) for k in ("o", "h", "l", "c"))
                if not l <= min(o, c) <= max(o, c) <= h:
                    raise ValueError("Invalid OHLC envelope.")
                # Conservative availability: next local midnight, after the
                # source-labelled calendar day. Actual publication time unknown.
                available = datetime.combine(local.date() + timedelta(days=1), datetime.min.time(), NY)
                ns = int(available.timestamp()) * 1_000_000_000
                observed[symbol][day] = {"symbol": symbol, "session": day,
                    "source_timestamp": raw["t"], "ts_event": ns, "ts_init": ns,
                    **fields}
    for symbol, rows in observed.items():
        if set(rows) != expected:
            raise ValueError(f"Incomplete session coverage for {symbol}: expected {len(expected)}, observed {len(rows)}.")
    return [observed[s][d] for s in symbols for d in sorted(expected)]


def native_objects(rows):
    from nautilus_trader.model.currencies import USD
    from nautilus_trader.model.data import Bar, BarType
    from nautilus_trader.model.identifiers import InstrumentId, Symbol
    from nautilus_trader.model.instruments import Equity
    from nautilus_trader.model.objects import Price, Quantity

    instruments, bars = [], []
    for symbol in sorted({r["symbol"] for r in rows}):
        selected = [r for r in rows if r["symbol"] == symbol]
        precision = max(2, max(max(0, -Decimal(r[k]).normalize().as_tuple().exponent)
                              for r in selected for k in ("o", "h", "l", "c")))
        identifier = InstrumentId.from_str(symbol + ".ALPACADATA")
        # ALPACADATA is a research namespace, not a real execution venue. The
        # increment is encoding resolution, not an asserted exchange tick rule.
        increment = Price.from_str(format(Decimal(1).scaleb(-precision), "f"))
        instruments.append(Equity(identifier, Symbol(symbol), USD, precision,
                                  increment, Quantity.from_int(1), 0, 0))
        bar_type = BarType.from_str(f"{identifier}-1-DAY-LAST-EXTERNAL")
        for row in selected:
            prices = [Price.from_str(format(Decimal(row[k]), f".{precision}f"))
                      for k in ("o", "h", "l", "c")]
            bars.append(Bar(bar_type, *prices, Quantity.from_str(row["v"]),
                            row["ts_event"], row["ts_init"]))
    return instruments, bars


def bar_signature(bar):
    return (str(bar.bar_type), *(Decimal(str(getattr(bar, k))) for k in
            ("open", "high", "low", "close", "volume")), bar.ts_event, bar.ts_init)


def catalog_import(rows, destination):
    """Publish only an exact native round-trip. Existing identical import is read-only."""
    from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

    destination = Path(destination)
    identities, bars = native_objects(rows)
    expected = sorted(bar_signature(b) for b in bars)
    expected_instruments = sorted([i.to_dict(i) for i in identities], key=lambda x: x['id'])
    if destination.exists():
        cat = ParquetDataCatalog(str(destination.resolve()))
        actual = sorted(bar_signature(b) for b in cat.bars())
        actual_instruments = sorted([i.to_dict(i) for i in cat.instruments()], key=lambda x: x['id'])
        if actual != expected or actual_instruments != expected_instruments:
            raise ValueError("Existing catalog differs; preserved without writing.")
        return {"status": "identical_read_only", "bars": len(bars), "instruments": len(identities)}
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.with_name(destination.name + ".staging")
    staging.mkdir(exist_ok=False)
    cat = ParquetDataCatalog(str(staging.resolve()))
    cat.write_data(identities)
    cat.write_data(bars)
    if sorted(bar_signature(b) for b in cat.bars()) != expected:
        raise ValueError("Native catalog round-trip differs; staging preserved.")
    if sorted([i.to_dict(i) for i in cat.instruments()], key=lambda x: x['id']) != expected_instruments:
        raise ValueError("Native instrument round-trip differs; staging preserved.")
    staging.rename(destination)
    return {"status": "written_and_verified", "bars": len(bars), "instruments": len(identities)}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirect refused; credentials were not forwarded.")


def acquire(raw_dir, auth, *, request_limit=MAX_REQUESTS):
    """Fetch only fixed samples. Failures are persisted without body/credential logging."""
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=False)
    started, count, total = time.monotonic(), 0, 0
    pages, requests = [], []
    opener = urllib.request.build_opener(NoRedirect())
    for start, end in WINDOWS:
        token, seen_tokens = None, set()
        while True:
            remaining = MAX_SECONDS - (time.monotonic() - started)
            if count >= request_limit or remaining <= 0 or total >= MAX_BYTES:
                raise ValueError("Pilot acquisition budget exhausted; raw evidence preserved.")
            params = {"symbols": ",".join(SYMBOLS), "timeframe": "1Day",
                "start": start + "T00:00:00-05:00", "end": end + "T23:59:59-05:00",
                "feed": "sip", "adjustment": "raw", "asof": "2025-12-31",
                "currency": "USD", "sort": "asc", "limit": "10000"}
            if token:
                params["page_token"] = token
            count += 1
            record = {"attempt": count, "endpoint": ENDPOINT, "window": [start, end],
                      "feed": "sip", "adjustment": "raw", "paginated": bool(token),
                      "utc": datetime.now(timezone.utc).isoformat(), "status": "reserved"}
            requests.append(record)
            save_json(raw_dir / "requests.json", requests)
            req = urllib.request.Request(ENDPOINT + "?" + urllib.parse.urlencode(params),
                headers={"APCA-API-KEY-ID": auth[0], "APCA-API-SECRET-KEY": auth[1],
                         "Accept": "application/json"})
            try:
                with opener.open(req, timeout=min(25, remaining)) as response:
                    payload = response.read(min(MAX_BYTES - total, 10_000_000) + 1)
                    if len(payload) > min(MAX_BYTES - total, 10_000_000):
                        (raw_dir / f"response-{count:02d}-partial.bin").write_bytes(payload)
                        raise ValueError("Response size cap exceeded.")
                    total += len(payload)
                    path = raw_dir / f"response-{count:02d}.json"
                    path.write_bytes(payload)
                    record.update(status="received", bytes=len(payload), sha256=digest(path),
                                  http_status=response.status, content_type=response.headers.get("Content-Type", ""))
                    save_json(raw_dir / "requests.json", requests)
                    obj = json.loads(payload, parse_float=Decimal)
                    pages.append(obj)
            except Exception as error:
                # Never print str(error), response headers, URLs or returned error
                # bodies: they can contain credentials or account-specific data.
                record.update(status="failed", error_type=type(error).__name__)
                if isinstance(error, urllib.error.HTTPError):
                    record["http_status"] = error.code
                save_json(raw_dir / "requests.json", requests)
                raise ValueError(f"Historical-data request {count} failed; see redacted receipt.") from None
            token = obj.get("next_page_token") if isinstance(obj, dict) else None
            if not token:
                break
            if not isinstance(token, str) or token in seen_tokens:
                raise ValueError("Invalid or repeated pagination token.")
            seen_tokens.add(token)
            time.sleep(0.5)
        time.sleep(0.5)
    return pages, {"attempts": count, "bytes": total, "elapsed_seconds": time.monotonic() - started}


def synthetic_proof(root):
    """No market data or engine simulation: native storage proof only."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    bars = {s: [{"t": "2016-01-04T05:00:00Z", "o": "100.1234", "h": "102.25",
                "l": "99.5", "c": "101.1", "v": "12345.25"}] for s in SYMBOLS}
    rows = validate_pages([{"bars": bars}], (("2016-01-04", "2016-01-04"),))
    save_json(root / "synthetic-normalized.json", rows)
    result = catalog_import(rows, root / "catalog")
    repeated = catalog_import(rows, root / "catalog")
    shutil.copytree(root / "catalog", root / "restored-catalog")
    restored = catalog_import(rows, root / "restored-catalog")
    receipt = {"data_kind": "synthetic_not_alpaca", "first": result,
               "repeat": repeated, "restore": restored}
    save_json(root / "proof.json", receipt)
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("check-access", "synthetic", "download"))
    p.add_argument("--env-file", default=".env.alpaca")
    p.add_argument("--root", default="data")
    p.add_argument("--id", default="alpaca-pilot-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    args = p.parse_args()
    if Path(args.id).name != args.id or args.id in (".", ".."):
        p.error("Dataset id must be one directory name.")
    root = Path(args.root)
    if args.command == "synthetic":
        print(json.dumps(synthetic_proof(root / "synthetic" / args.id)))
        return 0
    try:
        auth = credentials(args.env_file)
    except ValueError as e:
        print(str(e))
        return 2
    if args.command == "check-access":
        print("Local credentials present; provider authentication and entitlements not tested.")
        return 0
    manifest_path = root / "manifests" / (args.id + ".json")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": "alpaca-pilot-v1", "status": "in_progress", "symbols": SYMBOLS,
        "windows": WINDOWS, "feed": "sip", "adjustment": "raw", "asof": "2025-12-31",
        "scope": "private price diagnostics only", "redistribution": "not_qualified",
        "corporate_actions": "not_acquired", "point_in_time_universe": "not_qualified",
        "financial_comparison_eligible": False,
        "implementation_sha256": digest(__file__), "calendar_sha256": digest(Path(__file__).with_name("us_etf_calendar.py"))}
    with manifest_path.open("x") as f:
        json.dump(manifest, f, indent=2)
    try:
        pages, receipt = acquire(root / "raw" / "alpaca" / args.id, auth)
        rows = validate_pages(pages)
        normalized = root / "normalized" / (args.id + ".json")
        normalized.parent.mkdir(parents=True, exist_ok=True)
        save_json(normalized, rows)
        catalog = root / "catalog" / args.id
        result = catalog_import(rows, catalog)
        catalog_import(rows, catalog)  # read-only duplicate verification
        files = [normalized, *(root / "raw" / "alpaca" / args.id).rglob("*"), *catalog.rglob("*")]
        manifest.update(status="structural_pass_financial_use_blocked", acquisition=receipt,
            catalog=str(catalog), round_trip=result, rows=len(rows),
            bar_timestamp_policy="next New York midnight; source publication time unknown; daily session scope not asserted RTH",
            identity_policy="ALPACADATA research namespace; encoding increment is not a trading tick rule",
            files={str(f): digest(f) for f in files if f.is_file()})
    except Exception as e:
        manifest.update(status="failed_preserved", error_type=type(e).__name__)
        print("Pilot stopped; source evidence and failure receipt preserved.")
        return 1
    finally:
        save_json(manifest_path, manifest)
    print(json.dumps({"status": manifest["status"], "rows": manifest["rows"], "manifest": str(manifest_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
