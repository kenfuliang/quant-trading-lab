"""Trust statistics: PSR, DSR and PBO (CSCV).

Written from the published definitions:
- Bailey & Lopez de Prado, "The Sharpe Ratio Efficient Frontier" (PSR).
- Bailey & Lopez de Prado, "The Deflated Sharpe Ratio" (expected maximum Sharpe, DSR).
- Bailey, Borwein, Lopez de Prado & Zhu, "The Probability of Backtest Overfitting" (CSCV, PBO).

Sharpe ratios here are per period (not annualised, zero risk-free rate). Skewness and
kurtosis are population moments of the sample; kurtosis is non-excess (normal = 3).
Degenerate inputs return ``{"value": None, "reason": ...}``; nothing raises or yields NaN.
"""
from __future__ import annotations

import itertools
import math
from statistics import NormalDist

import numpy as np
import pandas as pd

__all__ = ["dsr", "expected_max_sharpe", "pbo", "psr", "sharpe_per_period"]

_ND = NormalDist()
EULER_GAMMA = 0.5772156649


def _clean(returns) -> np.ndarray:
    return np.asarray(returns, dtype=float).ravel()


def sharpe_per_period(returns) -> float | None:
    """Mean / sample std (ddof 1) of ``returns``; ``None`` if n < 2 or std is 0."""
    r = _clean(returns)
    if r.size < 2 or not np.all(np.isfinite(r)):
        return None
    std = r.std(ddof=1)
    if not std > 1e-15:
        return None
    return float(r.mean() / std)


def _none(reason: str, **extra) -> dict:
    return {"value": None, "reason": reason, **extra}


def psr(returns, sr_benchmark: float = 0.0) -> dict:
    """Probabilistic Sharpe Ratio.

    PSR = Phi((SR - SR*) * sqrt(n-1) / sqrt(1 - g3*SR + (g4-1)/4 * SR^2)), with per-period
    SR, population skew g3 and non-excess kurtosis g4.
    """
    r = _clean(returns)
    n = int(r.size)
    if not math.isfinite(sr_benchmark):
        return _none("sr_benchmark is not finite", n=n)
    if n < 3:
        return _none("fewer than 3 observations", n=n)
    sr = sharpe_per_period(r)
    if sr is None:
        return _none("zero or undefined standard deviation", n=n)
    dev = r - r.mean()
    sd0 = math.sqrt(float((dev ** 2).mean()))
    skew = float((dev ** 3).mean() / sd0 ** 3)
    kurt = float((dev ** 4).mean() / sd0 ** 4)
    denom = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr ** 2
    if not denom > 0:
        return _none("non-positive Sharpe variance term", sharpe=sr, skew=skew, kurtosis=kurt, n=n)
    z = (sr - sr_benchmark) * math.sqrt(n - 1) / math.sqrt(denom)
    return {"value": float(_ND.cdf(z)), "sharpe": sr, "skew": skew, "kurtosis": kurt, "n": n}


def expected_max_sharpe(n_trials: int, sr_variance: float) -> float:
    """Expected maximum per-period Sharpe over ``n_trials`` independent trials with
    cross-trial Sharpe variance ``sr_variance``:
    sqrt(V) * ((1-g) * Phi^-1(1 - 1/N) + g * Phi^-1(1 - 1/(N e))), g = Euler-Mascheroni."""
    n = int(n_trials)
    if n < 2:
        raise ValueError("expected_max_sharpe needs n_trials >= 2")
    if not sr_variance >= 0 or not math.isfinite(sr_variance):
        raise ValueError("expected_max_sharpe needs a finite sr_variance >= 0")
    g = EULER_GAMMA
    return math.sqrt(sr_variance) * (
        (1 - g) * _ND.inv_cdf(1 - 1 / n) + g * _ND.inv_cdf(1 - 1 / (n * math.e))
    )


