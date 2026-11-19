"""Portfolio combiner: several run outputs into one ``run-output/v1`` (``engine: "combiner"``).

Sleeve-level model, not a share-level portfolio. Each sleeve contributes its own run's
``net_return`` series (already net of its own trading costs). The account is long-only
with no leverage: sleeve weights ``w_i >= 0`` and ``sum(w_i) <= gross <= 1``; whatever is
not allocated is cash and earns zero. Positions in the output are sleeves
(``instrument`` is the component run id, ``quantity`` is 0 by definition, ``weight`` is the
drifted weight at the session close).

Timing convention: weights chosen from information up to the close of session ``t-1``
apply to the return of session ``t``. A rebalance "on session t" computes the new weights
from data through ``t-1`` (inverse-volatility uses the ``vol_window`` sessions ending at
``t-1``) and they apply from ``t``. The first session is allocated from an all-cash start
and charged turnover cost like any rebalance. Rebalance sessions: the first session, then
the first session of each calendar month (``monthly``) or every session (``daily``).

Per session ``t`` with start weights ``w`` (after any rebalance) and sleeve returns ``r``:

- ``gross_return = sum(w_i * r_i)`` (recorded directly, so a floored wipe-out day still reconciles); ``cost = rebalance_cost_bps * sum|w_target - w_drifted| / 10_000``
  on rebalance sessions (drifted weights are zero on the first session); ``net_return = gross_return - cost``;
  ``equity_t = equity_{t-1} * (1 + net_return)``.
- Drift to the close: ``w_i <- w_i (1 + r_i) / (1 + gross_return)`` (cash is a zero-return asset).

No leverage and no negative cash, even for a sleeve return of -100% or worse: each sleeve's
return is floored at -1 (its growth factor ``1 + r_i`` is floored at 0, so a sleeve can wipe
out its own value but never more), and with ``w_i >= 0`` and ``sum(w_i) <= 1`` the portfolio
return is at least ``-sum(w_i) >= -1``. The net return and equity are floored at -100% and 0;
at zero equity the account stays in cash (all weights zero, all returns zero).
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from research.evaluation.metrics import ZERO_STD
from research.evaluation.run_output import COLUMNS, DTYPES, config_hash, new_run_id

__all__ = ["METHODS", "REBALANCE", "PortfolioError", "Sleeve", "combine", "build_manifest",
           "reconcile", "start_weights", "rebalance_turnover", "manifest_sha256", "ENGINE", "ENGINE_VERSION"]

METHODS = ("equal", "inverse_vol")
REBALANCE = ("monthly", "daily")
ENGINE = "combiner"
ENGINE_VERSION = "combiner/v1"


class PortfolioError(ValueError):
    """Raised for an invalid combination request or inputs."""


@dataclass(frozen=True)
class Sleeve:
    run_id: str
    manifest: dict
    returns: pd.DataFrame
    fills: pd.DataFrame | None = None  # the component's own fills (report metrics only; the combiner ignores them)


def manifest_sha256(manifest: dict) -> str:
    """SHA-256 of the manifest as ``write_run`` serialises it (equals the file's hash when read back unchanged)."""
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, indent=2).encode("utf-8")).hexdigest()


