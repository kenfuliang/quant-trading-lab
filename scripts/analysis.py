#!/usr/bin/env python3
"""Analysis command: ablation ladder, trust statistics, lookahead check and tearsheet.

  run --spec <path> [--root <dir>]   run a spec and write <root>/analysis/<analysis_id>/
                                     (default root: the data root); prints the folder
  golden [--update] [--file <path>]  run the fixture ladder in a temp root and compare the
                                     per-rung summaries (rounded to 10 dp) with
                                     tests/golden/fixture-ladder-summary.json; exit 1 naming
                                     the file on a difference, or rewrite it with --update

The registry (comparison metrics, DSR trial counts) is read here, because evaluation code may
not import the control layer, and is passed to the evaluation functions as plain values.
Offline and order-free.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from reporting.run_tearsheet import tearsheet_html  # noqa: E402
from research.control import experiment_registry  # noqa: E402
from research.data.root import DataAbsent, data_root  # noqa: E402
from research.evaluation.analysis_output import build_analysis, render_report, write_analysis  # noqa: E402
from research.evaluation.datasets import DatasetBlocked, load_dataset  # noqa: E402
from research.evaluation.ladder import Rung, run_ladder  # noqa: E402
from research.evaluation.lookahead import check_lookahead  # noqa: E402
from research.evaluation.market_model import MarketConfig  # noqa: E402
from research.evaluation.parity_fixture import synthetic_fixture  # noqa: E402
from research.evaluation.run_output import read_run  # noqa: E402
from research.evaluation.screening_engine import run_screen  # noqa: E402
from research.evaluation.strategies import build_target_fn  # noqa: E402
from research.evaluation.trust import dsr, pbo, psr  # noqa: E402

REGISTRY = ROOT / "research/registry/experiments.jsonl"
FIXTURE_SPEC = ROOT / "research/registry/analysis-specs/fixture-ladder.json"
GOLDEN = ROOT / "tests/golden/fixture-ladder-summary.json"
GOLDEN_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
SQRT_252 = math.sqrt(252)
GRID_NOTE = "PBO grid is an illustrative grid; not registry trials."


def _code_commit() -> str:
    def git(*args):
        try:
            return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    commit = git("rev-parse", "HEAD") or "unknown"
    return commit if git("status", "--porcelain", "--untracked-files=normal") == "" else f"{commit}+dirty"


def trial_stats(records: list[dict], code: str) -> tuple[int, float | None]:
    """``(n_trials, per-period Sharpe variance)`` over registry records with ``context.code == code``.

    The variance is the sample variance of ``metrics.sharpe / sqrt(252)`` over those records that
    have a Sharpe; ``None`` when fewer than 2 do.
    """
    matching = [r for r in records if r["context"]["code"] == code]
    sharpes = [r["metrics"]["sharpe"] / SQRT_252 for r in matching if r["metrics"].get("sharpe") is not None]
    variance = float(np.var(sharpes, ddof=1)) if len(sharpes) >= 2 else None
    return len(matching), variance


def _rungs(spec: dict) -> list[Rung]:
    return [Rung(r["name"], r["strategy"], MarketConfig(**r.get("market", {}))) for r in spec["rungs"]]


def _load(spec: dict, root: Path, loader):
    if spec.get("fixture"):
        return synthetic_fixture(), {"dataset_id": "synthetic-fixture"}
    data, provenance = loader(spec["dataset_id"], tuple(spec["instruments"]), root)
    return data, {"dataset_id": spec["dataset_id"], **provenance}


def _pbo(spec: dict, data, market: MarketConfig) -> dict:
    grid = spec.get("pbo_grid")
    if not grid:
        return {"value": None, "reason": "no pbo_grid in spec"}
    zero = dataclasses.replace(market, cost_bps=0.0, commission_usd=0.0)
    columns = {json.dumps(item, sort_keys=True): run_screen(data, build_target_fn(item), zero).returns["net_return"].to_numpy()
               for item in grid}
    out = pbo(pd.DataFrame(columns))
    out["grid_size"] = len(grid)
    return out


def _comparison(spec: dict, records: list[dict]) -> dict | None:
    wanted = (spec.get("comparison") or {}).get("record_ids")
    if not wanted:
        return None
    by_id = {r["record_id"]: r for r in records}
    found = [by_id[i] for i in wanted if i in by_id]
    return {"records": [{"record_id": r["record_id"], "name": r["name"], "context": r["context"],
                         "metrics": r["metrics"]} for r in found],
            "missing": [i for i in wanted if i not in by_id]}


def run_spec(spec: dict, root: Path, registry_path: Path = REGISTRY, now: datetime | None = None,
             loader=None, tearsheet=tearsheet_html) -> dict:
    """Run a spec end to end; returns ``{"doc": ..., "folder": Path}``."""
    now = now or datetime.now(timezone.utc)
    root = Path(root)
    commit = _code_commit()
    loader = loader or load_dataset
    data, datasets = _load(spec, root, loader)
    rungs = _rungs(spec)
    steps = run_ladder(data, rungs, root / "runs", {"code_commit": commit, "datasets": datasets}, now)
    last, last_spec = rungs[-1], rungs[-1].strategy
    _, tables = read_run(root / "runs" / steps[-1]["run_id"])
    net = tables["returns"]["net_return"].to_numpy(dtype=float)

    notes = list(spec.get("notes", []))
    records = experiment_registry.load(registry_path) if spec.get("comparison") else []
    comparison = _comparison(spec, records)
    if comparison and comparison["records"]:
        code = comparison["records"][0]["context"]["code"]
        n_trials, variance = trial_stats(records, code)
        if variance is None:
            trust_dsr = {"value": None, "n_trials": n_trials,
                         "reason": f"fewer than 2 registry Sharpe values for context {code}"}
        else:
            trust_dsr = dsr(net, n_trials, variance)
        trust_dsr["code"] = code
    else:
        trust_dsr = {"value": None, "reason": "no comparison record; trial count undefined"}
    trust = {"psr": psr(net), "dsr": trust_dsr, "pbo": _pbo(spec, data, last.market)}
    if spec.get("pbo_grid"):
        notes.append(GRID_NOTE)
    lookahead = check_lookahead(data, lambda d: build_target_fn(last_spec), last.market, cutoffs=spec.get("cutoffs", 5))

    spec_with_notes = {**spec, "notes": notes}
    doc = build_analysis(spec_with_notes, steps, trust, lookahead, comparison,
                         {"code_commit": commit, "datasets": datasets}, now.isoformat(),
                         {"status": "skipped", "error": None})
    html_page = None
    try:
        series = pd.Series(net, index=pd.to_datetime(tables["returns"]["date"]))
        stats = {f"{key} (last rung)": float(value) for key, value in steps[-1]["summary"].items() if value is not None}
        html_page = tearsheet(series, stats, f"{spec.get('title', spec['spec_id'])} - {last.name}")
        doc["tearsheet"] = {"status": "written", "error": None}
    except Exception as exc:  # the tearsheet is optional; the analysis stands without it
        error = f"{type(exc).__name__}: {exc}"
        doc["tearsheet"] = {"status": "failed", "error": error}
        print(f"warning: tearsheet failed: {error}", file=sys.stderr)
    folder = write_analysis(root, doc, html_page, render_report(doc))
    return {"doc": doc, "folder": folder}


def _round(value):
    return round(value, 10) if isinstance(value, float) else value


def golden_summary(spec: dict) -> dict:
    """Deterministic ``{rung: summary}`` for a spec (ladder only, rounded to 10 dp)."""
    with tempfile.TemporaryDirectory() as tmp:
        data, datasets = _load(spec, Path(tmp), load_dataset)
        steps = run_ladder(data, _rungs(spec), Path(tmp) / "runs", {"code_commit": "golden", "datasets": datasets},
                           GOLDEN_NOW)
    return {s["rung"]: {k: _round(v) for k, v in s["summary"].items()} for s in steps}


def cmd_run(args) -> int:
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    root = args.root or data_root()
    print(run_spec(spec, root, args.registry)["folder"])
    return 0


def cmd_golden(args) -> int:
    summary = golden_summary(json.loads(FIXTURE_SPEC.read_text(encoding="utf-8")))
    text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.update:
        args.file.parent.mkdir(parents=True, exist_ok=True)
        args.file.write_text(text, encoding="utf-8")
        print(f"Updated {args.file}")
        return 0
    if not args.file.is_file() or json.loads(args.file.read_text(encoding="utf-8")) != json.loads(text):
        print(f"error: golden summary {args.file} differs from the fixture ladder; "
              "review the change and run scripts/analysis.py golden --update", file=sys.stderr)
        return 1
    print(f"Golden passed: {args.file}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--spec", type=Path, required=True)
    run.add_argument("--root", type=Path)
    run.add_argument("--registry", type=Path, default=REGISTRY)
    run.set_defaults(fn=cmd_run)
    golden = sub.add_parser("golden")
    golden.add_argument("--update", action="store_true")
    golden.add_argument("--file", type=Path, default=GOLDEN)
    golden.set_defaults(fn=cmd_golden)
    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except DataAbsent as error:
        print(error, file=sys.stderr)
        return 2
    except (DatasetBlocked, experiment_registry.RegistryError, OSError, ValueError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
