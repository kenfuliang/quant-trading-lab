#!/usr/bin/env python3
"""Launch cloud backtesting or the interactive IBKR paper deployment wizard."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["backtest", "observe", "smoke"])
    args = parser.parse_args()
    path = ROOT / "IBPaperStarter" / "config.json"
    original = path.read_text()
    config = json.loads(original)
    config["parameters"]["smoke-order"] = "false" if args.action == "observe" else "true"
    path.write_text(json.dumps(config, indent=4) + "\n")
    try:
        if args.action == "backtest":
            command = ["lean", "cloud", "backtest", "IBPaperStarter", "--push", "--open"]
        else:
            print("Select Interactive Brokers, enter PAPER credentials and DU account, then review paper mode.")
            command = ["lean", "cloud", "live", "deploy", "IBPaperStarter", "--push", "--open"]
        result = subprocess.run(command, cwd=ROOT)
    finally:
        path.write_text(original)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
