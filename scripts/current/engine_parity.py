#!/usr/bin/env python3
"""Run the screening and NautilusTrader engines on the same data and record a parity receipt.

``run`` loads the bars and actions, runs ``sma_trend_targets()`` through both engines
with the default ``MarketConfig``, writes both run outputs to ``<runs>/<run_id>/`` (the
native run's parent is the screening run) and ``receipt.json`` to
``<out>/<parity_id>/receipt.json``; the receipt references each run by id and
``manifest.json`` sha256. It exits 0 only when the comparator passes. Rejected input or
a mismatch is recorded and exits 1.

Each manifest's ``engine`` is ``EngineResult.engine`` (``screen`` or ``nautilus``) and its
``config`` holds only strategy, market, instruments and engine, so ``config_hash``
identifies the configuration; code and inputs are in ``code_commit`` and ``datasets``.
Offline and order-free: engineering evidence, not financial use.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from research.data.root import DataAbsent, parity_root, require, runs_root  # noqa: E402
from research.evaluation.market_model import MarketConfig, MarketDataError, sma_trend_targets, validate  # noqa: E402
from research.evaluation.native_engine import run_native  # noqa: E402
from research.evaluation.parity import compare  # noqa: E402
from research.evaluation.run_output import COLUMNS, config_hash, new_run_id, write_run  # noqa: E402
from research.evaluation.screening_engine import EngineError, EngineResult, run_screen  # noqa: E402
from research.evaluation.sector_derivative import load_sector_derivative  # noqa: E402

RECEIPT_SCHEMA = "parity-receipt/v1"
STRATEGY = {"name": "sma_trend_targets", "window": 20, "gross": 0.95}
TOLERANCES = {"quantities": "identical", "fill_dates": "identical", "cash_equity_usd_per_session": 0.01}
CASH_INTEREST = "not modelled"
HALF_DAYS_NOTE = "not marked by source"


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _code_commit() -> str:
    commit = _git("rev-parse", "HEAD") or "unknown"
    # Uncommitted tracked changes or new files mean the commit alone does not identify the code.
    dirty = _git("status", "--porcelain", "--untracked-files=normal")
    return commit if dirty == "" else f"{commit}+dirty"


def _engine_version(engine: str) -> str:
    if engine == "nautilus":
        import nautilus_trader

        return f"nautilus_trader {nautilus_trader.__version__}"
    return "screening_engine (project)"


def _calendar(data) -> dict:
    # The loader rejects instruments whose session lists differ, so loaded data is identical.
    return {
        "sessions": len(data.sessions),
        "first": data.sessions[0],
        "last": data.sessions[-1],
        "identical_across_instruments": True,
        "half_days": [],
        "half_days_note": HALF_DAYS_NOTE,
    }


def _write(runs: Path, result: EngineResult, base: dict, parent: str | None, now: datetime) -> dict:
    config = {
        "strategy": base["strategy"],
        "market": base["market"],
        "instruments": base["instruments"],
        "engine": result.engine,
    }
    run_id = new_run_id(config, now)
    manifest = {
        "run_id": run_id,
        "created_utc": now.isoformat(),
        "code_commit": base["code_commit"],
        "config": config,
        "config_hash": config_hash(config),
        "engine": result.engine,
        "engine_version": _engine_version(result.engine),
        "datasets": base["inputs"],
        "coverage": {"instruments": base["instruments"], "sessions": len(result.returns)},
        "parent_run": parent,
    }
    tables = {name: getattr(result, name)[list(cols)] for name, cols in COLUMNS.items()}
    path = write_run(runs, manifest, tables)
    return {"run_id": run_id, "manifest_sha256": _sha256(path / "manifest.json")}


def run(args, argv: list[str], loader) -> int:
    try:
        require(args.bars)
        require(args.actions)
    except DataAbsent as exc:
        print(exc, file=sys.stderr)
        return 2
    now =datetime.now(timezone.utc)
    instruments = tuple(name.strip() for name in args.instruments.split(",") if name.strip())
    inputs = {
        "bars": {"path": str(args.bars), "sha256": _sha256(args.bars)},
        "actions": {"path": str(args.actions), "sha256": _sha256(args.actions)},
    }
    market = MarketConfig()
    base = {
        "strategy": STRATEGY,
        "market": dataclasses.asdict(market),
        "instruments": list(instruments),
        "inputs": inputs,
        "code_commit": _code_commit(),
    }
    folder = Path(args.out) / new_run_id(dict(base, kind="parity"), now)
    folder.mkdir(parents=True, exist_ok=False)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "created_utc": now.isoformat(),
        "use": "engineering evidence, not financial use; offline and order-free",
        "command": ["scripts/current/engine_parity.py", *argv],
        "code_commit": base["code_commit"],
        "inputs": inputs,
        "instruments": list(instruments),
        "strategy": STRATEGY,
        "market": base["market"],
        "tolerances": TOLERANCES,
        "cash_interest": CASH_INTEREST,
        "runs_root": str(args.runs),
        "calendar": None,
        "timing": None,
        "runs": None,
        "status": None,
        "passed": False,
        "mismatch_count": None,
        "mismatches": None,
        "error": None,
    }
    stage = "load"
    try:
        data = loader(args.bars, args.actions, instruments)
        stage = "validate"
        receipt["calendar"] = _calendar(data)
        validate(data)
        target_fn = sma_trend_targets(window=STRATEGY["window"], gross=STRATEGY["gross"])
        stage = "screening"
        started = time.perf_counter()
        screen = run_screen(data, target_fn, market)
        screen_seconds = time.perf_counter() - started
        stage = "native"
        started = time.perf_counter()
        native = run_native(data, target_fn, market)
        native_seconds = time.perf_counter() - started
    except (MarketDataError, EngineError) as exc:
        receipt.update(status="rejected", error={"stage": stage, "type": type(exc).__name__, "message": str(exc)})
        _write_receipt(folder, receipt)
        print(f"parity rejected at {stage}: {exc}", file=sys.stderr)
        print(folder / "receipt.json")
        return 1
    report = compare(screen, native)
    screen_run = _write(Path(args.runs), screen, base, None, now)
    native_run = _write(Path(args.runs), native, base, screen_run["run_id"], now)
    receipt.update(
        timing={
            "screening_seconds": screen_seconds,
            "native_seconds": native_seconds,
            "projected_seconds_500_names": native_seconds * 500 / len(instruments),
        },
        runs={screen.engine: screen_run, native.engine: native_run},
        status="passed" if report.passed else "mismatch",
        passed=report.passed,
        mismatch_count=len(report.mismatches),
        mismatches=list(report.mismatches),
    )
    _write_receipt(folder, receipt)
    print(folder / "receipt.json")
    print(f"parity {'passed' if report.passed else 'FAILED'}: {len(report.mismatches)} mismatches")
    return 0 if report.passed else 1


def _write_receipt(folder: Path, receipt: dict) -> None:
    with (folder / "receipt.json").open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main(argv=None, loader=load_sector_derivative) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    cmd = commands.add_parser("run", help="run both engines and write a parity receipt")
    cmd.add_argument("--bars", type=Path, required=True)
    cmd.add_argument("--actions", type=Path, required=True)
    cmd.add_argument("--instruments", required=True, help="comma-separated, e.g. SPY,XLB,XLE,XLF")
    cmd.add_argument("--out", type=Path, default=None, help="parity receipts root (default <data root>/parity)")
    cmd.add_argument("--runs", type=Path, default=None, help="run outputs root (default <data root>/runs)")
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(argv)
    args.out = args.out if args.out is not None else parity_root()
    args.runs = args.runs if args.runs is not None else runs_root()
    return run(args, argv, loader)


if __name__ == "__main__":
    sys.exit(main())
