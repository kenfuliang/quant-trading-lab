#!/usr/bin/env python3
"""Run the screening and NautilusTrader engines on the same data and record a parity receipt.

``run`` loads the bars and actions (or, with ``--dataset <id>``, a verified, quality-gated
dataset from the data root; the receipt's inputs then carry the manifest sha256 and the
quality report path and status, and ``calendar.half_days`` comes from the quality report), runs ``sma_trend_targets()`` through both engines
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

from research.data.root import DataAbsent, data_root, parity_root, require, runs_root  # noqa: E402
from research.data.manifest import ManifestError  # noqa: E402
from research.evaluation.datasets import DatasetBlocked, load_dataset  # noqa: E402
from research.evaluation.market_model import (  # noqa: E402
    MarketConfig, MarketDataError, market_config_dict, sma_trend_targets, validate)
from research.evaluation.native_engine import run_native  # noqa: E402
from research.evaluation.parity import compare  # noqa: E402
from research.evaluation.run_output import COLUMNS, config_hash, new_run_id, write_run  # noqa: E402
from research.evaluation.screening_engine import EngineError, EngineResult, run_screen  # noqa: E402
from research.evaluation.sector_derivative import load_sector_derivative  # noqa: E402
from research.evaluation.universe import LABELS  # noqa: E402

RECEIPT_SCHEMA = "parity-receipt/v1"
STRATEGY = {"name": "sma_trend_targets", "window": 20, "gross": 0.95}
TOLERANCES = {"quantities": "identical", "fill_dates": "identical", "cash_equity_usd_per_session": 0.01}
CASH_INTEREST = "not modelled"
HALF_DAYS_NOTE = "not marked by source"
TIMING_ONLY_CLAIM = "timing only; no parity or financial claim"


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


def _calendar(data, half_days=None) -> dict:
    # The loader rejects instruments whose session lists differ, so loaded data is identical.
    return {
        "sessions": len(data.sessions),
        "first": data.sessions[0],
        "last": data.sessions[-1],
        "identical_across_instruments": True,
        "half_days": [] if half_days is None else list(half_days),
        "half_days_note": HALF_DAYS_NOTE if half_days is None else "from the quality report",
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
    if base.get("labels"):  # stock-class datasets only; ETF manifests keep exactly the old keys
        manifest["labels"] = base["labels"]
        manifest["universe_kind"] = base["universe_kind"]
    tables = {name: getattr(result, name)[list(cols)] for name, cols in COLUMNS.items()}
    path = write_run(runs, manifest, tables)
    return {"run_id": run_id, "manifest_sha256": _sha256(path / "manifest.json")}


def run(args, argv: list[str], loader, dataset_loader=load_dataset) -> int:
    try:
        if args.dataset:
            require(data_root() / "manifests" / f"{args.dataset}.json")
        else:
            require(args.bars)
            require(args.actions)
    except DataAbsent as exc:
        print(exc, file=sys.stderr)
        return 2
    now = datetime.now(timezone.utc)
    instruments = tuple(name.strip() for name in (args.instruments or "").split(",") if name.strip())
    universe_names = None
    if args.max_instruments is not None:
        if args.max_instruments < 1:
            print("--max-instruments must be at least 1", file=sys.stderr)
            return 2
        if not instruments:  # stock layer: the first N symbols in alphabetical order
            try:
                universe = dataset_loader(args.dataset, None)[0]
            except (MarketDataError, DatasetBlocked, ManifestError) as exc:
                print(f"cannot list the dataset's instruments: {exc}", file=sys.stderr)
                return 2
            universe_names = len(universe.bars)
            instruments = tuple(sorted(universe.bars))
        instruments = instruments[: args.max_instruments]
    if args.dataset:
        inputs = {"dataset_id": args.dataset}  # completed from the loader's provenance
    else:
        inputs = {
            "bars": {"path": str(args.bars), "sha256": _sha256(args.bars)},
            "actions": {"path": str(args.actions), "sha256": _sha256(args.actions)},
        }
    half_days = None
    market = MarketConfig(cost_model=args.cost_model)
    base = {
        "strategy": STRATEGY,
        "market": market_config_dict(market),
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
        "max_instruments": args.max_instruments,
        "timing_only": bool(args.timing_only),
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
        if args.dataset:
            data, provenance = dataset_loader(args.dataset, instruments)
            if provenance.get("universe_kind") == "current-holdings-proxy":
                receipt["labels"] = list(LABELS)
                receipt["universe_kind"] = "current-holdings-proxy"
                base["labels"] = list(LABELS)
                base["universe_kind"] = "current-holdings-proxy"
            files = provenance["inputs"]
            inputs.update(
                manifest_sha256=provenance["manifest_sha256"],
                quality_report=provenance["quality_report"],
                quality_status=provenance["quality_status"])
            if len(files) == 2:
                inputs.update(bars=files[0], actions=files[1])
            else:  # stock layer: one bar file per symbol plus the actions file(s)
                bars = [f for f in files if "actions" not in f["path"]]
                inputs.update(
                    bars={"files": len(bars), "sha256_of_sorted_sha256s": hashlib.sha256(
                        "\n".join(sorted(f["sha256"] for f in bars)).encode()).hexdigest()},
                    actions=[f for f in files if "actions" in f["path"]])
            half_days = provenance["half_days"]
        else:
            data = loader(args.bars, args.actions, instruments)
        stage = "validate"
        receipt["calendar"] = _calendar(data, half_days)
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
    except (MarketDataError, EngineError, DatasetBlocked, ManifestError) as exc:
        receipt.update(status="rejected", error={"stage": stage, "type": type(exc).__name__, "message": str(exc)})
        _write_receipt(folder, receipt)
        print(f"parity rejected at {stage}: {exc}", file=sys.stderr)
        print(folder / "receipt.json")
        return 1
    if args.timing_only:
        receipt.update(
            timing={
                "screening_seconds": screen_seconds,
                "native_seconds": native_seconds,
                "projected_seconds_500_names": native_seconds * 500 / len(instruments),
                **({"universe_names": universe_names,
                    "projected_seconds_universe": native_seconds * universe_names / len(instruments)}
                   if universe_names else {}),
            },
            runs=None, status="timing_only", passed=None, mismatch_count=None, mismatches=None,
            claim=TIMING_ONLY_CLAIM,
        )
        _write_receipt(folder, receipt)
        print(folder / "receipt.json")
        print(f"timing only: screening {screen_seconds:.1f}s, native {native_seconds:.1f}s; no parity claim")
        return 0
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


def main(argv=None, loader=load_sector_derivative, dataset_loader=load_dataset) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    cmd = commands.add_parser("run", help="run both engines and write a parity receipt")
    cmd.add_argument("--dataset", default=None, help="dataset id under <data root>/manifests (not with --bars/--actions)")
    cmd.add_argument("--bars", type=Path, default=None)
    cmd.add_argument("--actions", type=Path, default=None)
    cmd.add_argument("--instruments", default=None, help="comma-separated, e.g. SPY,XLB,XLE,XLF")
    cmd.add_argument("--max-instruments", type=int, default=None,
                     help="use only the first N instruments (with --dataset and no --instruments: "
                          "the first N symbols of the dataset in alphabetical order)")
    cmd.add_argument("--cost-model", choices=("flat", "adv"), default="flat",
                     help="MarketConfig.cost_model (default flat)")
    cmd.add_argument("--timing-only", action="store_true",
                     help="time both engines and record the receipt without a parity or financial claim "
                          "(no run outputs written, status timing_only)")
    cmd.add_argument("--out", type=Path, default=None, help="parity receipts root (default <data root>/parity)")
    cmd.add_argument("--runs", type=Path, default=None, help="run outputs root (default <data root>/runs)")
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(argv)
    if args.dataset and (args.bars or args.actions):
        parser.error("--dataset cannot be combined with --bars/--actions")
    if not args.dataset and not (args.bars and args.actions):
        parser.error("give --dataset, or both --bars and --actions")
    if not args.instruments and not (args.dataset and args.max_instruments):
        parser.error("give --instruments, or --dataset with --max-instruments")
    args.out = args.out if args.out is not None else parity_root()
    args.runs = args.runs if args.runs is not None else runs_root()
    return run(args, argv, loader, dataset_loader)


if __name__ == "__main__":
    sys.exit(main())
