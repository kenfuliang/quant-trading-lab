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
Percentage points appear only in display. Annualisation uses 252 sessions per year.
Owner: [run output contract](../research/evaluation/run_output.py).

## Metrics

- CAGR.
- Max drawdown, defined as `(current equity / prior peak equity) - 1` including the
  initial-capital baseline ([goals](goals.md)).
- Sharpe at a zero risk-free rate; always labelled as such.
- Calmar (CAGR over absolute max drawdown).
- Turnover.
- Longest underwater (sessions from a peak until equity regains it).

The benchmark is SPY total return, dividends reinvested ([goals](goals.md)).
Metric scoring and ranking stay with [research scoring](research-scoring.md).

## Cost levels

Reports show results at 5, 10 and 25 bp per side, with a $1 commission default. Owner:
[offline research infrastructure design](tasks/2026-11-17-offline-research-infra-design.md).

## Windows

- Development years: all history before the sealed forward window.
- Sealed forward window: read only once through the
  [trial ledger](../research/control/trial_ledger.py); rules in the
  [research standard](research-standard.md).
- Crisis windows, always reported separately: 2018-Q4, 2020-02-19 to 2020-04-30, and
  2022.

## Trial unit

One frozen configuration is one trial. Ablation rungs and parity runs are not trials.
Counting and recording follow the [research standard](research-standard.md).

## Schema versions

An additive change is a minor change and keeps the same id. A breaking change is a new
major version with a new id. Readers keep every old major so saved evidence stays
readable. The list of ids is the [artifact catalog](artifacts.md).

## Stances

Each stance is disclosed, not hidden:

- Long-only, cash account ([goals](goals.md)).
- Pre-tax: results are judged before personal tax; tax is an omitted item
  ([goals](goals.md)).
- Cash earns zero. Interest on idle cash is not modelled, and every parity receipt
  records `cash_interest: "not modelled"`
  ([parity design](tasks/2026-11-17-offline-research-infra-design.md)).
