# Strategy catalogue and SPY research suite

Status: active exploratory research protocol v1. Updated 2026-10-25.
This document owns suite selection, evaluation policy and completion meaning.
The machine-readable [catalogue](strategy_catalogue.json) owns the 100 entry records;
[daily strategy definitions](daily-strategies.md) own implemented signal formulas;
[leverage model](leverage-model.md) owns financing, sizing, fills and margin rules.

```text
100 candidate definitions → data/instrument/definition checks
  ├─ supported daily signals → independent prior-close decisions
  │    → 1x / 1.25x / 1.5x / 2x simulations in parallel
  │    → independent ledger audit → annual/full-period scores → browser/MLflow
  └─ unsupported prerequisites → visible blockers; no performance numbers
```

## Scope and evidence levels

The 100-name list is a research inventory, not 100 profitable systems or 100
Nautilus strategies. Indicators, allocation overlays, option payoff structures,
market-making and multi-asset systems have different implementation/data needs.
Every entry gets a definition, required inputs, provenance level and next acceptance.
An unavailable dataset or unspecified construction blocks a defensible backtest.
Do not substitute SPY prices for option chains, securities fundamentals or order books.

Runnable batch: IDs 1–8, 10–15, 19, 21, 31–34, 98 and 99 (22 daily SPY adaptations).
ID19 uses a precommitted close-entry/next-open-exit schedule described in
[overnight definitions](overnight-strategy.md); it cannot be combined with sizing
overlays in this contract. Its daily data is available; real auction fills are
not verified. Other signals use next-open rebalancing as described below.
The four allocation overlays are owned by [allocation definitions](allocation-strategies.md);
the two statistical models by [model definitions](model-strategies.md).
Explicitly adapted rules, such as long-only Turtle-style breakout without pyramiding,
are labeled as local variants, not exact replications of an original trading system.
No external package or strategy code is installed/copied by this batch.

Direction rules use completed OHLCV bars and shift to the next session open.
The precommitted overnight schedule enters at each close and exits at the next open. Use frozen source history starting in 2004 for available warm-up and evaluate
2005-01-03 through 2025-12-31. Strategies needing more history stay cash until their
indicators are ready. Every rule uses the same dates, USD 300,000, daily whole-share
sizing and financing contract. A rule plus leverage is an implementation variant,
not an independent strategy discovery. Four nominal exposure targets/caps create 88 runs. Volatility/drawdown/CPPI
overlays can reduce actual targets below the nominal cap; they are not constant
leverage implementations. CPPI uses prior-close portfolio equity; its floor is not
guaranteed through gaps. Optional per-session allocation factors are validated in
[the ledger](leveraged_spy.py) and independently recomputed in the Decimal audit.

## Evaluation policy

This is an **in-sample exploratory screen** on an already viewed dataset. Defaults
are recorded before running this batch and are not tuned to observed scores.
The tested family/parameter choices are not statistically independent. All runs,
including losses and failures, stay recorded. Ranking 88 variants introduces
selection bias; the highest Sharpe/Calmar is not evidence of superiority or a
credible future annual-doubling estimate. No untouched holdout is claimed.

Do not use the ranking to select live deployment. A later research protocol must
freeze a shortlist, state an economic hypothesis, predeclare chronological evaluation
and stress/cost tests, account for all trials, and obtain data not used to choose it.
Original SPY and leverage experiments remain separate immutable evidence.

## Artifact contract and completion

`reports/strategy-suite/<input-code-config-hash>/` contains catalogue and assumption
snapshots, signal inputs, per-case daily account/trade/annual ledgers, scores and a
manifest. Results are ignored by Git. Root-level source definitions and compact
validation receipts are versioned. Completed artifacts hash-verify before reuse;
failed/incomplete folders are retained and not overwritten. Three worker processes
run separate cases; each case is reconciled independently using Decimal arithmetic.

`simulated` means the declared data/model produced audited portfolio calculations;
it does not mean native Nautilus execution parity, paper verification, alpha proof,
implementation of an entire published methodology or live readiness. A completed
catalogue review is distinct from completing all 100 implementations. Dataset rights,
quotes, account permissions and broker simulation remain separately scoped.

Suite extension must preserve exact strategy IDs, record model/code/data identity,
show unsupported entries as blocked/definition-required, and avoid ranking mixed
capital/execution policies. All-suite status stays partial until every requested
entry's acceptance is satisfied; unresolved prerequisites are displayed explicitly.
