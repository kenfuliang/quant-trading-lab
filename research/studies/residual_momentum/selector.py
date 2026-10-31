"""Monthly residual-rank proposals, not a paper reproduction or order runner.

Inputs are fractional monthly total returns, explicit per-cell stock availability,
and one availability time for each factor-row vintage. The caller must qualify
universe membership, actions and vintage truth separately. No availability is
inferred from observation dates. No input is mutated and no future row is fitted.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

FACTORS = ("mkt_rf", "smb", "hml", "rf")


def _utc(value):
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp) or timestamp.tzinfo is None:
        raise ValueError("Availability and decision times must be explicit timezone-aware timestamps")
    return timestamp.tz_convert("UTC")


def score_month(returns, factors, stock_available_at, factor_available_at,
                *, formation_month, decision_time):
    """Return ranked scores and matched-universe controls for one formation month.

    Regression t-36..t-1; residual and raw-return signal t-12..t-2. An unavailable
    common factor blocks the whole proposal. A stock's missing/late history only
    excludes that stock, with a named reason. All controls share the resulting
    eligible set; this does not establish point-in-time universe eligibility.
    """
    month = pd.Period(formation_month, freq="M")
    cutoff = _utc(decision_time)
    if cutoff.tz_localize(None).to_period("M") != month:
        raise ValueError("Decision cutoff must be within the declared UTC formation month")
    for frame in (returns, factors):
        if not isinstance(frame.index, pd.PeriodIndex) or frame.index.freqstr != "M":
            raise ValueError("Returns and factors require monthly PeriodIndex")
        if frame.index.has_duplicates or frame.columns.has_duplicates:
            raise ValueError("Duplicate months or columns are invalid")
    if not all(isinstance(c, str) and c for c in returns.columns):
        raise ValueError("Stock identifiers must be nonempty strings")
    if not stock_available_at.index.equals(returns.index) or not stock_available_at.columns.equals(returns.columns):
        raise ValueError("Stock availability must align exactly with returns")
    if not factor_available_at.index.equals(factors.index):
        raise ValueError("Factor availability must align exactly with factor vintages")
    if not set(FACTORS).issubset(factors.columns):
        raise ValueError("Missing mkt_rf/smb/hml/rf fractional-return fields")
    window = pd.period_range(month - 36, month - 1, freq="M")
    if not window.isin(factors.index).all():
        raise ValueError("Common factor history must include 36 contiguous months")
    for value in factor_available_at.loc[window]:
        if _utc(value) > cutoff:
            raise ValueError("Factor vintage was not available by decision cutoff")
    factor_values = factors.loc[window, list(FACTORS)].to_numpy(dtype=float)
    if not np.isfinite(factor_values).all():
        raise ValueError("Nonfinite common factor inputs")
    design = np.column_stack([np.ones(36), factor_values[:, :3]])
    if np.linalg.matrix_rank(design) != 4 or np.linalg.cond(design) > 1e8:
        raise ValueError("Rank-deficient or ill-conditioned factor regression")
    scores, excluded, coefficients = {}, {}, {}
    for symbol in sorted(returns.columns):
        if not window.isin(returns.index).all():
            excluded[symbol] = "missing_months"
            continue
        values = returns.loc[window, symbol].to_numpy(dtype=float)
        if not np.isfinite(values).all() or (values < -1).any():
            excluded[symbol] = "invalid_or_missing_returns"
            continue
        try:
            times = [_utc(v) for v in stock_available_at.loc[window, symbol]]
        except (ValueError, TypeError):
            excluded[symbol] = "missing_or_naive_availability"
            continue
        if any(t > cutoff for t in times):
            excluded[symbol] = "unavailable_by_cutoff"
            continue
        excess = values - factor_values[:, 3]
        beta = np.linalg.lstsq(design, excess, rcond=None)[0]
        residuals = excess - design @ beta  # Removes fitted intercept as well.
        formation = residuals[-12:-1]  # Eleven months, excluding t-1.
        denominator = float(np.std(formation, ddof=1))
        if denominator <= 1e-12:
            excluded[symbol] = "zero_residual_volatility"
            continue
        score = float(formation.sum() / denominator)
        raw_momentum = float(np.prod(1 + values[-12:-1]) - 1)
        if not math.isfinite(score) or not math.isfinite(raw_momentum):
            excluded[symbol] = "nonfinite_score"
            continue
        scores[symbol] = {"residual": score, "ordinary": raw_momentum}
        coefficients[symbol] = dict(zip(("alpha", "mkt_rf", "smb", "hml"), map(float, beta)))
    eligible = sorted(scores)
    breadth = max(1, math.ceil(len(eligible) / 10)) if eligible else 0

    def selected_weights(key):
        selected = sorted(eligible, key=lambda s: (-scores[s][key], s))[:breadth]
        return {s: 1 / breadth for s in selected}

    return {
        "formation_month": str(month), "decision_time": cutoff.isoformat(),
        "status": "proposal_only_unqualified" if eligible else "no_eligible_targets",
        "eligible": eligible, "excluded": excluded, "scores": scores,
        "coefficients": coefficients,
        "weights": {"residual": selected_weights("residual"),
                    "ordinary": selected_weights("ordinary"),
                    "equal_weight": {s: 1 / len(eligible) for s in eligible}},
        "qualified_for_financial_run": False, "authorizes_orders": False,
    }