def dsr(returns, n_trials: int, sr_variance: float) -> dict:
    """Deflated Sharpe Ratio: PSR with benchmark SR* = ``expected_max_sharpe``."""
    if n_trials < 2:
        return _none("n_trials < 2")
    if not sr_variance > 0 or not math.isfinite(sr_variance):
        return _none("sr_variance must be positive")
    bench = expected_max_sharpe(n_trials, sr_variance)
    out = psr(returns, sr_benchmark=bench)
    out["sr_benchmark"] = bench
    out["n_trials"] = int(n_trials)
    return out


def pbo(perf: pd.DataFrame, n_partitions: int = 16) -> dict:
    """Probability of Backtest Overfitting via CSCV.

    ``perf`` has one row per period and one column per configuration (net returns). Rows are cut
    into ``n_partitions`` equal blocks (the remainder rows at the end are dropped). For every
    combination of S/2 blocks as in-sample (the complement is out-of-sample), the in-sample best
    column by Sharpe is ranked out-of-sample: omega = rank/(N+1) (average rank for ties),
    logit = ln(omega / (1 - omega)). PBO is the share of logits <= 0.
    """
    s = int(n_partitions)
    if s < 2 or s % 2:
        return _none("n_partitions must be even and >= 2", logits=[], n_combinations=0)
    x = np.asarray(perf, dtype=float)
    if x.ndim != 2 or x.shape[1] < 2:
        return _none("need at least 2 columns", logits=[], n_combinations=0)
    t, n = x.shape
    if t < s:
        return _none("fewer rows than partitions", logits=[], n_combinations=0)
    if not np.all(np.isfinite(x)):
        return _none("non-finite values", logits=[], n_combinations=0)
    m = t // s
    if m < 2:
        return _none("fewer than 2 rows per partition", logits=[], n_combinations=0)
    blocks = x[: m * s].reshape(s, m, n)
    # Constant columns (any non-zero level) have zero true variance; the sums-of-squares route
    # would leave rounding noise there and a huge spurious Sharpe, so exclude them exactly.
    # They are dropped as configurations (they would only inflate N in the rank).
    keep = np.ptp(x[: m * s], axis=0) > 0
    if keep.sum() < 2:
        return _none("fewer than 2 non-constant columns", logits=[], n_combinations=0)
    x = x[:, keep]
    n = x.shape[1]
    constant = np.zeros(n, dtype=bool)
    blocks = x[: m * s].reshape(s, m, n)
    p_sum = blocks.sum(axis=1)
    p_sq = (blocks ** 2).sum(axis=1)
    combos = np.array(list(itertools.combinations(range(s), s // 2)))
    total_sum, total_sq = p_sum.sum(axis=0), p_sq.sum(axis=0)
    half_cnt = m * (s // 2)

    def sharpe(sums, sqs, cnt):
        mean = sums / cnt
        var = (sqs - cnt * mean ** 2) / (cnt - 1)
        scale = np.maximum(np.maximum(mean ** 2, sqs / cnt), 1e-300)
        ok = (var > 1e-12 * scale) & ~constant
        with np.errstate(divide="ignore", invalid="ignore"):
            sr = mean / np.sqrt(np.where(ok, var, 1.0))
        return np.where(ok, sr, -np.inf)

    is_sum = p_sum[combos].sum(axis=1)
    is_sq = p_sq[combos].sum(axis=1)
    sr_is = sharpe(is_sum, is_sq, half_cnt)
    sr_oos = sharpe(total_sum - is_sum, total_sq - is_sq, half_cnt)
    best = sr_is.argmax(axis=1)
    chosen = sr_oos[np.arange(len(combos)), best][:, None]
    rank = (sr_oos < chosen).sum(axis=1) + 0.5 * ((sr_oos == chosen).sum(axis=1) + 1)
    omega = rank / (n + 1)
    logits = np.log(omega / (1 - omega))
    return {
        "value": float((logits <= 0).mean()),
        "logits": [float(v) for v in logits],
        "n_combinations": int(len(combos)),
        "reason": None,
        "n_partitions": s,
        "rows_used": int(m * s),
    }
