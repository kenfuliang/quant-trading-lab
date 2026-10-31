---
status: active
updated: 2026-10-31
owner: research-maintainers
---

# T11 loss-to-decision trace from saved exports

Classification: partial descriptive attribution, not a new financial experiment.
User requested the sequence locate losses → trace decisions → change one component
→ compare benefits, missed gains and costs. This task executes the first two steps
using saved evidence and identifies the exact boundary before the latter two.
The [specialist review](2026-10-31-t11-specialist-review.md) supplies prior questions;
[GRS](../research-standard.md) still owns any later bounded rule-change study.

```mermaid
flowchart LR
  L[Saved account losses: located] --> O[Closed trades and order IDs: traced]
  O --> G[Branch, gate and daily mark attribution: incomplete]
  G --> H[One component hypothesis: proposed only]
  H --> T[Future separately bounded comparison: not run]
```

## Scope and methods

Read-only original ungated/gated official reference exports and compatible closing
paths,2020–2025,1508sessions,USD10000anchor. One descriptive pass: ten largest
loss sessions per path plus three previously identified diagnostic dates
(2025-01-27,2025-04-09,2020-03-24). All history is viewed; event selection is
retrospective. No download, financial run, signal rerun, parameter search, broker
operation, new service or original-source modification.

The [trace script](../../scripts/trace_t11_saved_losses.py) verifies official-export
hashes against the existing reference audit, path ordering/coverage and existence
of every closed-trade order ID. It writes loss events, recent fill records,
reported trade intervals and per-symbol reported closed-trade aggregates to
`.local/t11-loss-trace-v1/trace.json` and two CSVs. All source exports remain intact.

Trade intervals crossing a session close are only a subset of potentially relevant
positions: trades entering/exiting exactly at the close, unclosed terminal holdings,
actions and engine recording conventions require separate handling. An empty
interval list does **not** prove cash. `profitLoss` and `totalFees` are preserved
as separate literal engine fields; this review does not assume fee inclusion or
subtract fees a second time. Account PnL uses consecutive saved NAVs including
initial capital; it is distinct from a whole trade's realized PnL.

## Located episodes and recovered exposure evidence

| Session | Gated account return / PnL | Ungated account return | Recoverable trace | Remaining unknown |
| --- | --- | --- | --- | --- |
| 2025-01-27 | −14.7825% / −USD76112.45 | −14.7829% | Both exports report SOXL/TECL/TQQQ trades entered2025-01-15and not exited until late February/early March | Daily asset marks, exact gate/branch inputs, split of the day's loss by asset |
| 2025-04-09 | +14.6725% / +USD69543.07 | +28.6097% | Both report TQQQ entered2025-04-07and exited2025-04-10; recent fills and trade order IDs are recovered | Relative exposure at each decision/open and why the gate/intent differed |
| 2020-03-24 | 0.0000% / USD0 | +9.6614% | Recent fills retained; no continuously crossing closed-trade interval in this specific filter | Exact account holdings/actions and policy/gate state; cannot infer cash solely from this filter |

For January15entries in gated T11, reported complete-trade PnL later closed at
−USD40137.97SOXL,−USD22456.55TECL and−USD6369.94TQQQ. These amounts are **not**
January27asset losses: they cover the complete reported holding intervals.
They nevertheless locate a specific concentrated long-basket episode, rather
than an abstract market classifier problem. The gate did not materially change
the observed January27percentage account loss versus ungated T11.

April's TQQQ reported quantity is10259gated versus43782ungated. Different account
wealth means quantities alone cannot establish relative risk or the gate colour.
The gated trade's whole-interval reported profit isUSD59787.01, distinct from the
USD69543.07one-session account gain. No daily PnL decomposition is fabricated.

## What the closed-trade detail adds

Gated export:525closed trades. Selected cumulative **reported closed-trade** PnL:

| Instrument | Closed trades | Reported profitLoss, USD |
| --- | ---: | ---: |
| TQQQ | 104 | +237039.62 |
| SOXL | 71 | +136823.71 |
| TECL | 72 | +123999.22 |
| SQQQ | 87 | +28086.59 |
| TECS | 49 | −28115.17 |
| SOXS | 30 | −46688.46 |

Across the three leveraged-long products above plus SPXL/QLD, reported closed
PnL totals+USD502876.02; the defined inverse-equity group totals−USD48226.94.
Volatility-product UVXY totals+USD30329.64. These are account-size/path-dependent
realized trade aggregates, not standalone strategy returns or causal marginal
contributions. They omit a full account reconciliation and cannot rank investments.

This refines the previous idea that the gate may suppress helpful defensive
positions: some inverse instruments show positive reported totals, others negative.
There is no evidence for treating every inverse trade as useful or every negative
aggregate as removable. TQQQ/TECL/SOXL also have overlapping economic exposure;
three symbols do not imply independent risk.

**Do not delete TECS/SOXS on this table alone.** Negative closed-trade totals can
coexist with useful crisis behavior, displaced opportunities and different later
account sizes. Selection after inspecting PnL is hindsight. The correct marginal
question requires a fixed same-date/cost/account comparison after tracing branch
and gate state; it was not run here.

## Reconciliation boundary and candidate direction

Reported closed PnL sumsUSD484510.02gated, while ending NAV less initial capital is
USD491845.82: unexplained differenceUSD7335.80. Ungated difference isUSD15099.04.
Open trades, fees, actions, dividends and recording conventions are possible
components, not assigned explanations. Do not force equality or call this a new
proved accounting defect. Complete ledger reconciliation remains missing.

Supported next analysis direction: **branch-conditioned risk/sizing**, preserving
T11's proposal, rather than another wholesale universe/strategy replacement.
Two mechanisms must be distinguished before choosing one: concentrated bullish
basket losses and adverse inverse-basket selections. The first is supported by
January's position intervals; the second by aggregate reported closed trades.
Neither identifies the proper threshold or proves a better rule.

The immediate missing join is original feature availability, branch ID, proposed
weights, gate/cap, realized holdings/action ledger and fill/account timestamps.
The existing official result export provides order/trade links but not that join.
A future rule change needs one frozen mechanism and finite new allowance; no
prior financial budget is reopened. Benefits, missed gains, costs and recovery
must then be compared together. **No component changed in this task.**

## Completion and evidence

- [x] Locate ten worst account sessions per reference plus fixed diagnostic dates.
- [x] Recover reported trade intervals and recent fills with valid linked order IDs.
- [x] Aggregate525/557reported closed trades without altering original exports.
- [x] Separate daily account PnL, whole-trade PnL, fees and unresolved residuals.
- [x] Save trace/CSV/source hashes and a no-new-score leaderboard closure link.
- [ ] Original per-session branch/gate/feature and complete holdings/account replay.
- [ ] Causal branch/asset daily loss allocation and marginal rule-change experiment.

[Evidence receipt](evidence/2026-10-31-t11-loss-decision-trace.json) binds inputs,
script, output, limits and checks. Original failures, exports and strategy sources
are preserved. Diagnostic records do not establish alpha, an upper bound,
operational readiness or a new performance score.
