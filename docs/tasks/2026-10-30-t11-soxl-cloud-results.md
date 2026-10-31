---
status: active
updated: 2026-10-30
owner: research-maintainers
---

# T11 signals on SOXL or cash: eight cloud cases

Classification: **provisional negative-results development report**. All eight financial
cases completed; evidence capture/audit remains incomplete. No new alpha, strategy
promotion, local historical parity or paper readiness is established.

## Question and frozen scope

Does concentrating T11’s SOXL-eligible bullish branch into SOXL, and otherwise
holding cash, improve performance versus full gated T11 and SOXL buy-and-hold?
The user explicitly approved these eight private test sources to their own
[QuantConnect project38676621](https://www.quantconnect.com/project/38676621).
Original project38484741 source was not modified. Private third-party source stays
ignored; no redistribution rights are inferred.

```text
Original T11 signals → SOXL eligible? → SOXL / cash → unchanged traffic-light cap
                      other branches → cash
```

[Design and preflight](2026-10-30-t11-soxl-cash.md) precedes these results. The
new frozen cloud plan and source hashes are in `.local/t11-soxl-cloud-v1/`.
One worker; two-hour launch deadline; eight cases maximum, zero retries. All
eight cases were reserved before submission; the allowance is exhausted. This
is separate from the pending36-case three-session programme.

## Data, accounting and evaluation conventions

2020-01-02–2025-12-31,1508 sessions, USD10000. Native adjusted subscriptions,
original2004 RAW SPY gate seed, T11 indicator/branch policy, IB margin/default fees
and staged signal-change MOO controller are retained. The controller applies the
90% target once; green/yellow/red yield90/45/0 percent target for the candidate.
No daily target maintenance after intent completion. SOXL buy-and-hold uses the
same initial90% target and continuous eligible intent. Other T11 branches, including
oversold TQQQ/SPXL, inverse and defensive allocations, become cash in SOXL-only.

25/50bp adverse fill contexts also use matched affordability reservations. Costs
can change quantities and later orders, so this is not pure fee subtraction on a
fixed trade list. Six percent fixed debit ACT/360 remains on prior cash, zero credit
interest and disabled native per-security margin interest. SOXL’s actual leveraged
ETF history is used; no three-times index reconstruction or added fictitious fund
borrowing charge. Corporate actions, cash and fills remain native-engine results,
not independently reconciled local accounting. The hosted provider snapshot is not
immutably pinned. All history has been viewed; no untouched holdout is claimed.

All eight runs used observed LEAN18217. Fresh gated T11 controls at both costs
avoid ranking a new engine result solely against older18215 references. The25bp
control reproduces the saved aggregate custom summary; this is not daily parity.

## Native overview results

Calmar below is **derived from rounded native Overview CAGR/DD**. Native Sharpe
is also retained. These conventions differ from custom daily-close metrics; do not
merge the two rankings. DD is a positive magnitude.

| Case | Cost bp | Derived native Calmar | Native CAGR | Native max DD | Native Sharpe |
| --- | ---: | ---: | ---: | ---: | ---: |
| gated_t11_25bp | 25 | 2.492 | 91.961% | 36.900% | 1.709 |
| soxl_cash_ungated_25bp | 25 | 1.137 | 60.054% | 52.800% | 1.098 |
| soxl_cash_gated_25bp | 25 | 1.271 | 62.172% | 48.900% | 1.155 |
| soxl_buy_hold_25bp | 25 | 0.155 | 13.498% | 86.900% | 0.584 |
| gated_t11_50bp | 50 | 1.713 | 68.515% | 40.000% | 1.329 |
| soxl_cash_ungated_50bp | 50 | 0.913 | 50.473% | 55.300% | 0.961 |
| soxl_cash_gated_50bp | 50 | 1.057 | 53.149% | 50.300% | 1.019 |
| soxl_buy_hold_50bp | 50 | 0.155 | 13.457% | 86.900% | 0.584 |

Full gated T11 has higher Calmar, CAGR and smaller drawdown than either
SOXL/cash variant at both costs. The gate improves SOXL-only Calmar and drawdown
relative to the ungated SOXL-only policy at both costs, but DD remains48.9–50.3%,
above the approximately30% reassessment reference. SOXL buy-and-hold suffers86.9%
native drawdown in this window. There is no candidate promotion.

## Annual and temporal diagnosis

Forty-three of48 annual custom-summary rows were captured. The25bp buy-and-hold
case lacks2021–2025 annual summaries; these are unavailable, not zero. At25bp,
2022 return is approximately−47.27% for SOXL/cash,−28.99% gated SOXL/cash, versus
+60.62% for full gated T11. The mapping removes defensive/inverse branches, but
precise causal P&L attribution needs daily decision/order logs; the annual contrast
alone does not establish which individual branch earned that gap.

Visible custom legacy longest-underwater counts at25bp are531 sessions ungated
SOXL/cash and365 gated, versus199 full gated T11. These exclude the recovery close;
do not mix them with temporal-v1.2. Truncated calendar counts and the25bp buy-and-hold
temporal fields remain unavailable. No complete recovery-inclusive temporal audit
or equity curve comparison was reconstructed.

## Capture failures and validation

The embedded result frame rejected pointer/focus actions and Download Results
events timed out. Reloading and alternate supported browser views did not recover
an official export. These failures are preserved; no retry backtests were launched.
The rendered terminal also truncates individual lines. The observation reader
accepts numeric fields only with a complete delimiter, rejects wrong run identities,
and keeps missing fields null. One control’s native Overview was transcribed from
the observed UI, with saved rendered fragments bound separately. Hashes establish
saved artifact identity, not full input/accounting truth.

[Structured incomplete receipt](evidence/2026-10-30-t11-soxl-cloud-results.json)
binds all8 run IDs, source hashes, visible build observations and capture limitations.
[Analysis UI](http://127.0.0.1:8765/t11-soxl-cloud-v1/index.html) provides cost filters,
comparison CSV and partial annual CSV. Original failed upload receipt remains
unchanged; subsequent explicit approval and successful case launches are separately
recorded. No financial slots remain; read-only export recovery does not renew them.

## Lessons and next eligible question

Concentrating a multi-asset policy into one leveraged long ETF loses more than
diversification: it removes alternative branches and changes execution turnover.
The existing gate helps within this narrower policy, but does not restore full
T11 performance or meet the30% loss reference. Higher costs materially reduce
all active cases. Before another strategy change, recover the official results
and reconcile daily equity, decisions and accounts. A future separately bounded
question could retain T11 defensive branches while changing only its bullish basket;
that was not tested here and is not authorized as another run by this receipt.

Validation: `make check` passed (586 offline tests, dependency and documentation
checks); the subsequently added report passed the separate documentation check.
The receipt validator passed structural/hash checks. Analysis UI rendered, its
25bp cost filter was checked, and the final screenshot was inspected. These checks
do not complete the missing official-export/daily financial audits.
