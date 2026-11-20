"""Candidate confirmation core: re-run a stored screening run's frozen candidate on the
NautilusTrader engine and prove the two engines agree.

Pure functions over plain values; the command (``scripts/confirm.py``) resolves roots, data
and gates. The candidate is exactly what the screening manifest records (strategy spec,
market config, instruments, dataset, optional membership ids). Nothing is tuned.

The stored run tables carry no cash, so ``confirm`` re-runs the screening engine in-process
and requires its four tables to equal the stored tables exactly (``check_exact``, same
dtypes): that ties the stored run id to the candidate. Then ``parity.compare`` judges screen
versus native.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from research.evaluation.engine_contract import EngineResult
from research.evaluation.market_model import MarketConfig, MarketData
from research.evaluation.native_engine import run_native
from research.evaluation.parity import ParityReport, compare
from research.evaluation.run_output import COLUMNS, config_hash, new_run_id
from research.evaluation.screening_engine import run_screen

RECEIPT_SCHEMA = "parity-receipt/v1"
KIND = "candidate-confirmation"
CANDIDATE_KEYS = ("strategy", "market", "instruments")
KNOWN_CONFIG_KEYS = ("engine", *CANDIDATE_KEYS, "ladder", "universe")
COPIED_KEYS = ("use", "acceptance_sha256", "labels", "universe_kind")
FINANCIAL_KEYS = ("use", "acceptance_sha256")
TOLERANCES = {"quantities": "identical", "fill_dates": "identical", "cash_equity_usd_per_session": 0.01}
CASH_INTEREST = "not modelled"
ENGINEERING_USE = "engineering evidence, not financial use; offline and order-free"
FINANCIAL_USE = ("confirmation of a financial-use screening run; offline and order-free; "
                 "binds a keep only with a clean commit and the run's accepted quality report")


class ConfirmError(ValueError):
    """The stored run cannot be confirmed (not a screen run, incomplete, or not reproducible)."""


@dataclass(frozen=True)
class Confirmation:
    screen: EngineResult
    native: EngineResult
    report: ParityReport
    stored_identical: bool
    screen_seconds: float
    native_seconds: float


def candidate_from_manifest(manifest: dict) -> dict:
    """Rebuild the frozen candidate inputs from a screening run manifest."""
    run_id = manifest.get("run_id")
    config = manifest.get("config")
    if manifest.get("engine") != "screen" or not isinstance(config, dict) or config.get("engine") != "screen":
        raise ConfirmError(f"run {run_id} engine is {manifest.get('engine')!r}; only a screen run can be confirmed")
    unknown = sorted(set(config) - set(KNOWN_CONFIG_KEYS))
    if unknown:
        raise ConfirmError(f"run {run_id} config has keys {unknown} that confirmation does not rebuild; "
                           "refusing to confirm a candidate it cannot fully reproduce")
    missing = [key for key in CANDIDATE_KEYS if key not in config]
    if missing:
        raise ConfirmError(f"run {run_id} config is missing {missing}; it is not a ladder or analysis screening run")
    strategy, market, instruments = config["strategy"], config["market"], config["instruments"]
    if (not isinstance(strategy, dict) or not isinstance(market, dict)
            or not isinstance(instruments, list) or not instruments):
        raise ConfirmError(f"run {run_id} config strategy, market or instruments is malformed")
    try:
        market_config = MarketConfig(**market)
    except TypeError as exc:
        raise ConfirmError(f"run {run_id} market config cannot be rebuilt: {exc}") from exc
    datasets = manifest.get("datasets")
    if not isinstance(datasets, dict):
        raise ConfirmError(f"run {run_id} manifest has no datasets")
    universe = config.get("universe")
    if universe is not None and not (
            isinstance(universe, dict) and universe.get("membership_id") and universe.get("identity_id")):
        raise ConfirmError(f"run {run_id} is masked but records no membership_id and identity_id")
    return {"strategy": strategy, "market": market_config, "instruments": tuple(instruments),
            "universe": universe, "datasets": datasets}


def _normalise(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.sort_values(list(frame.columns), kind="stable").reset_index(drop=True)


def _first_difference(name: str, stored: pd.DataFrame, rerun: pd.DataFrame) -> str:
    if len(stored) != len(rerun):
        days = sorted(set(stored["date"]) ^ set(rerun["date"])) or ["n/a"]
        return f"{name}: {len(stored)} stored rows vs {len(rerun)} re-run rows (first differing date {days[0]})"
    for column in stored.columns:
        if stored[column].dtype != rerun[column].dtype:
            return f"{name}.{column}: dtype {stored[column].dtype} stored vs {rerun[column].dtype} re-run"
        bad = (stored[column] != rerun[column]) & ~(stored[column].isna() & rerun[column].isna())
        if bad.any():
            first = bad.idxmax()
            return (f"{name}.{column} on {stored['date'][first]}: stored {stored[column][first]!r} "
                    f"vs re-run {rerun[column][first]!r}")
    return f"{name}: differs"


def stored_difference(stored: dict[str, pd.DataFrame], rerun: EngineResult) -> str | None:
    """First difference between the stored tables and the re-run's, or None when identical."""
    for name, columns in COLUMNS.items():
        a, b = _normalise(stored[name]), _normalise(getattr(rerun, name)[list(columns)])
        try:
            pd.testing.assert_frame_equal(a, b, check_exact=True, check_dtype=True)
        except AssertionError:
            return _first_difference(name, a, b)
    return None