def _validate(sleeves, method, gross, vol_window, rebalance, bps, initial_cash):
    if method not in METHODS:
        raise PortfolioError(f"unknown method {method!r}; expected one of {METHODS}")
    if rebalance not in REBALANCE:
        raise PortfolioError(f"unknown rebalance {rebalance!r}; expected one of {REBALANCE}")
    if not (isinstance(gross, (int, float)) and 0 < gross <= 1):
        raise PortfolioError(f"gross must be in (0, 1], got {gross!r}")
    if not (isinstance(vol_window, int) and not isinstance(vol_window, bool) and vol_window >= 2):
        raise PortfolioError(f"vol_window must be an integer >= 2, got {vol_window!r}")
    if not (math.isfinite(bps) and bps >= 0):
        raise PortfolioError(f"rebalance_cost_bps must be finite and >= 0, got {bps!r}")
    if not (math.isfinite(initial_cash) and initial_cash > 0):
        raise PortfolioError(f"initial_cash must be positive, got {initial_cash!r}")
    if len(sleeves) < 2:
        raise PortfolioError(f"a combination needs at least two sleeves, got {len(sleeves)}")
    ids = [s.run_id for s in sleeves]
    if len(set(ids)) != len(ids):
        raise PortfolioError(f"duplicate component run ids: {sorted(i for i in set(ids) if ids.count(i) > 1)}")
    first = list(sleeves[0].returns["date"])
    if not first:
        raise PortfolioError(f"component {ids[0]} has no sessions")
    for s in sleeves[1:]:
        dates = list(s.returns["date"])
        if dates != first:
            raise PortfolioError(_first_difference(sleeves[0].run_id, first, s.run_id, dates))
    for s in sleeves:
        _check_stock_labels(s)
    for s in sleeves:
        values = s.returns["net_return"].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            bad = s.returns["date"].iloc[int(np.argmax(~np.isfinite(values)))]
            raise PortfolioError(f"component {s.run_id} has a non-finite net_return on {bad}")


