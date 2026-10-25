#!/usr/bin/env python3
"""Local NautilusTrader + IB Gateway paper connection tools."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["doctor", "probe", "observe"])
    parser.add_argument("--seconds", type=int, default=45)
    args = parser.parse_args()
    import nautilus_trader
    from paper_trading.gateway import probe
    from paper_trading.node import build_config, observe
    config = build_config()
    if args.action == "doctor":
        print(json.dumps({"engine": "NautilusTrader", "version": nautilus_trader.__version__,
                          "gateway": "127.0.0.1:4002", "execution_clients": len(config.exec_clients),
                          "quantconnect_service": False, "feed": "delayed/frozen"}, indent=2))
        return
    accounts = probe()
    print(f"IB API handshake passed; {len(accounts)} paper account(s) verified. No orders requested.", flush=True)
    if args.action == "observe":
        if not 10 <= args.seconds <= 300:
            raise ValueError("Observation duration must be 10–300 seconds.")
        result = observe(args.seconds)
        print(json.dumps(result))
        if not all(result.values()):
            raise RuntimeError("Observation did not verify both data connection and SPY instrument loading.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError) as error:
        print(f"Connection check stopped: {error}", file=sys.stderr)
        raise SystemExit(1)
