---
status: active
updated: 2026-10-25
owner: research-maintainers
---

# Feature engineering contract

Skills-only integration note: executable research implementations and saved results
are delivered in the dependent [research PR](https://github.com/kenfuliang/quant-trading-lab/pull/1).
Implementation descriptions and linked historical evidence below refer to that
reviewed snapshot; they do not establish runtime availability on this branch.


This file owns feature definitions, availability and diagnostic interpretation.
[Research lifecycle](research-development.md) owns the RSI loop;
[scoring](research-scoring.md) owns selection meanings; [intake](research-intake.md)
owns external claims. RSI means recursive self-improvement here.

```mermaid
flowchart LR
    H[Economic hypothesis or bounded LLM proposal] --> R[Versioned feature registry]
    R --> C[Pure causal transform and validation]
    C --> F[Freeze candidate and diagnostic budget]
    F --> J[Join matured outcomes separately]
    J --> D[Coverage, redundancy and temporal diagnosis]
    D --> V[Retain, redundant, blocked or inconclusive]
    V --> N[Separately scoped policy ablation or new question]
```

## Feature records and implementation

A registry entry carries ID/version, family, mechanism, exact formula and code
identity, raw fields, units, window/minimum history, availability boundary/lag,
missing/zero handling, provenance and existing-feature reference. Source/code/
registry hashes bind every actual test. Keep raw fields, engineered inputs,
execution observations and future labels distinct.

The first local registry and pure builder are in
[`research/feature_engineering.py`](https://github.com/kenfuliang/quant-trading-lab/blob/4586095846c63abf2e0b90dc547654256c3fc45e/research/feature_engineering.py).
[`scripts/feature_diagnostic.py`](https://github.com/kenfuliang/quant-trading-lab/blob/4586095846c63abf2e0b90dc547654256c3fc45e/scripts/feature_diagnostic.py) is an offline
saved-SPY diagnostic, not a generic model trainer or portfolio simulator. It
reads the existing source and gate outcome manifest, checks exact joins, freezes
calibration-only bin edges and reports later development blocks. No arbitrary
expression evaluation, packages, market downloads or API keys are needed.

Compute features from completed bars and shift once to the next saved session's
execution boundary. Validate prefix invariance and future perturbation: later
observations cannot alter earlier inputs. Same-day open/range/volume are not known
at that day's open. Fitted scaling, imputation, bins, PCA or selection must use
only their declared earlier calibration/training data. No full-sample ranks,
backfill or centered windows. Missing warmup and undefined ratios retain reasons;
invalid source values stop instead of becoming confident zeros.

Underlying raw-price corporate-action and source-calendar/availability limitations
remain attached. Correct timing arithmetic does not certify provider publication
latency, data rights, independent alpha or broker-realistic fills.

## Evaluation contract

Freeze candidates, proposal rounds, definitions, baselines, targets, horizons,
periods and stop bounds before generating new diagnostics. Count feature variants
and target/horizon comparisons even when no financial backtest runs. Do not promote
a feature by its strongest retrospectively selected horizon or era.

- Quality: coverage, finite values, constants, units, chronological availability
  and independent numeric checks. Eligibility precedes ranking.
- Redundancy: compare with existing inputs and other candidates using declared
  periods; a correlated feature is not automatically useless, and low correlation
  is not proof of incremental prediction.
- Target relations: returns, risk and gate-label regions answer different
  questions. A volatility predictor is not necessarily a return predictor.
  Single-SPY time-series rank correlation is not cross-sectional factor IC.
- Temporal stability: report fixed blocks, calibration-only cuts and counts.
  Already viewed development blocks are not holdouts. Purge labels whose maturity
  crosses a declared block boundary. No fitted classifier or calibrated success
  probability is inferred from tercile frequencies.
- Dependence: report overlapping windows and a fixed stride view if relevant;
  nonoverlapping outcomes still share autocorrelated inputs/market conditions.
  Do not manufacture p-values or independent sample counts.
- Gate labels: condition on policy eligibility/actionability explicitly, and show
  small episode counts. Gate outcomes retain later policy decisions and their
  own capital paths; they cannot isolate the effect of one feature or action.

Retain-for-next-test means a concrete question remains feasible. Financial benefit
requires a new controlled policy test with costs and the entire trial history.
Negative, redundant and inconclusive findings are valid workflow outcomes.

## Established feature families and source reuse

Screened2026-10-25; conceptual references, not locally reproduced strategies.

| Family | Familiar examples | Local feasibility / missing input |
| --- | --- | --- |
| Trend/momentum | Lagged returns, MA/EMA distances, slopes, MACD | Saved SPY daily closes; raw-price/dividend semantics disclosed |
| Reversal/oscillators | Short return reversal, RSI, stochastic position | OHLC available; every lookback/threshold is a counted hypothesis |
| Risk | Realized volatility, downside variation, short/long volatility ratio | Saved prices; forecasts need independent evaluation |
| Range/price position | High-low range, ATR, rolling extrema, candlestick geometry | Daily OHLC; not intraday order or execution evidence |
| Volume/liquidity | Relative volume, dollar volume, price-volume correlation | Saved daily volume; not a substitute for spread/order-book data |
| Cross-sectional styles | Value, size, profitability, investment, momentum | Point-in-time multi-stock fundamentals/constituents absent |
| Cross-asset/macro | Breadth, yield spreads, credit and cross-asset relationships | Additional qualified inputs and publication calendars absent |
| Microstructure/options/text | Imbalance, spread, implied volatility/skew, news sentiment | Quotes/options/events/text histories and availability absent |
| Portfolio/policy state | Exposure, time in cash, confirmation counters | Existing decision logs; distinguish availability from realized outcome |

Qlib's [Alpha158 implementation](https://github.com/microsoft/qlib/blob/54355232463878d2eebb91fe0ee5fa7fa1f5976c/qlib/contrib/data/loader.py)
provides concrete examples of range geometry, moving averages, return/risk,
correlation and volume transforms; Alpha360 uses lagged price/volume histories.
Its [benchmark documentation](https://github.com/microsoft/qlib/blob/54355232463878d2eebb91fe0ee5fa7fa1f5976c/examples/benchmarks/README.md)
distinguishes those feature sets and signal/portfolio metrics. These are design
references, not158independent alphas or free-data SPY performance. We do not copy,
install or run Qlib in this task.

Kakushadze's [101Formulaic Alphas,2016v3](https://arxiv.org/abs/1601.00991v3)
illustrates compositional price/volume operators. Cross-sectional ranks and
neutralization require a real universe; replacing them with single-SPY time ranks
changes the hypothesis. The paper's portfolio results are not reproduced here.

## LLM-assisted engineering

[RD-Agent(Q),2025v2](https://arxiv.org/html/2505.15155v2) separates research,
implementation, validation and feedback, with factor/model co-optimization.
[AlphaAgent,2025v2](https://arxiv.org/abs/2502.16789v2) proposes formula-similarity,
hypothesis alignment and complexity regularization. Reuse those process ideas,
not their headline returns or an unbounded search loop. Their data, markets,
models, costs and repeated-search settings differ from this local SPY diagnostic.
RD-Agent repository inspected at484776c211e4fbbeef03e0ec00d6bbee7362a4f4;
Qlib at54355232463878d2eebb91fe0ee5fa7fa1f5976c. No upstream code/data license or
performance adoption is asserted. Paper access is not a dataset license.

A useful bounded prompt specifies: available fields and timing; existing features;
economic question; maximum proposals/operators/lookbacks; required formula, units,
lag and falsifier; no protected outcomes. The LLM proposes and critiques; pure code
computes, tests and records. Preserve rejected duplicates and proposal context.
Historical market knowledge in pretrained LLMs and prior conversation may already
contain evaluation outcomes, so label the resulting ideas development-informed.
Do not claim an untouched test merely because raw future rows were withheld.

Current task uses this assistant for one bounded three-feature proposal round;
there is no external LLM/API call, new agent, automated mutation, trained RL or
LLM-versus-human performance comparison. LLM-authored code is reviewed and tested
before it touches real saved evidence.
