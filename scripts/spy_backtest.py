#!/usr/bin/env python3
"""Run the fixed SPY experiment offline, optionally fetching its initial snapshot."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import platform
import shutil
import sys
import urllib.request
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research.spy_backtest import (
    ALLOCATION, COMMISSION, COST_BPS, END, FAST, INITIAL_CASH, SLOW, SOURCE_URL, START,
    audit_run, load_data, metrics, run_engine,
)
from research.spy_report import write_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "backtests/raw/spy-yahoo-2004-2025.json")
    parser.add_argument("--download", action="store_true", help="Fetch only if the snapshot does not exist; never overwrite it")
    args = parser.parse_args()
    raw = args.data.resolve()
    if not raw.exists():
        if not args.download:
            parser.error("No data snapshot. Add --download to fetch the initial public history.")
        response = urllib.request.urlopen(urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read()
        raw.parent.mkdir(parents=True, exist_ok=True)
        with raw.open("xb") as stream:
            stream.write(response)
    frame, dividends, source = load_data(raw)
    now = datetime.now(ZoneInfo("America/Los_Angeles"))
    output = ROOT / "reports/spy" / now.strftime("%Y%m%d-%H%M%S-%f")
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(raw, output / "source-data.json")
    normalized = frame.copy()
    normalized["dividend_per_share"] = [dividends.get(d, 0) for d in frame.index]
    normalized.to_csv(output / "input_daily.csv")
    runs = {}
    for mode in ("trend", "buy_hold"):
        curve, fills, credits, orders = run_engine(frame, dividends, mode)
        fills, audit = audit_run(frame, dividends, mode, curve, fills, credits)
        summary = metrics(curve, fills, credits)
        summary["modeled_spread_slippage_usd"] = float(fills.modeled_cost_vs_open_usd.sum())
        runs[mode] = dict(curve=curve, fills=fills, credits=credits, orders=orders, metrics=summary, audit=audit)
    import nautilus_trader
    manifest = {
        "status": "completed", "created_local": now.isoformat(), "source": source,
        "source_snapshot_relative": str((output / "source-data.json").relative_to(ROOT)),
        "parameters": {"start": START, "end": END, "fast_ema": FAST, "slow_ema": SLOW,
                       "initial_cash_usd": INITIAL_CASH, "entry_allocation": ALLOCATION,
                       "cost_bps_per_side": COST_BPS, "commission_per_order_usd": COMMISSION,
                       "cash_interest": 0, "automatic_dividend_reinvestment": False},
        "runtime": {"python": platform.python_version(), "nautilus_trader": nautilus_trader.__version__},
        "audits": {mode: run["audit"] for mode, run in runs.items()},
        "source_code_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in [ROOT / "research/spy_backtest.py", ROOT / "research/spy_report.py", Path(__file__).resolve()]},
    }
    write_report(runs, manifest, output)
    for mode, run in runs.items():
        print(mode, json.dumps(run["metrics"], indent=2))
    print("REPORT:", output / "report.md")
    print("CHART:", output / "comparison.png")


if __name__ == "__main__":
    main()
