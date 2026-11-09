#!/usr/bin/env python3
"""Per-day SPY EMA50/200 target-position series from the existing backtest engine.

Offline, order-free. Output is the reference a shadow run is compared against.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from paper_trading.spy_signal import target_series
from research.studies.spy.spy_backtest import END, FAST, SLOW, START, load_data, run_engine


def replay_series(frame, dividends, *, start=START, end=END, fast=FAST, slow=SLOW):
    """Rows of {date, target_position, signal}; target is the position held from that open."""
    curve, _, _, _ = run_engine(frame, dividends, "trend", start=start, end=end, fast=fast, slow=slow)
    signal = dict(zip(frame.index, [0] + target_series(frame.close, fast, slow)[:-1]))
    rows = [{"date": date, "target_position": int(shares > 0), "signal_target": signal[date]}
            for date, shares in curve.shares.items()]
    mismatches = [r["date"] for r in rows if r["target_position"] != r["signal_target"]]
    return rows, mismatches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "backtests/raw/spy-yahoo-2004-2025.json")
    parser.add_argument("--out", type=Path, default=ROOT / ".local/shadow/replay.json")
    parser.add_argument("--start", default=START)
    parser.add_argument("--end", default=END)
    args = parser.parse_args()
    frame, dividends, source = load_data(args.data)
    rows, mismatches = replay_series(frame, dividends, start=args.start, end=args.end)
    payload = {"source_sha256": source["sha256"], "start": args.start, "end": args.end,
               "fast": FAST, "slow": SLOW, "parity_mismatches": mismatches, "rows": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=1, allow_nan=False) + "\n"
    args.out.write_text(text)
    print(json.dumps({"rows": len(rows), "parity_mismatches": len(mismatches),
                      "out": str(args.out), "sha256": hashlib.sha256(text.encode()).hexdigest()}))
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
