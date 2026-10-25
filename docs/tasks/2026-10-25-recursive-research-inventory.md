---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Recursive research: starting inventory

This is a dated, read-only capability and result snapshot supporting the user's
requested ten-hour research program. It does not redefine portfolio priority,
investment policy, or acceptance gates. Current capabilities remain owned by
[README](../../README.md), objectives by [goals](../goals.md), sequence by
[roadmap](../roadmap.md), and research handoffs by
[research development](../research-development.md). Exact current file identities,
checks and computed descriptive statistics are in the
[inventory receipt](evidence/2026-10-25-recursive-research-inventory.json).

```text
What exists                         Small missing research-control layer
───────────                         ───────────────────────────────────
Frozen SPY input ──→ audited ledger ──→ bounded plan / attempt registry
22 causal adaptations ──→ 88 cases ──→ diagnosis / multi-perspective scores
Saved equity + trades + costs ───────→ branch allocation / stop conditions
19 skill instructions ──────────────→ recorded decision / next bounded cycle
                                            ↓
                               independent future evidence still required
```

## Confirmed goal and scope

The [mandate](../goals.md) records USD300,000 scenario capital, a one-year planning
horizon, annual doubling aspiration, permission to research leverage, free/local
data only, and approximately30% drawdown as a stop-and-reassess tolerance. These
are user preferences rather than established achievable performance or approved
operational loss/exposure limits. Benchmark, liquidity needs, hard risk budgets,
instrument selection, numerical leverage limits and precedence between return and
downside remain open. Offline research can proceed while those investment-policy
choices remain unresolved, with explicitly labeled research assumptions.

The newly requested recursive-development objective is to make better research
decisions from evidence, including useful rejections and switching direction when
marginal progress stops. It is distinct from investment returns and from model
weight training. The current system has neither a trained research policy/value
model nor a live optimization agent.

## What we actually have

| Asset | Observed status | Limit / prerequisite |
| --- | --- | --- |
| Local runtime | Python3.12 environment; NautilusTrader1.231.0 pinned; dependency check passed | Native configuration/catalog behavior proof is still roadmap M1 |
| Preserved input | SPY raw Yahoo snapshot and normalized5535 rows, 2004-01-02–2025-12-31; 2004 warmup and5283 evaluation sessions, 2005-01-03–2025-12-31 | Retail data; no independent exchange/provider reconciliation or fully verified research redistribution rights |
| Initial fixture | Saved EMA/buy-and-hold evidence and independently reconciled economic outputs | Earlier USD100k entry-only assumptions differ from USD300k daily-sizing suite |
| Finance model | Offline long/cash portfolio ledger; fees/spread, dividends, calendar-day financing and intraday margin checkpoints; separate Decimal audit | Not native broker execution; fixed6% debit interest and simplified fills, no tax/settlement/market-impact model |
| Catalogue | Exactly100 ideas with source context, default rule and blockers | Catalogue entry is not implemented/replicated strategy performance |
| Supported batch | 22 causal SPY adaptations ×1x/1.25x/1.5x/2x =88 financial cases | 78 entries need absent/unverified data or instrument models; cases are correlated, not independent discoveries |
| Saved evidence | Completed study `97fc0717512bee9e`; all465 saved artifact hashes and15 current financial input hashes match its manifest | All history already viewed; audit establishes model accounting, not alpha |
| Metrics/browser | Annual/full-period returns, daily-close drawdown, Sharpe, Calmar, costs, daily paths, local HTML and MLflow importers | No general compatibility-aware arbitrary-strategy importer or multi-asset portfolio simulator |
| Prior independent receipt | 1936 score rows,464904 sessions and246485 fills checked; max ledger difference about1.09e-8USD | Historical receipt retained; this inventory rechecks hashes, not every trade replay |
| Skills | 19 entrypoints:5 advisers,5 previous workflows,9 bounded research workflows | Instructions, not an automatic scheduler/search/controller; paired9-task baseline54/54 versus equipped54/54 showed no incremental quality gain |
| Offline checks | Fresh `make check` passed:64 tests,52 documentation files and dependency integrity | Covers exercised behavior, not complete catalog/persistence/broker readiness |
| Broker observation | Observer/doctor/probe implementation and offline fixtures | Last observed paper-account access blocker unresolved; no successful project broker connection, paper orders or live execution recorded |
| Native persistence/recovery/health | Assessed interfaces and documented plans | Behavior/configuration remains unverified or planned under M1–M5 |

