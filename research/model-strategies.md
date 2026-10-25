---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Fixed statistical model adaptations

This document owns the local rules for catalogue IDs 98 and 99 implemented in
`model_signals.py`. These are precisely specified research adaptations of two
broad families, not implementations of every supervised-learning or regime
strategy. Hyperparameters below were fixed before observing their backtests.
There is no model selection, parameter sweep, random initialization, external
training dataset, or claim of profitable unseen-data performance.

```text
Completed daily OHLC history
           ↓
As-of-close feature / realized-label boundary
           ↓
Fixed monthly training → current-close decision
                                      ↓ one-session shift
                           Next-open long/cash target
```

Both functions use the same validated OHLC/index and next-open contract as
[daily signal adaptations](daily-strategies.md). `build_model_signal(raw, id)`
returns `open`, `low`, `close`, `want_long`; the boolean target is already shifted
once. Build on full warm-up history, then slice the evaluation period. Both
models can remain in cash during early evaluation because the 2004 warm-up
contains insufficient complete observations. Costs, dividends, sizing and
financing belong to the caller's [portfolio model](leverage-model.md).

## ID98: rolling ridge next-session return forecast

At completed close i, the five features are raw close returns over 1, 5, 20 sessions,
the population standard deviation of the last 20 one-session close returns, and
close/SMA50−1. The target for feature row j is the next session's intraday return,
close(j+1)/open(j+1)−1. This target is known only after that session closes.
Training at close i includes feature rows **strictly before i**, so every label
is realized by close i. Current feature i is used for prediction, never training.

Use the last 504 candidate feature rows, discard incomplete feature/label rows,
and require at least 252 valid examples. Train on the first eligible close and
then on the first available close of each calendar month. Between refits use the
last fitted parameters. Features are centered and scaled using only that fit's
training data; scales <= 1e−12 become 1. Ridge regression has an unpenalized
intercept, penalty 10 on each standardized coefficient, and normal-equation
solution `(X'X + penalty)^−1 X'y` through a linear solver. There is no online
hyperparameter change or prediction threshold selection.

Hold a long target when the predicted next-session intraday return is strictly
positive; otherwise target cash. There is no expected-cost threshold in this
fixed baseline. Simulation nevertheless charges actual modeled trading costs.
The label forecasts one session's open-to-close return; the daily position-target
ledger can retain positions overnight when successive predictions remain
positive. Consequently ledger profit is not simply the sum of predicted-label
profits; overnight exposure is intentional and must be evaluated separately.
The first possible trained decision is feature index 301 (zero-based), with the
first possible next-open target at 302, because features require 50 closes and
training requires 252 complete feature/label pairs.

## ID99: two-component Gaussian-mixture regime allocation

This is a distribution-based classification adaptation, **not** a hidden Markov
model and not a forecast of regime transitions. It assumes the inferred current
regime may persist into the next trading session; that is an unproven research
hypothesis.

Use one-session raw close returns. On the first close with 252 finite returns,
and then the first close of each calendar month, fit a two-component univariate
Gaussian mixture on the trailing 252 returns, including the just-completed
session. Initialize means at sample 25th/75th percentiles, both variances at the
sample population variance with floor 1e−8, and weights at 0.5. Run exactly 40 EM
iterations. Each iteration computes responsibilities in log space, floors
component mass at 1e−12, floors weights at 0.01 then normalizes them, and floors
component variances at 1e−8. No random start or best-fit selection occurs.

On every completed close, classify its return using the last fitted mixture.
Identify the lower-variance component (component 0 breaks equal-variance ties).
Target long only if that component's fitted mean is positive **and** its posterior
probability for the current return exceeds 0.5. Otherwise target cash. Equal
posterior probability stays cash. The first possible next-open target is 253.
There is no fractional allocation, short position, transition matrix, posterior
smoothing, stop rule, or leverage decision inside this signal.

## Evidence and limitations

Tests cover deterministic repeated runs, flat data and finite mixture
probabilities, minimum-training cash behavior, monthly fit cadence, exact first
ridge training-label timestamps, next-open shift, synthetic regime switches,
and invariance when future rows, returns or labels are changed or truncated.
Those are implementation checks, not independent economic validation. Rolling
historical refits avoid future-label leakage but do not establish an untouched
holdout: this full history has already been viewed in other project research.
Raw-price return features omit dividends and are separate from portfolio total
returns. Gaussian distributions, fixed thresholds and basic ridge regression
can be poor descriptions of market behavior. Any comparison must retain the
underlying data, assumptions and observed failures alongside scores.
