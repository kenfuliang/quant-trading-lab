#!/usr/bin/env python3
"""Fetch daily bars (read-only GET) and replay the unqualified T11 prototype to the latest completed session.

  fetch    bounded GET of the calendar, 24 adjusted ETF series and raw SPY; saved under --root/<UTC>/
  replay   recompute each day's prototype decision from a saved run, simulate holdings and equity,
           measure agreement with the saved cloud export, and write the page inputs
  all      fetch then replay (what the daily job runs)

The prototype is unqualified (see paper_trading/t11_replay.py). Nothing here can submit an order.
Outputs go under ignored --root; they derive from private market data and a private policy file.
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

from paper_trading.t11_pilot import SYMBOLS
from paper_trading.t11_preview import pinned_policy
from paper_trading.t11_replay import cut_to_completed, decisions, parity, parse_bars, simulate

NY = ZoneInfo("America/New_York")
ROUTES = {("https://paper-api.alpaca.markets", "/v2/calendar"), ("https://data.alpaca.markets", "/v2/stocks/bars")}
MAX_REQUESTS, MAX_BYTES, MAX_SECONDS = 14, 40_000_000, 240
MIN_ET_MINUTES = 16 * 60 + 30


def save(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False, sort_keys=True) + "\n")


def load_policy(path):
    """Hash-pinned private policy via the repo's own loader; never an unpinned module."""
    path = Path(path)
    return lambda features, cap: pinned_policy(path, features, cap)


def fetch(args):
    from research.studies.checkpoint_20261031.alpaca_pilot import NoRedirect, credentials
    now = datetime.now(timezone.utc)
    local = now.astimezone(NY)
    run = args.root / now.strftime("%Y%m%dT%H%M%SZ")
    run.mkdir(parents=True, mode=0o700, exist_ok=False)
    summary = {"status": "started", "requests": 0, "bytes": 0, "broker_submissions": 0}
    started = time.monotonic()
    key, secret = credentials(args.env)
    opener = urllib.request.build_opener(NoRedirect())

    def request(host, path, params):
        if (host, path) not in ROUTES:
            raise ValueError("Route forbidden.")
        if summary["requests"] >= MAX_REQUESTS or time.monotonic() - started > MAX_SECONDS:
            raise ValueError("Request/time budget exhausted.")
        summary["requests"] += 1
        req = urllib.request.Request(host + path + "?" + urllib.parse.urlencode(params), method="GET",
                                     headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret})
        with opener.open(req, timeout=20) as response:
            raw = response.read(6_000_001)
        if len(raw) > 6_000_000:
            raise ValueError("Response too large.")
        summary["bytes"] += len(raw)
        if summary["bytes"] > MAX_BYTES:
            raise ValueError("Byte budget exhausted.")
        (run / f"response-{summary['requests']:02d}.json").write_bytes(raw)
        return json.loads(raw)

    def pages(symbols, start, adjustment, end):
        params = {"symbols": ",".join(sorted(symbols)), "timeframe": "1Day", "adjustment": adjustment, "feed": "sip",
                  "start": start + "T00:00:00-05:00", "end": end.isoformat(), "limit": 10000}
        got, tokens = [], set()
        while True:
            payload = request("https://data.alpaca.markets", "/v2/stocks/bars", params)
            got.append(payload)
            token = payload.get("next_page_token")
            if not token:
                return got
            if token in tokens:
                raise ValueError("Pagination token repeated.")
            tokens.add(token)
            params["page_token"] = token

    try:
        calendar = request("https://paper-api.alpaca.markets", "/v2/calendar", {"start": "2016-01-01", "end": str(local.date())})
        sessions = [x["date"] for x in calendar]
        latest = sessions[-1] if sessions else None
        if latest == str(local.date()) and local.hour * 60 + local.minute < MIN_ET_MINUTES:
            latest = sessions[-2]  # today's bar is not final before 16:30 New York
        end = now - timedelta(minutes=20)
        pages(SYMBOLS, args.adj_start, "all", end)
        pages({"SPY"}, "2016-01-01", "raw", end)
        summary.update(status="fetched", latest_completed_session=latest, adj_start=args.adj_start)
    except Exception as exc:
        summary.update(status="failed_preserved", error_type=type(exc).__name__, error=str(exc)[:200])
    finally:
        summary["elapsed_seconds"] = round(time.monotonic() - started, 2)
        save(run / "summary.json", summary)
        save(run / "manifest.json", {"files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in run.iterdir()
                                              if p.is_file() and p.name != "manifest.json"}})
    print(json.dumps({"fetch": summary["status"], "run": str(run), "latest": summary.get("latest_completed_session"), "orders": 0}))
    return run if summary["status"] == "fetched" else None


def split_responses(run):
    """First pages belong to the adjusted 24-symbol request, later to raw SPY (the order fetch() wrote)."""
    files = sorted(run.glob("response-*.json"))
    payloads = [json.loads(f.read_text()) for f in files[1:]]  # skip the calendar
    adj, raw = [], []
    for payload in payloads:
        (raw if set(payload.get("bars", {})) == {"SPY"} and len(adj) else adj).append(payload)
    return adj, raw