Ignored `data/` contains1145 LEAN example/support files. Their presence does not
establish licensed, complete, timestamp-valid multi-asset research inputs; do not
quietly treat those directories as an approved universe. New symbols also do not
automatically establish an untouched holdout. Only the saved SPY input has the
current experiment's documented economic treatment.

## What the existing results tell us

All figures below are descriptive development-sample outcomes under the saved
suite's assumptions. Overall `return_pct` means CAGR; it is not annual return or
total return. Daily-close drawdown can miss intraday equity losses even though
the ledger separately checks specified intraday margin points.

| Saved case | CAGR | Daily-close max drawdown | Calmar | Sharpe | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| ID2 EMA,1x | 8.01% | −29.06% | .276 | .643 | Simple reference for sizing/timing comparisons |
| ID32 EMA plus volatility target,1x nominal cap | 6.47% | −15.10% | .429 | .734 | Best suite Calmar; lower return and shallower losses, not universal improvement |
| ID31 volatility target,2x nominal cap | 11.03% | −45.61% | .242 | .620 | Highest suite CAGR, but substantially worse than stated drawdown tolerance |
| ID11 RSI2,1x | 3.83% | −21.52% | .178 | .434 | Lower standalone scores, potentially different timing worth diagnosing |
| ID19 overnight,1x | −17.52% | −98.25% | −.178 | −1.666 | Strong negative result under modeled frequent trading costs |

No saved annual return row reaches100%. Twelve of88 full-period CAGRs are
nonpositive. Twenty-one of88 cases have historical drawdown no worse than−30%;
that descriptive count must not be presented as an approved gate or predicted
future loss bound. Existing results do not support annual doubling or establish
a persistent edge. Search rankings were selected using already-inspected history.

ID32 targets10% annualized volatility with a1x nominal exposure cap in the case
above; its percentage volatility objective is not a10% portfolio-weight cap.
Margin interest and daily sizing also mean nominal exposure labels are not
constant realized leverage.

Exact aligned daily equity-return correlation is .918 for ID2/ID32 at1x, and .422
for ID2/ID11 at1x, over5283 intervals including each path's opening capital anchor.
The date vectors were checked identical before computing returns. This is
descriptive dependence; a lower correlation by itself is not a profitable or
stress-resilient allocation. Exposure can explain much of apparent diversification.

The [Survival Funnel review](2026-10-25-research-strategy-survival-funnel.md) adds a
static inventory of47 upstream families,318 settings and9222 reported cases,
with67 source-filter survivors. Its results were checked for CSV consistency,
not reproduced from prices. Reusable concepts are rejection transparency,
parameter stability, causal rule definitions and dependence-aware diagnostics.
License ambiguity blocks direct code adoption at the pinned revision; source
test selection, execution timing, costs and stitched drawdowns limit transfer of
reported performance. It does not supply verified multi-asset market data.

## What needs building before credible recursive research

These are prerequisites/candidate work packets for the coordinating plan, not a
replacement roadmap or claims that new tools already exist.

1. **Frozen research contract.** Per branch: hypothesis/control, eligible data,
   primary estimand, diagnostic metrics, resource/trial budget, risks, stop and
   reopening conditions. Keep research scores separate from investment eligibility.
