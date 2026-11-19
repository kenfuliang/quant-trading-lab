#!/usr/bin/env python3
"""Recompute a combination from its component run ids and compare it with the recorded run.

  portfolio_repro.py --run-id COMBINATION_RUN_ID [--runs-root DIR]

Reads the combination and its components (every hash verified), recombines with the recorded
parameters into a temporary runs root (never the real one) and prints one JSON object: the
config hashes and the SHA-256 of each parquet table, original against recomputed. The temporary
run id differs from the original only by its timestamp prefix. Exit 0 when the config hash and all
four tables are identical, 1 otherwise. Offline, order-free, writes nothing outside the temp root.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.data.root import data_root  # noqa: E402
from research.evaluation.portfolio import Sleeve, build_manifest, combine  # noqa: E402
from research.evaluation.run_output import read_run, write_run  # noqa: E402

PARAMS = ("vol_window", "rebalance", "gross", "rebalance_cost_bps", "initial_cash")


def reproduce(runs: Path, run_id: str) -> dict:
    manifest, _ = read_run(runs / run_id)
    config = manifest["config"]
    sleeves = []
    for component in config["components"]:
        comp_manifest, tables = read_run(runs / component["run_id"])
        sleeves.append(Sleeve(component["run_id"], comp_manifest, tables["returns"], tables["fills"]))
    params = {key: config[key] for key in PARAMS}
    tables = combine(sleeves, config["method"], **params)
    again = build_manifest(sleeves, config["method"], params, tables, datetime.now(timezone.utc),
                           manifest["code_commit"], exploratory=True)
    with tempfile.TemporaryDirectory() as tmp:
        path = write_run(Path(tmp), again, tables)
        new_files = json.loads((path / "manifest.json").read_text())["files"]
    tables_equal = {name: new_files[name] == manifest["files"][name] for name in new_files}
    return {"original_run": run_id, "temporary_run": again["run_id"],
            "config_hash_original": manifest["config_hash"], "config_hash_recomputed": again["config_hash"],
            "config_hash_equal": manifest["config_hash"] == again["config_hash"],
            "parquet_sha256_original": {k: manifest["files"][k] for k in new_files},
            "parquet_sha256_recomputed": new_files, "tables_equal": tables_equal,
            "all_identical": manifest["config_hash"] == again["config_hash"] and all(tables_equal.values())}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--runs-root", type=Path)
    args = parser.parse_args(argv)
    runs = args.runs_root or data_root() / "runs"
    result = reproduce(runs, args.run_id)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_identical"] else 1


if __name__ == "__main__":
    sys.exit(main())
