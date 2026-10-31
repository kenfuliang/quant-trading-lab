---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# RSI robustness epoch: completion review

Outcome: **retain the frozen EMA/volatility-only candidate for independent
validation**. All three predeclared comparisons against EMA passed. This is a
stronger historical stress result, not a newly improved algorithm or proof of
future profitability. [Frozen protocol](2026-10-25-rsi-gate-robustness.md) owns
rules, selection criterion, assumptions and bounds; it was not amended after freeze.

```mermaid
flowchart LR
    A[Previous candidate unchanged] --> B[Nine reserved execution paths]
    B --> C[All account and metric audits pass]
    C --> D[Joint comparison passes in three contexts]
    D --> E[Retain for independent validation]
    E --> F[Stop: budget exhausted]
```

## What was tested

Three fixed rules at5bp,25bp, and25bp plus an extra session of dynamic-signal
delay. Each actual path consumed one slot, including three baseline reproductions
and the duplicate standing buy-and-hold control in the last context. No retries,
fitting, tuning, other assets, external downloads, services, MLflow writes, agents
or broker operations. This is the existing custom research ledger with independent
Decimal replay; no NautilusTrader or MLflow source was modified.

| Context / rule | CAGR | Max close DD | Sharpe | Calmar | Longest recovery intervals |
| --- | ---: | ---: | ---: | ---: | ---: |
| 5bp / gate | 8.734% | -17.770% | 0.769 | 0.492 | 513 |
| 5bp / EMA | 8.013% | -29.062% | 0.643 | 0.276 | 531 |
| 5bp / entry-only holding | 9.161% | -51.680% | 0.608 | 0.177 | 1243 |
| 25bp / gate | 8.435% | -18.584% | 0.745 | 0.454 | 531 |
| 25bp / EMA | 7.753% | -29.201% | 0.625 | 0.266 | 684 |
| 25bp / entry-only holding | 9.150% | -51.676% | 0.607 | 0.177 | 1243 |
| 25bp + delay / gate | 8.489% | -19.208% | 0.745 | 0.442 | 517 |
| 25bp + delay / EMA | 7.769% | -31.199% | 0.626 | 0.249 | 558 |
| 25bp / standing holding control repeated | 9.150% | -51.676% | 0.607 | 0.177 | 1243 |

Longest observed intervals include recovery/censor semantics, separate from the
deepest episode; these nine longest episodes recovered within observation.
The gate's worst21-session return was approximately-16.32% in each context;
EMA ranged from-28.66% to-29.20%. Higher cost/delay need not worsen every realized
metric monotonically: they can change share rounding, traded quantities and which
historical prices a signal encounters. Neither delay nor higher costs is a return
enhancement recommendation.

## Weaknesses preserved

Entry-only holding had greater full-period CAGR in all contexts. The gate beat EMA
over the whole path, yet lost to it on cumulative return in the already-viewed
2012–2018 block in all three contexts. Its reduced exposure is a plausible major
source of loss reduction; this study does not isolate timing alpha at matched risk.
The report includes every annual return/DD/Sharpe/Calmar row and block, exposure,
cost and temporal paths. Results are not uniformly better year by year.

The inherited raw block helper labels cumulative-period return/absolute DD as
`calmar`; that quantity is **not annualized Calmar**. Preserve those raw bytes,
exclude that column from block rankings, and explain its semantics in the browser.
Overall and calendar-year Calmar were independently verified and are unaffected.
This identified reporting issue should be addressed in a separate future change,
without rewriting the frozen runner or old results.

## Evidence and reproduction

New branch: `codex/rsi-gate-robustness`, based on main
`4999ec5767eccdd6f61863b14a05e459855f95e3`. Work remains local and uncommitted;
the separate diagram PR is unchanged. Executable source/test/dependency identities
and dirty-file status were recorded before execution in
`research/plans/spy-gate-robustness-v1.json`, SHA256
`1ddd9c98521e5498c93cb68dcb0066e22bf5ff84c146e856a73e2cdcff4c7329`.
Inputs retain the prior frozen source identity and viewed-history disclosure.

Runtime outputs: `.local/gate-robustness/1ddd9c98521e5498/`.
Nine attempts completed with zero failures in13.995seconds, one worker and900second
ceiling. The exclusive output identity prevents re-execution. Failed/timeout
engineering fixtures verify one consumed attempt, retained evidence and no further
launch; these synthetic fixtures are not financial performance trials.

Read-only browser package:
[execution robustness](http://127.0.0.1:8765/gate-robustness/20261025-v1/index.html).
The package is saved under `.local/performance/gate-robustness/20261025-v1/`;
this task does not start the server. Exact audit/hash counts are in the
[machine receipt](evidence/2026-10-25-rsi-gate-robustness.json).

Validation: `make check` exit0,227 offline tests; documentation/dependencies pass.
The six new synthetic checks cover causal delay, standing-control semantics,
joint-criterion rejection, invalid bounds, failed-attempt preservation/replay
rejection and timeouts. Fresh read-only verification checked105 run artifacts and
six browser-package artifacts,47,547 Decimal session reconciliations,792 independent
financial metric comparisons and278,397 temporal scalar/window checks. Fifteen
baseline metric/duration comparisons matched prior evidence. Static HTML was
generated and hash-verified; interactive browser visual inspection and hosted CI
were not performed. The diagram PR was not merged or changed.

From the repository root, `python -m research.gate_robustness` in the project venv
performs offline preflight only. Do not rerun `--freeze` or `--execute`: both reject
existing identity. The report builder reads saved artifacts and refuses an existing
output directory; select a fresh report path for an explicitly requested rebuild.
No fresh financial path is needed to inspect the saved result.

## Next decision

Freeze this candidate and full selection history for genuinely unviewed,
qualified chronological evidence. First resolve data/calendar and dividend-payment
assumptions and native parity prerequisites; the separate ETF readiness audit
remains not ready. A future protocol must explicitly qualify data availability
and use a new bounded budget. More searches over these same years cannot establish
independent validation. No automatic next epoch, paper promotion or deployment.

The goal is complete because it produced a reproducible bounded decision, including
negative opportunity costs and unresolved validity limits. It did not establish
the annual-doubling aspiration or a trained-RL/self-modifying production system.
