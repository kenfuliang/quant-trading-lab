#!/usr/bin/env python3
"""Run an offline native fixture, read-only preflight, or bounded paper session."""
import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.parse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.alpaca_pilot import digest, number
from paper_trading.alpaca import AlpacaPaperHTTP, PaperError, check_quote, save
from paper_trading.alpaca_native import Context, started_node, stop_node
from paper_trading.alpaca_fixture import native_fixture
from nautilus_trader.model.data import Bar, QuoteTick
from nautilus_trader.model.objects import Price, Quantity
from research.spy_backtest import BAR_TYPE, INSTRUMENT_ID

NY = ZoneInfo("America/New_York")
RUNS = ROOT / ".local/alpaca-paper/runs"


def history_bars(payload, calendar, last_day):
    """Validate explicit broker calendar coverage; only completed daily bars."""
    rows = payload.get("bars")
    if not isinstance(rows, list) or payload.get("next_page_token"):
        raise PaperError("Warmup is incomplete or paginated.")
    expected = {r["date"] for r in calendar if r["date"] < last_day}
    seen, result = set(), []
    previous = None
    for row in rows:
        stamp = datetime.fromisoformat(row["t"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise PaperError("Warmup timestamps lack timezone.")
        local = stamp.astimezone(NY)
        day = local.date().isoformat()
        if local.time().isoformat() != "00:00:00" or day not in expected or day in seen or (previous and stamp <= previous):
            raise PaperError("Invalid, duplicate or incomplete warmup sessions.")
        previous = stamp
        seen.add(day)
        vals = {k: Decimal(number(row[k], positive=(k != "v"))) for k in ("o", "h", "l", "c", "v")}
        if not vals["l"] <= min(vals["o"], vals["c"]) <= max(vals["o"], vals["c"]) <= vals["h"]:
            raise PaperError("Invalid warmup OHLC.")
        available = datetime.combine(local.date() + timedelta(days=1), datetime.min.time(), NY)
        ns = int(available.timestamp()) * 1_000_000_000
        prices = [Price.from_str(str(vals[k].quantize(Decimal("0.01")))) for k in ("o", "h", "l", "c")]
        result.append(Bar(BAR_TYPE, *prices, Quantity.from_str(str(vals["v"])), ns, ns))
    if seen != expected or len(result) < 200:
        raise PaperError("Warmup must cover every expected session and at least 200 bars.")
    return result


def unresolved_journals():
    terminal = {"filled", "canceled", "expired", "rejected"}
    return [str(p) for p in RUNS.glob("*/journal.json")
            if any(r.get("status") not in terminal for r in json.loads(p.read_text()))]


async def session(api, preflight, root):
    clock = preflight["clock"]
    timestamp = datetime.fromisoformat(clock["timestamp"])
    local = timestamp.astimezone(NY)
    elapsed_open = (local - local.replace(hour=9, minute=30, second=0, microsecond=0)).total_seconds()
    if clock["is_open"] is not True or not 0 <= elapsed_open < 60:
        return {"status": "not_run_outside_first_open_minute", "broker_submissions": 0, "native_fills": 0}
    if Decimal(preflight["cash"]) < 1000 or unresolved_journals():
        raise PaperError("Insufficient cash or unresolved prior order outcome.")
    today = local.date().isoformat()
    start = (local.date() - timedelta(days=450)).isoformat()
    calendar = await asyncio.to_thread(api.request, "GET", "/v2/calendar?" + urllib.parse.urlencode({"start": start, "end": today}))
    end = local.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
    history = await asyncio.to_thread(api.request, "GET", "/v2/stocks/SPY/bars?" + urllib.parse.urlencode({
        "start": start, "end": end.isoformat(), "timeframe": "1Day", "feed": "sip", "adjustment": "raw",
        "asof": today, "sort": "asc", "limit": 1000}), data=True)
    bars = history_bars(history, calendar, today)
    ctx = Context(api, root, preflight["cash"])
    node, strategy, task = await started_node(ctx)
    try:
        for bar in bars:
            ctx.data.feed(bar)
        for _ in range(100):
            if strategy.slow.initialized:
                break
            await asyncio.sleep(.01)
        if not strategy.slow.initialized:
            raise PaperError("EMA warmup was not received by native strategy.")
        ctx.armed = True
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline and not ctx.unknown:
            if ctx.pending:
                await asyncio.sleep(.1)
                continue
            current = await asyncio.to_thread(api.request, "GET", "/v2/clock")
            observed = datetime.fromisoformat(current["timestamp"]).astimezone(NY)
            seconds = (observed - observed.replace(hour=9, minute=30, second=0, microsecond=0)).total_seconds()
            if current.get("is_open") is not True or not 0 <= seconds < 60:
                break
            payload = await asyncio.to_thread(api.request, "GET", "/v2/stocks/SPY/quotes/latest?feed=iex", data=True)
            bid, ask, ns = check_quote(payload["quote"], time.time_ns())
            ctx.data.feed(QuoteTick(INSTRUMENT_ID, Price.from_str(str(bid.quantize(Decimal("0.01")))),
                Price.from_str(str(ask.quantize(Decimal("0.01")))), Quantity.from_int(1), Quantity.from_int(1), ns, time.time_ns()))
            await asyncio.sleep(.2)
            if ctx.submissions or any(e["type"] == "decision" for e in ctx.events):
                # One decision at the open, not a continuous or intraday strategy.
                while ctx.pending and time.monotonic() < deadline:
                    await asyncio.sleep(.1)
                break
        ctx.armed = False
        if ctx.pending:
            ctx.unknown = True
        positions = await asyncio.to_thread(api.request, "GET", "/v2/positions")
        open_orders = await asyncio.to_thread(api.request, "GET", "/v2/orders?status=open&limit=100")
        native_qty = Decimal(str(strategy.portfolio.net_position(INSTRUMENT_ID)))
        broker_qty = sum(Decimal(p["qty"]) for p in positions if p["symbol"] == "SPY")
        parity = native_qty == broker_qty and not any(p["symbol"] != "SPY" for p in positions)
        result = {"status": "paper_observed" if parity and not ctx.unknown and not open_orders else "reconciliation_required",
            "broker_submissions": ctx.submissions, "native_fills": ctx.fills,
            "native_broker_position_match": parity, "open_orders": len(open_orders),
            "ending_spy_shares": str(broker_qty), "warmup_bars": len(bars),
            "events": ctx.events, "unknown": ctx.unknown}
        return result
    finally:
        ctx.armed = False
        save(root / "events.json", ctx.events)
        await stop_node(node, task)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["offline", "replay", "preflight", "session"])
    parser.add_argument("--env-file", default=".env.alpaca")
    parser.add_argument("--log-mlflow", action="store_true")
    args = parser.parse_args()
    RUNS.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + args.mode
    root = RUNS / run_id
    root.mkdir(mode=0o700, exist_ok=False)
    lock = RUNS.parent / "active.lock"
    owned = False
    result = {"mode": args.mode, "strategy": "existing_SPY_EMA50_200", "evidence_kind": "offline_fixture" if args.mode in ("offline", "replay") else "broker_paper",
        "max_shares": 1, "max_notional_usd": 1000, "max_orders": 2, "financial_performance_evidence": False,
        "sizing_change": "one_share_instead_of_99pct_cash", "order_policy_change": "DAY_limit_instead_of_market",
        "reconciliation_scope": "flat-start bounded session; no general restart recovery",
        "code_hashes": {p: digest(ROOT / p) for p in ["paper_trading/alpaca.py", "paper_trading/alpaca_native.py",
                         "paper_trading/alpaca_fixture.py", "research/spy_backtest.py", "scripts/alpaca_paper.py"]}}
    for source in result["code_hashes"]:
        dest = root / "source" / source
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((ROOT / source).read_bytes())
    exit_code = 0
    try:
        if args.mode in ("offline", "replay"):
            result.update(asyncio.run(native_fixture(root / "fixture", saved_spy=args.mode == "replay")))
            result["status"] = "passed_offline_native_lifecycle"
        else:
            # Exclusive process-level lock; stale locks require manual investigation.
            with lock.open("x") as f:
                f.write(run_id)
            owned = True
            api = AlpacaPaperHTTP(args.env_file, root / "private-http")
            preflight = api.preflight()
            result.update(status="preflight_passed", market_open=preflight["clock"]["is_open"],
                next_open=preflight["clock"]["next_open"], flat_account=True, broker_submissions=0, native_fills=0)
            if args.mode == "session":
                result.update(asyncio.run(session(api, preflight, root)))
            if result.get("status") == "reconciliation_required":
                exit_code = 1
    except Exception as error:
        result.update(status="failed_preserved", error_type=type(error).__name__)
        exit_code = 1
    finally:
        if owned:
            lock.unlink()
        result["completed_utc"] = datetime.now(timezone.utc).isoformat()
        save(root / "summary.json", result)
    if args.log_mlflow:
        logged = subprocess.run([str(ROOT / ".local/venvs/mlflow/bin/python"), str(ROOT / "scripts/import_alpaca_mlflow.py"), str(root / "summary.json")], cwd=ROOT)
        if logged.returncode:
            print("MLflow import failed; local summary preserved.")
            exit_code = 1
    print(json.dumps({"status": result["status"], "summary": str(root / "summary.json")}))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