2. **Attempt and access registry.** Link parent/child hypotheses, all successes,
   failures/rejections, data/code/config hashes, viewed periods and reasons. A
   versioned JSON/JSONL file is sufficient initially; a database is not necessary.
3. **Bounded plan executor.** Existing suite runner hardcodes source,22 IDs and
   four exposures. Add a narrow explicit plan interface or separate analytical
   harness for allowed saved-result operations; do not replace the audited ledger.
   Plan changes, new assumptions and retries must count and preserve failures.
4. **Separated scorecards.** Evidence eligibility first; measured strategy tradeoffs
   second; research-action information value/cost third. Unknowns stay unknown;
   attractive scores cannot override invalid data. Record scales before results.
5. **Diagnosis and uncertainty tools.** Exact-interval alignment, cost/exposure
   attribution, regime counts, drawdown/recovery, parameter neighborhoods,
   dependence-aware intervals and explicit multiple-search limitations. Add tools
   to answer an actual question, not a generic dashboard wishlist.
6. **Branch allocator and regression tests.** Deterministic simple priority rules,
   exploration allowance, budgets, stagnation/rejection/blocker states and reopening
   triggers before considering learned RL/GAE policies. A policy must not rewrite
   its evaluation or erase losing branches.
7. **Independent evidence path.** Existing historical SPY data is development data.
   A historical resplit after seeing results cannot recover independence. Declare
   exploratory resampling as such; specify future observation or separately
   justified independent data before financial promotion.
8. **Broader inputs/instrument contracts when justified.** Audit free-source rights,
   total-return/corporate-action semantics and point-in-time availability before
   ETF/stock selection. Futures, FX and options require contract/roll/currency/
   margin/expiry/assignment models. Do not infer those from daily SPY schemas.

Existing broker/catalog/recovery roadmap requirements remain applicable before
operation. Offline scoring experiments do not need broker access and cannot satisfy
those operational prerequisites.

## Smallest feasible two-cycle demonstration

**Cycle1: diagnose a sizing tradeoff without searching indicators.** Freeze
ID2 versus ID32,1x nominal cap, all saved periods and current costs. Attribute
net growth, drawdown/recovery, exposure and turnover; determine whether measured
downside reduction trades away gains consistently or depends on a few episodes.
Record both improvements and regressions. Outcome can be a supported tradeoff or
inconclusive claim, not forced dominance. A later change must have a bounded
falsifier; parameter tuning is unnecessary for this first evidence cycle.

**Cycle2: investigate a different mechanism—portfolio complementarity.** Freeze
ID2 versus ID11 at1x and evaluate exact-interval return dependence, common loss
episodes and fixed50/50 sleeve accounting against each component. Compare using
the same capital conventions and keep any passive sleeve combination distinct
from a daily rebalanced combined account. A portfolio with revised weights,
rebalancing or margin is a new financial experiment requiring explicit mechanics.
Do not choose weights by maximizing the already-viewed sample. This branch can
teach us whether alternative timing merits research without acquiring new data.

ID19 is a useful cost/turnover rejection fixture, not a promising default branch
for repeated threshold searches. Its high costs may motivate a distinct, bounded
question, but do not tune away the assumed costs just to improve its score.

Both cycles are feasible on saved inputs, explore different layers and can end in
useful rejection. Neither demonstrates multi-asset alpha, unseen improvement, an
autonomously learned research policy, or readiness to trade.

## Verification and preservation

Git base: `a5a73ec9a6fd65395d40fdace7994172d1dc42f8`; checkout contains substantial
earlier dirty work. The exact financial input hashes match the saved study; the
base SHA alone does not identify that working tree. Fresh checks found no duplicate
dates, ordering failures, missing normalized cells, negative volumes or invalid
OHLC rows in the saved normalized SPY input. Those checks do not certify external
source correctness or rights. No strategy simulation, MLflow import, service
startup, broker operation, network access, commit or publication occurred in this
inventory task. Preserved artifacts and prior results were not rewritten.