def replay(args, run):
    adj_pages, raw_pages = split_responses(run)
    # The adjusted request contains SPY too; raw SPY comes from its own pages.
    bars = parse_bars(adj_pages, SYMBOLS)
    raw_spy = {d: v[3] for d, v in parse_bars(raw_pages, {"SPY"})["SPY"].items()}
    latest = json.loads((run / "summary.json").read_text()).get("latest_completed_session")
    bars, raw_spy = cut_to_completed(bars, raw_spy, latest)
    policy = load_policy(args.policy)
    decided = decisions(bars, raw_spy, policy, args.start)
    dataset = simulate(decided, bars, args.capital, args.deployment, args.cost_bp)
    dataset["name"] = "T11 prototype replay"
    out = args.root / "latest"
    out.mkdir(parents=True, exist_ok=True)
    save(out / "decisions.json", decided)
    save(out / "dataset.json", dataset)
    closepath = [{"session": d, "nav_usd": v, "export_sample_utc": f"{d}T21:00:00+00:00", "mapping": "replay_close"}
                 for d, v in zip(dataset["dates"], dataset["nav"])]
    closepath[0]["nav_usd"] = float(args.capital)
    save(out / "closepath.json", closepath)
    spy = [bars["SPY"][d][3] for d in dataset["dates"]]
    save(out / "spy_closepath.json", [{"session": d, "nav_usd": (float(args.capital) if k == 0 else round(args.capital * spy[k] / spy[0], 4)),
                                       "export_sample_utc": f"{d}T21:00:00+00:00", "mapping": "replay_close"} for k, d in enumerate(dataset["dates"])])
    report = {"source_run": run.name, "start": args.start, "sessions": len(dataset["dates"]), "last_session": dataset["dates"][-1],
              "latest_decision": decided[max(decided)] | {"session": max(decided)}, "assumptions": {
                  "capital": args.capital, "deployment": args.deployment, "cost_bp_per_traded_notional": args.cost_bp,
                  "fills": "next session open", "shares": "whole shares on dividend/split adjusted prices"}}
    if args.reference_close_path and args.reference_export:
        from scripts.daily_holdings import build_dataset
        ref = build_dataset("cloud", json.loads(Path(args.reference_close_path).read_text()), json.loads(Path(args.reference_export).read_text()))
        report["parity_vs_cloud_export"] = parity(dataset, ref)
    p = report.get("parity_vs_cloud_export")
    dataset["note"] = ("Prototype replay, not the cloud backtest: each day's decision is recomputed by the repo's UNQUALIFIED local prototype from data up to that close; "
                       f"fills at the next open, {args.cost_bp:g}bp cost, {args.deployment:.0%} deployment, whole shares on adjusted prices. "
                       + (f"On the {p['overlap_sessions']} sessions it overlaps the cloud export it held the same symbols on {p['same_held_set_share']:.0%} of days "
                          f"({p['same_held_set_when_reference_invested']:.0%} of days the export was invested) and daily returns correlate {p['daily_return_correlation']:.2f}. " if p else "")
                       + "Share counts and values are not the cloud's.")
    save(out / "dataset.json", dataset)
    save(out / "report.json", report)
    print(json.dumps({"replay": "ok", "sessions": report["sessions"], "last_session": report["last_session"],
                      "latest_decision": report["latest_decision"], "parity": report.get("parity_vs_cloud_export")}, default=str))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("fetch", "replay", "all"))
    parser.add_argument("--root", type=Path, default=ROOT / ".local/t11-replay")
    parser.add_argument("--env", type=Path, default=ROOT / ".env.alpaca")
    parser.add_argument("--policy", type=Path, default=ROOT / ".local/t11-reproduction-v1/policy_port.py")
    parser.add_argument("--run", type=Path, help="saved fetch folder for replay (default: newest fetched)")
    parser.add_argument("--adj-start", default="2023-01-01")
    parser.add_argument("--start", default="2025-01-02", help="first session to decide on")
    parser.add_argument("--capital", type=float, default=10000.0)
    parser.add_argument("--deployment", type=float, default=0.9)
    parser.add_argument("--cost-bp", type=float, default=25.0)
    parser.add_argument("--reference-close-path", help="cloud close-path JSON for the parity check")
    parser.add_argument("--reference-export", help="cloud export JSON for the parity check")
    args = parser.parse_args(argv)
    run = args.run
    if args.command in ("fetch", "all"):
        run = fetch(args)
        if run is None:
            return 1
    if args.command in ("replay", "all"):
        if run is None:
            good = [p for p in sorted(args.root.glob("*/")) if (p / "summary.json").exists()
                    and json.loads((p / "summary.json").read_text()).get("status") == "fetched"]
            if not good:
                print("No fetched run to replay.", file=sys.stderr)
                return 1
            run = good[-1]
        return replay(args, run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
