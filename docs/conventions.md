---
status: active
updated: 2026-11-18
owner: project-maintainers
---

# Research conventions

This file owns the shared conventions every run, analysis and receipt uses. Each
section states the convention and links to the owner of the rule behind it.

## Instrument identity

An instrument has a stable id with a dated symbol history, so a ticker change does not
split or merge its data. Status: planned. Owner: Plan 5 (`instrument-identity/v1`, see
the [artifact catalog](artifacts.md)).

## Strategy identity

A strategy run is identified by `config_hash` (a hash of the configuration only) plus
`code_commit`. Data identity and run time are not part of the hash. Owner:
[run output contract](../research/evaluation/run_output.py) (`run-output/v1`).

## Units

Returns, costs, weights and drawdowns are stored as fractions, never percent.
Percentage points appear only in display. Fractions in data: owner
[run output contract](../research/evaluation/run_output.py). Annualisation uses 252
sessions per year: owner [research development](research-development.md).

## Metrics

- CAGR.
- Max drawdown, defined as `(current equity / prior peak equity) - 1` including the
  initial-capital baseline ([goals](goals.md)).
- Sharpe at a zero risk-free rate (convention from
  [research development](research-development.md)); always labelled as such.
- Calmar (CAGR over absolute max drawdown); defined here.
- Turnover per year (traded value over average equity, divided by years of 252
  sessions); defined here.
- Longest underwater (sessions from a peak until equity regains it); defined here.

The benchmark is SPY total return, dividends reinvested ([goals](goals.md)).
Metric scoring and ranking stay with [research scoring](research-scoring.md).

## Cost levels

Reports show results at 5, 10 and 25 bp; these report levels are defined here. The
$1 commission default (`commission_usd`) and the per-side cost applied to a fill
(`execution_price`) are owned by the
[market model](../research/evaluation/market_model.py).

Analysis strategies keep the current holding when the decision inputs (gate state and
proposal) are unchanged since the previous session and the target is within 2% of the
current shares, so constant-weight positions do not trade for one-share drift; the rule
is owned by [strategies](../research/evaluation/strategies.py).

## Windows

- Development years: all history before the sealed forward window.
- Sealed forward window: read only once through the
  [trial ledger](../research/control/trial_ledger.py); rules in the
  [research standard](research-standard.md).
- Crisis windows, always reported separately: 2018-Q4, 2020-02-19 to 2020-04-30, and
  2022. Defined here.

## Trial unit

One frozen configuration is one trial. Ablation rungs and parity runs are not trials.
Counting and recording follow the [research standard](research-standard.md).

## Schema versions

An additive change is a minor change and keeps the same id. A breaking change is a new
major version with a new id. Readers keep every old major so saved evidence stays
readable. The list of ids is the [artifact catalog](artifacts.md).

## Use

A run's `use` is `engineering` (the default: screening, parity, development) or
`financial` (`use: financial` in the spec or `--use financial`). Financial use needs a
passing quality report, or a `pass-with-exceptions` report with an owner-written
[acceptance](../research/evaluation/acceptance.py) covering every exception; engineering
manifests carry no `use` key. The acceptance (`quality-acceptance/v1`, see the
[artifact catalog](artifacts.md)) is bound to one report by SHA-256. Rules and limits:
[workflow](workflow.md#enforced-research-rules).

## Combinations

A combination (`scripts/portfolio.py combine`) weights several run outputs into one
`run-output/v1` with `engine: "combiner"`. It is a sleeve-level model: each component
contributes its own `net_return` (already net of its trading costs), positions are sleeves
and `quantity` is 0. Weights are `equal` or `inverse_vol` (causal, trailing volatility),
long-only and summing to at most `gross` (at most 1.0, so no leverage); cash earns zero;
rebalancing is a turnover cost (default 5 bp) on returns. Components must have identical
date sets. Stock members make the combination survivor-biased and discovery-only; `use` is
`financial` only if every component is. Trial rule: each combination is a trial, so a real
one needs `--cycle-id` (one ledger trial) and its own frozen plan and forward window;
`--exploratory` records none and is for demonstrations. Goals:
[research baseline and selection](goals.md); plan:
[Plan 7](tasks/2026-11-18-offline-infra-plan7-portfolio-plan.md); first demonstration:
[portfolio record](tasks/2026-11-18-portfolio.md).

## Stances

Each stance is disclosed, not hidden:

- Long-only, cash account ([goals](goals.md)).
- Pre-tax: results are judged before personal tax; tax is an omitted item
  ([goals](goals.md)).
- Cash earns zero. Interest on idle cash is not modelled, and every parity receipt
  records `cash_interest: "not modelled"`
  ([engine parity record](tasks/2026-11-17-engine-parity.md)).