def confirm(data: MarketData, target_fn, market: MarketConfig, stored_tables: dict[str, pd.DataFrame], *,
            run_screen_fn=run_screen, run_native_fn=run_native) -> Confirmation:
    """Re-run the screen engine, require it to equal the stored tables, run native, compare."""
    started = time.perf_counter()
    screen = run_screen_fn(data, target_fn, market)
    screen_seconds = time.perf_counter() - started
    difference = stored_difference(stored_tables, screen)
    if difference is not None:
        raise ConfirmError(f"stored screening run is not reproducible: {difference}")
    started = time.perf_counter()
    native = run_native_fn(data, target_fn, market)
    native_seconds = time.perf_counter() - started
    return Confirmation(screen, native, compare(screen, native), True, screen_seconds, native_seconds)


def native_manifest(screen_manifest: dict, native_result: EngineResult, *, code_commit: str, now: datetime,
                    engine_version: str, agreed: bool = True) -> dict:
    """The NautilusTrader run manifest: the screening config with only ``engine`` changed.

    When the engines did not agree (``agreed`` False) the run is written without ``use`` and
    ``acceptance_sha256``, so it fails the financial-run gate on its own and can back no keep."""
    config = {key: value for key, value in screen_manifest["config"].items() if key != "ladder"}
    config["engine"] = native_result.engine
    manifest = {
        "run_id": new_run_id(config, now),
        "created_utc": now.isoformat(),
        "code_commit": code_commit,
        "config": config,
        "config_hash": config_hash(config),
        "engine": native_result.engine,
        "engine_version": engine_version,
        "datasets": screen_manifest["datasets"],
        "coverage": {"instruments": list(config["instruments"]), "sessions": len(native_result.returns)},
        "parent_run": screen_manifest["run_id"],
    }
    for key in COPIED_KEYS:
        if key in screen_manifest and (agreed or key not in FINANCIAL_KEYS):
            manifest[key] = screen_manifest[key]
    return manifest


def build_receipt(*, parity_id: str, now: datetime, command: list[str], code_commit: str,
                  screen_manifest: dict, screen_sha256: str, native_run_id: str, native_sha256: str,
                  confirmation: Confirmation, runs_root: str, calendar: dict | None = None) -> dict:
    """The ``parity-receipt/v1`` document for a candidate confirmation."""
    config = screen_manifest["config"]
    datasets = screen_manifest["datasets"]
    financial = screen_manifest.get("use") == "financial"
    report = confirmation.report
    sha = datasets.get("manifest_sha256")
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "kind": KIND,
        "parity_id": parity_id,
        "run_id": native_run_id,
        "created_utc": now.isoformat(),
        "use": ENGINEERING_USE if not financial else FINANCIAL_USE,
        "command": list(command),
        "code_commit": code_commit,
        "inputs": datasets,
        "datasets": datasets,
        "instruments": list(config["instruments"]),
        "max_instruments": None,
        "timing_only": False,
        "strategy": config["strategy"],
        "market": config["market"],
        "tolerances": TOLERANCES,
        "cash_interest": CASH_INTEREST,
        "runs_root": runs_root,
        "calendar": calendar,
        "candidate": {
            "strategy": config["strategy"],
            "market": config["market"],
            "instruments": list(config["instruments"]),
            "ladder": config.get("ladder"),
            "universe": config.get("universe"),
        },
        "timing": {"screening_seconds": confirmation.screen_seconds,
                   "native_seconds": confirmation.native_seconds},
        "runs": {"screen": {"run_id": screen_manifest["run_id"], "manifest_sha256": screen_sha256},
                 "nautilus": {"run_id": native_run_id, "manifest_sha256": native_sha256}},
        "stored_screen_identical": confirmation.stored_identical,
        "bindable": bool(isinstance(sha, str) and sha),
        "status": "passed" if report.passed else "mismatch",
        "passed": report.passed,
        "mismatch_count": len(report.mismatches),
        "mismatches": list(report.mismatches),
        "error": None,
    }
    if financial:
        receipt["run_use"] = "financial"
        receipt["acceptance_sha256"] = screen_manifest.get("acceptance_sha256")
    for key in ("labels", "universe_kind"):
        if key in screen_manifest:
            receipt[key] = screen_manifest[key]
    return receipt
