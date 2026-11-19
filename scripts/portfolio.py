#!/usr/bin/env python3
"""Portfolio command: combine run outputs into one sleeve-level run, and report on it.

  combine --run-id A --run-id B [...] --method equal|inverse_vol
          [--gross 1.0 --vol-window 60 --rebalance monthly|daily --rebalance-cost-bps 5.0
           --initial-cash 100000]
          (--cycle-id ID | --exploratory) [--runs-root DIR] [--ledger-dir DIR] [--root DIR]
      load each component with read_run (every hash verified), record one ledger trial
      (--cycle-id) or none (--exploratory, the manifest says so), write the combined run
      under the runs root and print its run id. Exactly one of the two flags is required.
  report --run-id ID [--runs-root DIR] [--root DIR]
      write <root>/portfolio/<run id>/report.json (portfolio-report/v1), exclusive create.

The ledger trial is recorded before the run is written and its number goes in the manifest.
The default ledger is the tracked research/registry/trial-ledger; use --exploratory (or a
temporary --ledger-dir) for anything that is not a real research cycle. Offline and order-free.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from research.control.trial_ledger import TrialLedger  # noqa: E402
from research.data.root import DataAbsent, data_root  # noqa: E402
from research.evaluation.metrics import summarize  # noqa: E402
from research.evaluation.portfolio import (METHODS, REBALANCE, PortfolioError, Sleeve, build_manifest,  # noqa: E402
                                           combine, manifest_sha256, reconcile)
from research.evaluation.run_output import RunOutputError, read_run, write_run  # noqa: E402

SCHEMA = "portfolio-report/v1"
LEDGER_DIR = ROOT / "research/registry/trial-ledger"
RECONCILE_TOLERANCE = 1e-12
LIMITATIONS = [
    "Sleeve-level model: the combination weights sleeve return series, it is not a share-level portfolio "
    "(positions are sleeves and quantity is 0).",
    "Cash earns zero: whatever is not allocated to a sleeve (gross below 1, or drift) is idle.",
    "Costs are rebalance turnover only: rebalance_cost_bps times the sum of absolute weight changes.",
    "Sleeve returns already include their own trading costs; none is charged twice.",
    "The combination is not a share-level portfolio: no lot sizes, no per-name limits, no intra-sleeve netting.",
]


def _code_commit() -> str:
    def git(*args):
        try:
            return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    commit = git("rev-parse", "HEAD") or "unknown"
    return commit if git("status", "--porcelain", "--untracked-files=normal") == "" else f"{commit}+dirty"


def _safe_id(run_id: str) -> str:
    if not run_id or Path(run_id).name != run_id or run_id in (".", ".."):
        raise PortfolioError(f"invalid run id {run_id!r}")
    return run_id


def _load_sleeve(runs: Path, run_id: str) -> Sleeve:
    """Load one component, naming it in any failure (missing, tampered or unreadable)."""
    try:
        manifest, tables = read_run(runs / _safe_id(run_id))
    except (RunOutputError, OSError, ValueError, KeyError) as error:
        raise PortfolioError(f"component {run_id}: {error}") from error
    return Sleeve(run_id, manifest, tables["returns"])


def _roots(args) -> tuple[Path, Path]:
    root = Path(args.root) if args.root else data_root()
    runs = Path(args.runs_root) if args.runs_root else root / "runs"
    return root, runs


def cmd_combine(args) -> int:
    if bool(args.cycle_id) == bool(args.exploratory):
        raise PortfolioError("exactly one of --cycle-id and --exploratory is required "
                             f"(got {'both' if args.cycle_id else 'neither'})")
    _, runs = _roots(args)
    sleeves = [_load_sleeve(runs, run_id) for run_id in args.run_id]
    params = {"vol_window": args.vol_window, "rebalance": args.rebalance, "gross": args.gross,
              "rebalance_cost_bps": args.rebalance_cost_bps, "initial_cash": args.initial_cash}
    tables = combine(sleeves, args.method, **params)  # validates everything before any trial is recorded
    commit = _code_commit()
    if args.cycle_id and commit.endswith("+dirty"):
        raise PortfolioError(f"refusing to record a trial from a dirty tree ({commit}); commit first "
                             "or use --exploratory")
    trial = None
    if args.cycle_id:
        description = f"portfolio combine {args.method} of {', '.join(args.run_id)}"
        with TrialLedger(args.ledger_dir) as ledger:
            number = ledger.trial(args.cycle_id, description)
        trial = {"cycle_id": args.cycle_id, "trial_number": number}
    manifest = build_manifest(sleeves, args.method, params, tables, datetime.now(timezone.utc), commit,
                              trial=trial, exploratory=bool(args.exploratory))
    write_run(runs, manifest, tables)
    print(manifest["run_id"])
    return 0


def _clean(value):
    """JSON-safe copy: non-finite floats become None, numpy scalars become Python numbers."""
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, (np.floating, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


def _initial_cash(returns: pd.DataFrame, fallback: float) -> float:
    first = returns.iloc[0]
    denominator = 1 + float(first["net_return"])
    return float(first["equity"]) / denominator if denominator > 0 else fallback


def diversification(sleeve_returns: pd.DataFrame, portfolio_returns: pd.Series, weights: np.ndarray) -> dict:
    """Diversification ratio and risk-contribution shares.

    ``weights`` are the first rebalance's target weights ``w_i`` (the full-sample weights are not
    constant: they drift and, for inverse_vol, re-target), and every statistic uses the full
    sample with ddof 1:

    - ``diversification_ratio = sum_i(w_i * sigma_i) / sigma_p`` where ``sigma_i`` is the standard
      deviation of sleeve ``i``'s ``net_return`` and ``sigma_p`` that of the combined run's
      ``net_return`` (after rebalance cost); ``None`` when ``sigma_p`` is zero.
    - ``risk_contribution_share_i = w_i * Cov(r_i, r_p) / Var(r_p)``, ``r_p`` the combined
      ``net_return``. The shares sum to about 1 only when the weights stay near the first
      rebalance's and cost and cash are small; ``sum`` is reported so the gap is visible.
    """
    sigma = sleeve_returns.std(axis=0, ddof=1).to_numpy(dtype=float)
    sigma_p = float(portfolio_returns.std(ddof=1))
    var_p = sigma_p ** 2
    if not (math.isfinite(sigma_p) and sigma_p > 1e-12):
        return {"weights": weights.tolist(), "sleeve_sigma": sigma.tolist(), "portfolio_sigma": sigma_p,
                "diversification_ratio": None, "risk_contribution_share": None, "risk_contribution_sum": None}
    covariance = np.array([float(sleeve_returns[c].cov(portfolio_returns)) for c in sleeve_returns.columns])
    shares = weights * covariance / var_p
    return {"weights": weights.tolist(), "sleeve_sigma": sigma.tolist(), "portfolio_sigma": sigma_p,
            "diversification_ratio": float((weights * sigma).sum() / sigma_p),
            "risk_contribution_share": shares.tolist(), "risk_contribution_sum": float(shares.sum())}


def build_report(runs: Path, run_id: str, now: datetime) -> dict:
    try:
        manifest, tables = read_run(runs / _safe_id(run_id))
    except (RunOutputError, OSError, ValueError, KeyError) as error:
        raise PortfolioError(f"combined run {run_id}: {error}") from error
    combination = manifest.get("combination")
    if manifest.get("engine") != "combiner" or not isinstance(combination, dict):
        raise PortfolioError(f"run {run_id} is not a combination (engine {manifest.get('engine')!r})")
    recorded = {c["run_id"]: c["manifest_sha256"] for c in manifest["config"]["components"]}
    sleeves = []
    for component in combination["components"]:
        sleeve = _load_sleeve(runs, component)
        if manifest_sha256(sleeve.manifest) != recorded.get(component):
            raise PortfolioError(f"component {component}: manifest hash differs from the one recorded "
                                 f"in combination {run_id}")
        sleeves.append(sleeve)
    ids = [s.run_id for s in sleeves]
    cash = float(manifest["config"]["initial_cash"])
    dates = list(tables["returns"]["date"])
    frame = pd.DataFrame({s.run_id: s.returns.set_index("date").loc[dates, "net_return"].astype(float)
                          for s in sleeves})
    portfolio_net = tables["returns"].set_index("date")["net_return"].astype(float)
    weights = np.array([float(combination["weights_first_rebalance"][i]) for i in ids])
    recon = reconcile(tables, sleeves)
    empty_fills = tables["fills"]
    per_sleeve = {s.run_id: summarize(s.returns, empty_fills.iloc[0:0], _initial_cash(s.returns, cash))
                  for s in sleeves}
    passed = recon["max_abs_return_error"] <= RECONCILE_TOLERANCE
    report = {
        "schema": SCHEMA,
        "run_id": run_id,
        "created_utc": now.isoformat(),
        "method": combination["method"],
        "components": ids,
        "use": manifest.get("use", "engineering"),
        "labels": manifest.get("labels", []),
        "universe_kind": manifest.get("universe_kind"),
        "exploratory": bool(combination.get("exploratory", False)),
        "trial": combination.get("trial"),
        "sessions": len(dates),
        "metrics": {"combined": summarize(tables["returns"], tables["fills"], cash), "sleeves": per_sleeve},
        "correlation": {"instruments": ids, "matrix": frame.corr().to_numpy(dtype=float).tolist()},
        "diversification": diversification(frame, portfolio_net, weights),
        "reconciliation": {**recon, "tolerance": RECONCILE_TOLERANCE,
                           "status": "PASS" if passed else "FAIL"},
        "limitations": LIMITATIONS,
    }
    return _clean(report)


def cmd_report(args) -> int:
    root, runs = _roots(args)
    report = build_report(runs, args.run_id, datetime.now(timezone.utc))
    folder = root / "portfolio" / _safe_id(args.run_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "report.json"
    try:
        with open(path, "x", encoding="utf-8") as stream:
            stream.write(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    except FileExistsError as error:
        raise PortfolioError(f"report already exists: {path}") from error
    print(path)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    comb = sub.add_parser("combine")
    comb.add_argument("--run-id", action="append", required=True, help="component run id (repeat; at least two)")
    comb.add_argument("--method", choices=METHODS, required=True)
    comb.add_argument("--gross", type=float, default=1.0)
    comb.add_argument("--vol-window", type=int, default=60)
    comb.add_argument("--rebalance", choices=REBALANCE, default="monthly")
    comb.add_argument("--rebalance-cost-bps", type=float, default=5.0)
    comb.add_argument("--initial-cash", type=float, default=100_000.0)
    comb.add_argument("--cycle-id", help="record one ledger trial under this research cycle")
    comb.add_argument("--exploratory", action="store_true", help="record no trial; the manifest says so")
    comb.add_argument("--runs-root", type=Path)
    comb.add_argument("--ledger-dir", type=Path, default=LEDGER_DIR)
    comb.add_argument("--root", type=Path)
    comb.set_defaults(fn=cmd_combine)
    rep = sub.add_parser("report")
    rep.add_argument("--run-id", required=True)
    rep.add_argument("--runs-root", type=Path)
    rep.add_argument("--root", type=Path)
    rep.set_defaults(fn=cmd_report)
    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except DataAbsent as error:
        print(error, file=sys.stderr)
        return 2
    except (PortfolioError, OSError, ValueError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
