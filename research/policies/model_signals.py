"""Fixed local statistical signal adaptations; see model-strategies.md."""
import numpy as np
import pandas as pd

from research.policies.daily_signals import _validate


DEFINITIONS = {
    98: ('Rolling ridge next-session return forecast long/cash adaptation',
         {'training_max': 504, 'training_min': 252, 'ridge': 10., 'refit': 'monthly',
          'features': ['return1', 'return5', 'return20', 'volatility20', 'sma50_gap']}),
    99: ('Two-component Gaussian-mixture low-volatility regime long/cash adaptation',
         {'training_sessions': 252, 'iterations': 40, 'variance_floor': 1e-8,
          'refit': 'monthly', 'posterior_threshold': .5}),
}


def _features(close):
    ret = close.pct_change(fill_method=None)
    return pd.DataFrame({'return1': ret,
                         'return5': close.pct_change(5, fill_method=None),
                         'return20': close.pct_change(20, fill_method=None),
                         'volatility20': ret.rolling(20).std(ddof=0),
                         'sma50_gap': close / close.rolling(50).mean() - 1})


def _fit_ridge(features, labels):
    """Train-only standardization; unpenalized intercept, fixed ridge10."""
    mean = features.mean(axis=0)
    scale = features.std(axis=0)
    scale = np.where(scale > 1e-12, scale, 1.)
    design = np.column_stack([np.ones(len(features)), (features - mean) / scale])
    penalty = np.diag([0.] + [10.] * features.shape[1])
    beta = np.linalg.solve(design.T @ design + penalty, design.T @ labels)
    return mean, scale, beta


def _posterior(values, weights, means, variances):
    values = np.asarray(values, dtype=float).reshape(-1, 1)
    scores = (np.log(weights) - .5 * np.log(2 * np.pi * variances)
              - .5 * (values - means) ** 2 / variances)
    scores -= scores.max(axis=1, keepdims=True)
    probabilities = np.exp(scores)
    return probabilities / probabilities.sum(axis=1, keepdims=True)


def _fit_mixture(values):
    """Deterministic two-Gaussian EM with fixed iterations and variance floor."""
    values = np.asarray(values, dtype=float)
    means = np.quantile(values, [.25, .75])
    variances = np.repeat(max(values.var(), 1e-8), 2)
    weights = np.array([.5, .5])
    for _ in range(40):
        responsibility = _posterior(values, weights, means, variances)
        mass = np.maximum(responsibility.sum(axis=0), 1e-12)
        weights = np.maximum(mass / len(values), .01)
        weights /= weights.sum()
        means = (responsibility * values[:, None]).sum(axis=0) / mass
        variances = np.maximum(
            (responsibility * (values[:, None] - means) ** 2).sum(axis=0) / mass, 1e-8)
    return weights, means, variances


def build_model_signal(raw: pd.DataFrame, strategy_id: int) -> pd.DataFrame:
    """Return boolean previous-close decision for next-open long/cash execution.

    Training is performed only on realized observations available at each close.
    No hyperparameter optimization, random seeds, external data or broker calls.
    """
    if strategy_id not in DEFINITIONS:
        raise ValueError(f'Unsupported model strategy ID: {strategy_id}')
    prices = _validate(raw)
    close = prices.close
    targets = np.zeros(len(prices), dtype=bool)
    fitted, fit_month = None, None
    returns = close.pct_change(fill_method=None).to_numpy()
    if strategy_id == 98:
        features = _features(close).to_numpy()
        # Label j is the return realized during session j+1, after feature j.
        # At close i, the most recent eligible training feature is i-1.
        labels = (prices.close / prices.open - 1).shift(-1).to_numpy()
        for i, date in enumerate(prices.index):
            if not np.isfinite(features[i]).all():
                continue
            month = (date.year, date.month)
            if fitted is None or month != fit_month:
                start = max(0, i - 504)
                x, y = features[start:i], labels[start:i]
                valid = np.isfinite(x).all(axis=1) & np.isfinite(y)
                if valid.sum() >= 252:
                    fitted = _fit_ridge(x[valid], y[valid])
                    fit_month = month
            if fitted is not None:
                mean, scale, beta = fitted
                prediction = np.r_[1., (features[i] - mean) / scale] @ beta
                targets[i] = prediction > 0
    else:
        for i, date in enumerate(prices.index):
            if i < 252:
                continue
            month = (date.year, date.month)
            if fitted is None or month != fit_month:
                sample = returns[i - 251:i + 1]
                if np.isfinite(sample).all():
                    fitted = _fit_mixture(sample)
                    fit_month = month
            if fitted is not None:
                weights, means, variances = fitted
                # Stable argmin breaks equal-variance ties by component index.
                safe = int(np.argmin(variances))
                posterior = _posterior([returns[i]], weights, means, variances)[0, safe]
                targets[i] = means[safe] > 0 and posterior > .5
    result = prices[['open', 'low', 'close']].copy()
    result['want_long'] = pd.Series(targets, index=prices.index).shift(1, fill_value=False)
    return result
