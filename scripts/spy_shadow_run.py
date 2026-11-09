#!/usr/bin/env python3
"""SPY shadow run: collect daily bars read-only, record hypothetical positions.

GET-only. No order client, side, quantity or client id exists in this path.
Offline mode (--bars-json) reads saved Alpaca-style pages; --fetch makes the
bounded read-only collection. Output stays under ignored .local/shadow/<UTC>/.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from paper_trading.shadow import DecisionStore, build_decisions, parse_spy_closes
from paper_trading.tracking_error import tracking_error
from paper_trading.spy_signal import FAST, SLOW

NY = ZoneInfo("America/New_York")
BARS_ENDPOINT = ("https://data.alpaca.markets", "/v2/stocks/bars")
MAX_REQUESTS, MAX_BYTES, MAX_SECONDS = 6, 8_000_000, 90


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def fetch_pages(now, key, secret, opener):
    """Bounded GET collection of raw SPY daily bars; returns (pages, request_count)."""
    if now.astimezone(NY).hour < 21:
        raise SystemExit("Read-only shadow collection requires after 21:00 NY to exclude incomplete daily bars.")
    params = {"symbols": "SPY", "timeframe": "1Day", "adjustment": "raw", "feed": "sip", "sort": "asc",
              "start": (now - timedelta(days=450)).astimezone(NY).date().isoformat(),
              "end": (now - timedelta(minutes=20)).isoformat(), "limit": 10000}
    pages, tokens, spent, size, started = [], set(), 0, 0, time.monotonic()
    while True:
        if spent >= MAX_REQUESTS or time.monotonic() - started > MAX_SECONDS:
            raise ValueError("Request/time budget exhausted.")
        spent += 1
        request = urllib.request.Request(BARS_ENDPOINT[0] + BARS_ENDPOINT[1] + "?" + urllib.parse.urlencode(params),
                                         method="GET", headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret})
        with opener.open(request, timeout=15) as response:
            raw = response.read(2_000_001)
        size += len(raw)
        if len(raw) > 2_000_000 or size > MAX_BYTES:
            raise ValueError("Response/byte budget exhausted.")
        payload = json.loads(raw)
        pages.append(payload)
        token = payload.get("next_page_token")
        if not token:
            return pages, spent
        if token in tokens:
            raise ValueError("Pagination token repeated.")
        tokens.add(token)
        params["page_token"] = token


def run(pages, replay_rows, local_root, now, *, days=20, source="offline", requests=0, fast=FAST, slow=SLOW):
    """Compute decisions, join to replay, write the run directory. Returns the summary."""
    local_root = Path(local_root)
    run_dir = local_root / now.strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
    plan = {"mode": "shadow_decisions_read_only", "created_utc": now.isoformat(), "source": source,
            "signal": {"fast": fast, "slow": slow}, "days": days, "orders": 0,
            "allowed_endpoints": ["GET " + BARS_ENDPOINT[0] + BARS_ENDPOINT[1]],
            "max_requests": MAX_REQUESTS, "max_bytes": MAX_BYTES, "max_seconds": MAX_SECONDS, "retries": 0,
            "code_sha256": {p: sha256(ROOT / p) for p in
                            ("scripts/spy_shadow_run.py", "paper_trading/shadow.py",
                             "paper_trading/tracking_error.py", "paper_trading/spy_signal.py")}}
    save(run_dir / "plan.json", plan)
    summary = {"status": "started", "broker_submissions": 0, "requests": requests}
    try:
        closes = parse_spy_closes(pages)
        decisions = build_decisions(closes, days=days, fast=fast, slow=slow)
        summary["store"] = DecisionStore(local_root / "decisions.jsonl").add(decisions)
        (run_dir / "decisions.jsonl").write_text(
            "".join(json.dumps(d, sort_keys=True, allow_nan=False) + "\n" for d in decisions))
        summary.update(last_close=decisions[-1]["observed_close_date"], decisions=len(decisions),
                       pending_position=decisions[-1]["hypothetical_position"])
        if replay_rows is None:
            summary["tracking"] = {"status": "not_run"}
            summary["status"] = "completed_no_replay"
        else:
            report = tracking_error(decisions, replay_rows)
            save(run_dir / "tracking_error.json", report)
            summary["tracking"] = {k: report[k] for k in ("status", "compared_days", "tracking_error")} | {
                "mismatch_days": len(report["mismatch_days"]),
                "missing_in_shadow": len(report["missing_in_shadow"]),
                "missing_in_replay": len(report["missing_in_replay"])}
            summary["status"] = "completed" if report["status"] == "ok" else "completed_flagged"
    except Exception as exc:
        summary.update(status="failed_preserved", error_type=type(exc).__name__)
    finally:
        save(run_dir / "summary.json", summary)
        save(run_dir / "manifest.json", {"files": {p.name: sha256(p) for p in sorted(run_dir.iterdir())
                                                   if p.is_file() and p.name != "manifest.json"}})
    summary["run_dir"] = str(run_dir)
    return summary


def redacted_summary(summary):
    """Counts and flags only: no prices, EMAs or paths."""
    keep = {k: summary[k] for k in ("status", "decisions", "broker_submissions", "requests") if k in summary}
    return keep | {"tracking": summary.get("tracking"), "store": summary.get("store")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bars-json", type=Path, nargs="*", default=[], help="saved Alpaca-style bar pages (offline)")
    parser.add_argument("--fetch", action="store_true", help="bounded read-only GET collection")
    parser.add_argument("--replay", type=Path, help="shadow_replay.py output to join against")
    parser.add_argument("--days", type=int, default=20)
    parser.add_argument("--local-root", type=Path, default=ROOT / ".local/shadow")
    parser.add_argument("--redacted-summary", type=Path, help="write counts-only summary (safe to track)")
    args = parser.parse_args()
    if bool(args.bars_json) == args.fetch:
        parser.error("Give either --bars-json files or --fetch.")
    now = datetime.now(timezone.utc)
    requests = 0
    if args.fetch:
        from research.studies.checkpoint_20261031.alpaca_pilot import NoRedirect, credentials
        key, secret = credentials(ROOT / ".env.alpaca")
        pages, requests = fetch_pages(now, key, secret, urllib.request.build_opener(NoRedirect()))
        source = "alpaca_data_get"
    else:
        pages, source = [json.loads(p.read_text()) for p in args.bars_json], "offline_saved_pages"
    replay = json.loads(args.replay.read_text())["rows"] if args.replay else None
    summary = run(pages, replay, args.local_root, now, days=args.days, source=source, requests=requests)
    if args.redacted_summary:
        save(args.redacted_summary, redacted_summary(summary))
    print(json.dumps({"status": summary["status"], "run_dir": summary["run_dir"], "orders": 0}))
    return 0 if summary["status"].startswith("completed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