def _universe_kinds(node) -> set[str]:
    """Every ``universe_kind`` value found anywhere in a (nested) datasets structure."""
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "universe_kind" and isinstance(value, str) and value:
                found.add(value)
            else:
                found |= _universe_kinds(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            found |= _universe_kinds(value)
    return found


def _check_stock_labels(sleeve: Sleeve) -> None:
    """Defence in depth: a component whose datasets carry a ``universe_kind`` must carry labels too."""
    if _universe_kinds(sleeve.manifest.get("datasets")) and not sleeve.manifest.get("labels"):
        raise PortfolioError(
            f"component {sleeve.run_id} has a dataset universe_kind but its manifest has no labels; "
            "refusing to combine it without the survivor-bias labels it should carry")


def _first_difference(id_a, dates_a, id_b, dates_b) -> str:
    for i, (x, y) in enumerate(zip(dates_a, dates_b)):
        if x != y:
            return (f"component {id_b} dates differ from {id_a} at session {i}: "
                    f"{id_a} has {x}, {id_b} has {y}")
    longer, extra = (id_a, dates_a[len(dates_b)]) if len(dates_a) > len(dates_b) else (id_b, dates_b[len(dates_a)])
    return (f"component {id_b} has {len(dates_b)} sessions but {id_a} has {len(dates_a)}; "
            f"first extra session is {extra} in {longer}")


def _target_weights(method, ids, returns, t, gross, window, dates):
    """Target sleeve weights and trailing sigmas for a rebalance on session ``t`` (information through t-1)."""
    n = len(ids)
    if method == "equal" or t < window:
        return np.full(n, gross / n), None
    history = returns[t - window:t]  # sessions t-window .. t-1
    sigma = history.std(axis=0, ddof=1)
    for i, s in enumerate(sigma):
        if not np.isfinite(s) or s <= ZERO_STD:
            raise PortfolioError(
                f"component {ids[i]} has zero or non-finite volatility over the {window} sessions "
                f"{dates[t - window]}..{dates[t - 1]} before rebalance session {dates[t]} (index {t}); "
                "a sleeve with a leading warm-up (no position, constant returns) is the likely cause")
    inv = 1.0 / sigma
    return gross * inv / inv.sum(), sigma


def combine(sleeves: list[Sleeve], method: str, *, gross: float = 1.0, vol_window: int = 60,
            rebalance: str = "monthly", rebalance_cost_bps: float = 5.0,
            initial_cash: float = 100_000.0) -> dict[str, pd.DataFrame]:
    """Combine sleeve return series into the four ``run-output/v1`` tables (see the module docstring)."""
    _validate(sleeves, method, gross, vol_window, rebalance, rebalance_cost_bps, initial_cash)
    ids = [s.run_id for s in sleeves]
    dates = list(sleeves[0].returns["date"])
    raw = np.column_stack([s.returns["net_return"].to_numpy(dtype=float) for s in sleeves])
    clamped = np.maximum(raw, -1.0)  # a sleeve can lose its whole value, never more: no leverage
    n = len(ids)

    drifted = np.zeros(n)
    equity_prev = float(initial_cash)
    ret_rows, pos_rows, sig_rows = [], [], []
    for t, date in enumerate(dates):
        alive = equity_prev > 0
        is_rebalance = alive and (t == 0 or rebalance == "daily" or dates[t - 1][:7] != date[:7])
        cost = 0.0
        if is_rebalance:
            target, sigma = _target_weights(method, ids, raw, t, gross, vol_window, dates)
            cost = rebalance_cost_bps * float(np.abs(target - drifted).sum()) / 10_000
            start = target
            for i, run_id in enumerate(ids):
                sig_rows.append((date, run_id, "target_weight", float(target[i])))
                if sigma is not None:
                    sig_rows.append((date, run_id, "sleeve_vol", float(sigma[i])))
        else:
            start = drifted if alive else np.zeros(n)
        gross_r = float(start @ clamped[t])
        net = max(gross_r - cost, -1.0)
        equity = equity_prev * (1 + net)
        growth = start * (1 + clamped[t])
        total = float(growth.sum() + (1.0 - start.sum()))
        drifted = growth / total if (total > 0 and equity > 0) else np.zeros(n)
        ret_rows.append((date, gross_r, cost, net, equity))
        for i, run_id in enumerate(ids):
            pos_rows.append((date, run_id, 0, float(drifted[i])))
        equity_prev = equity
    return {
        "returns": _frame("returns", ret_rows),
        "positions": _frame("positions", pos_rows),
        "signals": _frame("signals", sig_rows),
        "fills": _frame("fills", []),
    }


def _frame(name: str, rows: list[tuple]) -> pd.DataFrame:
    cols = COLUMNS[name]
    frame = pd.DataFrame(rows, columns=list(cols))
    for col in cols:
        kind = DTYPES[name][col]
        if kind == "float64":
            frame[col] = frame[col].astype("float64")
        elif kind == "int64":
            frame[col] = frame[col].astype("int64")
        else:
            frame[col] = frame[col].astype(object)
    return frame


def _label_union(sleeves: list[Sleeve]) -> tuple[list[str], list[str]]:
    labels = sorted({lab for s in sleeves for lab in (s.manifest.get("labels") or [])})
    kinds = sorted({k for s in sleeves
                    for k in ({s.manifest["universe_kind"]} if s.manifest.get("universe_kind") else set())
                    | _universe_kinds(s.manifest.get("datasets"))})
    return labels, kinds


def build_manifest(sleeves: list[Sleeve], method: str, params: dict, tables: dict[str, pd.DataFrame],
                   now: datetime, code_commit: str, trial: dict | None = None,
                   exploratory: bool = False) -> dict:
    """A manifest that passes ``write_run``. Exactly one of ``trial`` (``{cycle_id, trial_number}``)
    and ``exploratory=True`` is required: a combination is never written unrecorded."""
    if (trial is None) == (not exploratory):
        raise PortfolioError("provide exactly one of trial and exploratory=True")
    ids = [s.run_id for s in sleeves]
    config = {
        "method": method,
        "vol_window": params.get("vol_window", 60),
        "rebalance": params.get("rebalance", "monthly"),
        "gross": params.get("gross", 1.0),
        "rebalance_cost_bps": params.get("rebalance_cost_bps", 5.0),
        "initial_cash": params.get("initial_cash", 100_000.0),
        "components": [{"run_id": s.run_id, "manifest_sha256": manifest_sha256(s.manifest)} for s in sleeves],
    }
    first = tables["signals"]
    first = first[(first["stage"] == "target_weight") & (first["date"] == tables["returns"]["date"].iloc[0])]
    combination = {
        "method": method,
        "components": ids,
        "weights_first_rebalance": {str(r.instrument): float(r.value) for r in first.itertuples()},
    }
    if exploratory:
        combination["exploratory"] = True
    else:
        combination["trial"] = {"cycle_id": trial["cycle_id"], "trial_number": trial["trial_number"]}
    manifest = {
        "run_id": new_run_id(config, now),
        "created_utc": now.isoformat(),
        "code_commit": code_commit,
        "config": config,
        "config_hash": config_hash(config),
        "engine": ENGINE,
        "engine_version": ENGINE_VERSION,
        "datasets": {s.run_id: s.manifest.get("datasets") for s in sleeves},
        "coverage": {"instruments": ids, "sessions": len(tables["returns"])},
        "parent_run": None,
        "combination": combination,
    }
    if all(s.manifest.get("use") == "financial" for s in sleeves):
        manifest["use"] = "financial"
        hashes = {s.manifest.get("acceptance_sha256") for s in sleeves}
        manifest["acceptance_sha256"] = hashes.pop() if len(hashes) == 1 else None
    else:
        manifest["use"] = "engineering"
    labels, kinds = _label_union(sleeves)
    if labels:
        manifest["labels"] = labels
    if kinds:
        manifest["universe_kind"] = kinds[0] if len(kinds) == 1 else ",".join(kinds)
    return manifest


def _target_and_positions(tables, ids):
    dates = list(tables["returns"]["date"])
    pos = tables["positions"].pivot(index="date", columns="instrument", values="weight").loc[dates, ids]
    sig = tables["signals"]
    target = (sig[sig["stage"] == "target_weight"].pivot(index="date", columns="instrument", values="value")
              .reindex(columns=ids))
    return dates, pos, target


def start_weights(tables: dict[str, pd.DataFrame], ids: list[str]) -> np.ndarray:
    """Start-of-session weights actually used, shape ``(sessions, len(ids))``: the ``target_weight``
    signals on a rebalance session, else the previous close's position weights (zero before the first)."""
    dates, pos, target = _target_and_positions(tables, ids)
    out = np.zeros((len(dates), len(ids)))
    prev = np.zeros(len(ids))
    for t, date in enumerate(dates):
        out[t] = target.loc[date].to_numpy(dtype=float) if date in target.index else prev
        prev = pos.iloc[t].to_numpy(dtype=float)
    return out


def rebalance_turnover(tables: dict[str, pd.DataFrame], ids: list[str]) -> float:
    """Sum over rebalance sessions of ``|w_target - w_drifted|`` (drifted weights are zero on the first)."""
    dates, pos, target = _target_and_positions(tables, ids)
    prev = np.zeros(len(ids))
    total = 0.0
    for t, date in enumerate(dates):
        if date in target.index:
            total += float(np.abs(target.loc[date].to_numpy(dtype=float) - prev).sum())
        prev = pos.iloc[t].to_numpy(dtype=float)
    return total


def reconcile(tables: dict[str, pd.DataFrame], sleeves: list[Sleeve]) -> dict[str, float]:
    """Recompute portfolio gross return from the recorded weights and the sleeve returns.

    Start weights of session ``t`` are the ``target_weight`` signals on a rebalance session, else the
    previous close's position weights. Returns ``{max_abs_return_error, weights_sum_max, cash_min,
    cost_total}`` (``cash_min`` is ``1 - max sum of weights``, unscaled by ``gross``; rounding noise
    below 1e-12 in magnitude is reported as 0.0)."""
    ids = [s.run_id for s in sleeves]
    returns = tables["returns"]
    dates, pos, _ = _target_and_positions(tables, ids)
    clamped = np.maximum(np.column_stack([s.returns.set_index("date").loc[dates, "net_return"].to_numpy(dtype=float)
                                          for s in sleeves]), -1.0)
    weights = start_weights(tables, ids)
    worst = 0.0
    for t in range(len(dates)):
        worst = max(worst, abs(float(weights[t] @ clamped[t]) - float(returns["gross_return"].iloc[t])))
    sums = pos.sum(axis=1)
    cash_min = float((1.0 - sums).min())
    return {
        "max_abs_return_error": float(worst),
        "weights_sum_max": float(sums.max()),
        "cash_min": 0.0 if abs(cash_min) < 1e-12 else cash_min,
        "cost_total": float(returns["cost"].sum()),
    }
