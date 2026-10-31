"""Bounded current-SPY-holdings raw price archive, not a historical universe."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from research.alpaca_pilot import ENDPOINT, NoRedirect, credentials, digest, number, save_json, native_objects, bar_signature
from research.us_etf_calendar import sessions

START, END = "2016-01-01", "2025-12-31"
NY = ZoneInfo("America/New_York")
REQUEST_LIMIT, BYTE_LIMIT, TIME_LIMIT = 240, 250_000_000, 900
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def parse_holdings(path):
    with zipfile.ZipFile(path) as z:
        strings = ["".join(e.itertext()) for e in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("s:si", NS)]
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    records, excluded, date, fund, header = [], [], None, None, False
    for row in sheet.findall(".//s:sheetData/s:row", NS):
        vals = {}
        for cell in row.findall("s:c", NS):
            v = cell.find("s:v", NS)
            value = v.text if v is not None else ""
            vals["".join(c for c in cell.get("r") if c.isalpha())] = strings[int(value)] if cell.get("t") == "s" and value else value
        if vals.get("A") == "Ticker Symbol:":
            fund = vals.get("B")
        if vals.get("A") == "Holdings:":
            date = datetime.strptime(vals["B"].removeprefix("As of "), "%d-%b-%Y").date().isoformat()
        if vals.get("A") == "Name" and vals.get("B") == "Ticker" and vals.get("C") == "Identifier":
            header = True
            continue
        if not header or vals.get("H") != "USD" or not vals.get("G"):
            continue
        record = {"symbol": vals.get("B", ""), "name": vals.get("A", ""),
                  "issuer_identifier": vals.get("C", ""), "currency": vals["H"]}
        if not re.fullmatch(r"[A-Z]{1,5}(?:\.[A-Z])?", record["symbol"]):
            record["reason"] = "cash" if record["symbol"] == "-" else "nonstandard_instrument_identity_unqualified"
            excluded.append(record)
        else:
            if not re.fullmatch(r"[A-Z0-9]{9}", record["issuer_identifier"]):
                raise ValueError("Holding lacks an expected issuer identifier.")
            records.append(record)
    symbols = [r["symbol"] for r in records]
    if fund != "SPY" or not date or not header or not records or len(symbols) != len(set(symbols)):
        raise ValueError("Invalid/duplicate or wrong-fund holdings universe.")
    return {"holdings_asof": date, "fund": fund, "equities": sorted(records, key=lambda r: r["symbol"]),
            "excluded": excluded, "kind": "current_SPY_equity_holdings_proxy_not_historical_membership",
            "issuer_file_sha256": digest(path)}


def validate_symbol(symbol, raw, expected):
    if not raw:
        return [], {"symbol": symbol, "status": "unavailable", "observed_rows": 0}
    seen, result, previous = set(), [], None
    for record in raw:
        stamp = datetime.fromisoformat(record["t"].replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
            raise ValueError("Timestamp must be explicit UTC.")
        local = stamp.astimezone(NY)
        day = local.date().isoformat()
        if local.time().isoformat() != "00:00:00" or day not in expected or day in seen or (previous and stamp <= previous):
            raise ValueError("Invalid, duplicate or nonchronological session.")
        previous = stamp
        seen.add(day)
        vals = {k: number(record.get(k), positive=k != "v") for k in ("o", "h", "l", "c", "v")}
        o, h, l, c = (Decimal(vals[k]) for k in ("o", "h", "l", "c"))
        if not l <= min(o, c) <= max(o, c) <= h:
            raise ValueError("Invalid OHLC envelope.")
        available = datetime.combine(local.date() + timedelta(days=1), datetime.min.time(), NY)
        ns = int(available.timestamp()) * 1_000_000_000
        result.append({"symbol": symbol, "session": day, "source_timestamp": record["t"],
                       "ts_event": ns, "ts_init": ns, **vals})
    first, last = min(seen), max(seen)
    interior = sorted(d for d in expected if first <= d <= last and d not in seen)
    receipt = {"symbol": symbol, "observed_rows": len(result), "first": first, "last": last,
        "leading_missing_sessions": sum(d < first for d in expected),
        "trailing_missing_sessions": sum(d > last for d in expected),
        "interior_missing_sessions": interior,
        "status": "quarantined_interior_gaps" if interior else ("structural_full_window" if seen == expected else "structural_partial_window"),
        "listing_dates_inferred": False}
    return ([] if interior else result), receipt


def append_catalog(rows, destination):
    from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog
    catalog = ParquetDataCatalog(str(Path(destination).resolve()))
    instruments, bars = native_objects(rows)
    ids = [str(i.id) for i in instruments]
    if catalog.instruments(instrument_ids=ids):
        raise ValueError("Duplicate instrument write rejected; staging preserved.")
    catalog.write_data(instruments)
    catalog.write_data(bars)
    if sorted(bar_signature(b) for b in catalog.bars(instrument_ids=ids)) != sorted(bar_signature(b) for b in bars):
        raise ValueError("Native batch read-back differs.")
    if sorted([i.to_dict(i) for i in catalog.instruments(instrument_ids=ids)], key=lambda x: x["id"]) != sorted([i.to_dict(i) for i in instruments], key=lambda x: x["id"]):
        raise ValueError("Native instrument metadata differs.")
    return len(bars)


class Downloader:
    def __init__(self, root, auth, mapping_date, request_limit=REQUEST_LIMIT):
        self.root, self.auth, self.mapping_date = Path(root), auth, mapping_date
        self.limit = min(request_limit, REQUEST_LIMIT)
        self.count, self.bytes, self.started = 0, 0, time.monotonic()
        self.records = []
        self.opener = urllib.request.build_opener(NoRedirect())
        self.root.mkdir(parents=True, exist_ok=False)

    def batch(self, symbols, batch_number):
        rows = {s: [] for s in symbols}
        token, tokens = None, set()
        while True:
            remaining = TIME_LIMIT - (time.monotonic() - self.started)
            if self.count >= self.limit or self.bytes >= BYTE_LIMIT or remaining <= 0:
                raise ValueError("Acquisition bound reached.")
            params = {"symbols": ",".join(symbols), "timeframe": "1Day", "start": START + "T00:00:00-05:00",
                      "end": END + "T23:59:59-05:00", "feed": "sip", "adjustment": "raw", "currency": "USD",
                      "asof": self.mapping_date, "sort": "asc", "limit": "10000"}
            if token:
                params["page_token"] = token
            self.count += 1
            row = {"attempt": self.count, "batch": batch_number, "symbols": symbols,
                   "parameters": {k: v for k, v in params.items() if k != "page_token"},
                   "page_token_sha256": __import__("hashlib").sha256(token.encode()).hexdigest() if token else None,
                   "utc": datetime.now(timezone.utc).isoformat(), "status": "reserved"}
            self.records.append(row)
            save_json(self.root / "requests.json", self.records)
            request = urllib.request.Request(ENDPOINT + "?" + urllib.parse.urlencode(params),
                headers={"APCA-API-KEY-ID": self.auth[0], "APCA-API-SECRET-KEY": self.auth[1], "Accept": "application/json"})
            try:
                with self.opener.open(request, timeout=min(25, remaining)) as response:
                    size = min(10_000_000, BYTE_LIMIT - self.bytes)
                    payload = response.read(size + 1)
                    path = self.root / f"response-{self.count:03d}.json"
                    path.write_bytes(payload)
                    self.bytes += len(payload)
                    row.update(status="received", bytes=len(payload), sha256=digest(path), http_status=response.status)
                    save_json(self.root / "requests.json", self.records)
                    if len(payload) > size:
                        raise ValueError("Response exceeded size bound; partial bytes preserved.")
                    obj = json.loads(payload, parse_float=Decimal)
                if not isinstance(obj.get("bars"), dict):
                    raise ValueError("Unexpected provider response.")
                for s, records in obj["bars"].items():
                    if s not in rows or not isinstance(records, list):
                        raise ValueError("Unexpected source instrument.")
                    rows[s].extend(records)
                token = obj.get("next_page_token")
                if token and (not isinstance(token, str) or token in tokens):
                    raise ValueError("Invalid/repeated pagination token.")
                if token:
                    tokens.add(token)
            except Exception as error:
                row.update(status="failed", error_type=type(error).__name__)
                if isinstance(error, urllib.error.HTTPError):
                    row["http_status"] = error.code
                save_json(self.root / "requests.json", self.records)
                raise ValueError(f"Acquisition stopped at attempt {self.count}; see redacted receipt.") from None
            time.sleep(.5)
            if not token:
                return rows


def run(source, dataset_id, root=Path("data")):
    if Path(dataset_id).name != dataset_id or dataset_id in (".", ".."):
        raise ValueError("Invalid dataset identifier.")
    root = Path(root)
    manifest_path = root / "manifests" / (dataset_id + ".json")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    universe = parse_holdings(source)
    if not 490 <= len(universe["equities"]) <= 510:
        raise ValueError("Unexpected equity count for this fixed universe scope.")
    auth = credentials(".env.alpaca")
    manifest = {"schema": "current-spy-stock-library-v1", "dataset_id": dataset_id, "status": "in_progress",
        "start": START, "end": END, "universe": universe, "source_file": str(source),
        "universe_source_url": "https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx",
        "financial_comparison_eligible": False, "redistribution": "not_qualified", "corporate_actions": "not_acquired",
        "code_sha256": digest(__file__), "pilot_helper_sha256": digest(Path(__file__).with_name("alpaca_pilot.py")),
        "calendar_sha256": digest(Path(__file__).with_name("us_etf_calendar.py")),
        "source_mapping_asof": universe["holdings_asof"], "quality": [], "rows_cataloged": 0,
        "limits": {"requests": REQUEST_LIMIT, "bytes": BYTE_LIMIT, "acquisition_seconds": TIME_LIMIT}}
    with manifest_path.open("x") as f:
        json.dump(manifest, f, indent=2)
    staging, published = root / "catalog" / (dataset_id + ".staging"), root / "catalog" / dataset_id
    normalized = root / "normalized" / dataset_id
    normalized.mkdir(parents=True, exist_ok=False)
    staging.mkdir(parents=True, exist_ok=False)
    manifest["source_snapshots"] = {}
    for path in [Path(__file__), Path(__file__).with_name("alpaca_pilot.py"), Path(__file__).with_name("us_etf_calendar.py")]:
        target = normalized / (path.name + ".source")
        target.write_bytes(path.read_bytes())
        manifest["source_snapshots"][str(target)] = digest(target)
    downloader = Downloader(root / "raw" / "alpaca" / dataset_id, auth, universe["holdings_asof"])
    expected = {d.strftime("%Y-%m-%d") for d in sessions(START, END)}
    manifest["expected_window_sessions"] = len(expected)
    symbols = [r["symbol"] for r in universe["equities"]]
    try:
        for batch_n, index in enumerate(range(0, len(symbols), 20), 1):
            subset = symbols[index:index + 20]
            source_rows = downloader.batch(subset, batch_n)
            accepted = []
            for symbol in subset:
                try:
                    rows, quality = validate_symbol(symbol, source_rows[symbol], expected)
                except Exception as e:
                    rows, quality = [], {"symbol": symbol, "status": "quarantined_invalid", "error_type": type(e).__name__, "observed_rows": len(source_rows[symbol])}
                manifest["quality"].append(quality)
                if rows:
                    save_json(normalized / (symbol + ".json"), rows)
                    accepted.extend(rows)
            if accepted:
                manifest["rows_cataloged"] += append_catalog(accepted, staging)
            manifest.update(http_attempts=downloader.count, response_bytes=downloader.bytes,
                            elapsed_seconds=time.monotonic() - downloader.started)
            save_json(manifest_path, manifest)
            print(json.dumps({"batch": batch_n, "processed": len(manifest["quality"]), "of": len(symbols),
                              "rows_cataloged": manifest["rows_cataloged"], "requests": downloader.count}), flush=True)
        from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog
        native = ParquetDataCatalog(str(staging.resolve()))
        accepted_symbols = {q["symbol"] for q in manifest["quality"] if q["status"].startswith("structural_")}
        if {str(i.raw_symbol) for i in native.instruments()} != accepted_symbols:
            raise ValueError("Final catalog instrument identities differ.")
        if len(manifest["quality"]) != len(symbols):
            raise ValueError("Some universe instruments were not processed.")
        staging.rename(published)
        files = [Path(source), *normalized.rglob("*"), *downloader.root.rglob("*"), *published.rglob("*")]
        manifest.update(status="acquisition_complete_conditional_price_data", catalog=str(published),
            instruments_cataloged=len(accepted_symbols), artifacts={str(p): digest(p) for p in files if p.is_file()},
            timestamp_policy="next_New_York_midnight_source_publication_time_unknown",
            note="Partial availability does not establish listing dates. Current membership is survivor-selected. No actions or financial comparison qualification.")
    except Exception as error:
        manifest.update(status="failed_preserved", error_type=type(error).__name__, http_attempts=downloader.count,
                        response_bytes=downloader.bytes, elapsed_seconds=time.monotonic() - downloader.started)
        raise
    finally:
        save_json(manifest_path, manifest)
    return manifest_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="data/raw/universe/sp500-20261025/holdings.xlsx")
    parser.add_argument("--id", required=True)
    args = parser.parse_args()
    print(run(args.source, args.id))
