#!/usr/bin/env python3
"""How often the recorded pilot limits would have fired on past SPY EMA50/200 history. Offline, read-only.

Reads the adjusted SPY bars from a saved scripts/t11_replay.py fetch folder (default: newest under --root)
and runs paper_trading.pilot_replay. It places no order and contacts nothing. The result describes viewed
development history under a close-to-close approximation; it is not a forecast and not advice.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from paper_trading.pilot_replay import replay
from paper_trading.risk_gate import PilotLimits
from paper_trading.t11_pilot import SYMBOLS
from paper_trading.t11_replay import parse_bars
from scripts.t11_replay import split_responses


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT / ".local/t11-replay")
    parser.add_argument("--run", type=Path, help="fetch folder (default: newest under --root)")
    parser.add_argument("--start", help="first session to count, YYYY-MM-DD")
    parser.add_argument("--out", type=Path, help="write the full result as JSON")
    args = parser.parse_args(argv)
    run = args.run or sorted(p for p in args.root.glob("2*") if p.is_dir())[-1]
    adjusted, _ = split_responses(run)
    closes = {d: v[3] for d, v in parse_bars(adjusted, SYMBOLS)["SPY"].items()}
    result = replay(closes, PilotLimits(), start=args.start)
    if args.out:
        args.out.write_text(json.dumps(result, indent=1))
    print(f"Fetch {run.name}; sessions counted {result['sessions']} ({min(closes)} to {max(closes)} available); "
          f"long {result['long_share']:.0%} of days; final equity {result['final_equity']}; max drawdown {result['max_drawdown']:.1%}")
    for name, count in result["counts"].items():
        recent = result["events"][name][-3:]
        print(f"  {name}: {count} session(s){'; latest ' + ', '.join(recent) if recent else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
