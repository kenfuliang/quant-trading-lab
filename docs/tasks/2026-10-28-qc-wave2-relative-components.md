---
status: active
updated: 2026-10-28
owner: research-intake
---

# Wave two: reversal, relative value and liquidity components

Four representatives screened across three families, following [research intake](../research-intake.md), [GRS](../research-standard.md) and the [parallel review](2026-10-28-qc-parallel-review.md). This extends representative coverage, not complete family/code/runtime qualification. The [evidence receipt](evidence/2026-10-28-qc-wave2-relative-components.json) owns input hashes, exact IDs, proposed contracts and usage. No financial result was generated.

```mermaid
flowchart LR
 U[Historical eligible universe + availability times] --> F[Qualified returns / spreads / turnover features]
 F --> T[Optional target ranking / pair formation]
 T --> P[Reversal or relative-value proposal]
 P --> R[Risk: gross/net, concentration, borrow]
 R --> E[Separate multi-leg execution + costs]
 E --> A[Audit outcomes and failure evidence]
```

| Representative / family | Verified public method | Pipeline contribution and key correction | Readiness |
| --- | --- | --- | --- |
| **QC-T-15311 Short-Term Reversal Strategy in Stocks** / mean reversion | Weekly long recent losers and short winners, ranked on 22-session returns within 100 liquid names. | Target ranking plus signed position proposal; a reversal rule is not evidence of market crash prediction. | Method screened; complete source/runtime and historical universe, borrow and costs unqualified. |
| **QC-T-15300 Pairs Trading with Stocks** / relative value | Select four pairs by one-year normalized-price distance; reform half-yearly and trade divergence/reversion. | Pair selection plus proposal. Low historical distance does not establish statistically calibrated cointegration. | Licensed mechanism alternative exists, but differs materially and its tested adaptation is negative. |
| **QC-T-15352 Liquidity Effect in Stocks** / liquidity/microstructure | Annual low-versus-high turnover portfolio within a small-cap subset. | Turnover alpha feature, target selection and long-short proposal; **not execution improvement** or measured order-book liquidity. | PIT fundamentals/shares/universe, turnover units, short availability and impact unqualified. |
| **QC-T-15298 Pairs Trading: Copula vs Cointegration** / relative value | Dependence models generate conditional mispricing signals; formation parameters refresh monthly. | Statistical-model selection is not switching trading strategies by regime. | Exact comparable pair/source identity and licensed runtime unresolved. |

Primary sources checked: [15311 reversal](https://www.quantconnect.com/research/15311/short-term-reversal-strategy-in-stocks/), [15300 stock pairs](https://www.quantconnect.com/research/15300/pairs-trading-with-stocks/), [15352 liquidity](https://www.quantconnect.com/research/15352/liquidity-effect-in-stocks/), [15298 copula](https://www.quantconnect.com/research/15298/pairs-trading-copula-vs-cointegration/). Current page revisions are unknown; prior pinned tutorial fragments are identified in the receipt at Tutorials commit 4a341890296f7e79e095508f06170c72ccaa629c. Public descriptions verify mechanisms only, not complete runtime/source identity or performance. No source copied from restricted interfaces.

## Proposed causal contracts

All contracts are proposals for future development, not installed shared adapters. Every input needs its own publication/availability time, permanent instrument ID, normalization/action policy, missing status and formation/fit cutoff. A decision may use only already available inputs; the earliest permitted fill must follow that decision. A date label alone does not establish ordering.

- **Reversal:** emit eligible-universe identity, trailing-return scores/ranks, long/short intent, readiness and exclusion reasons, with weekly decision and next review times. Current 500 survivors cannot stand in for the historical US universe. Separate forecast horizon, rebalancing and actual holding duration; forced universe removal is a distinct exit reason.
- **Pairs:** emit pair IDs, formation window, pair-quality statistic, spread/residual units, fit cutoff, hedge method, entry/exit state and signed leg intent. Invalid or unstable fits produce an explicit unavailable decision, not a conveniently flat financial result. Gross, net and beta neutrality differ; matching dollar legs is not proof of hedging.
- **Liquidity factor:** emit turnover numerator/denominator units, shares publication timestamp, universe exclusions and quantile rank. The article's mean-volume versus annual-turnover terminology requires audit. Split consistency and lagged shares matter. Its `HasFundamentalData` claim must not substitute for checking actual ADR/fund/security-type exclusions. Buying less liquid names is not evidence we can execute cheaply.
- **Copula:** emit conditional dependence scores with model family/revision and training cutoff before a separate policy maps scores to positions. Protect empirical-CDF boundaries, admissible dependence parameters and extreme/negative hedge ratios. The article names QQQ/XLK after copula selection but GLD/DGL as the same pair in the comparison section. Treat common-universe/model-superiority claims as unverified until identities and dates reconcile.

Historical borrow availability, recalls and short dividends remain named prerequisites for every short portfolio. Sparse daily price histories cannot qualify synchronized fills, spreads, partial-leg risk or market impact. Shorting a liquid current security is not proof of historical availability. Annual liquidity rebalancing does not eliminate capacity risk. Free hosted data access and local download entitlement are separate questions; this review qualifies neither anew.

## Rights, equivalence and preserved negative evidence

The existing package review found no qualified complete licensed implementations for 15311, 15352 or 15298. Pinned method fragments are not full algorithm packages; grant applicability and dependencies still require candidate-specific review. Similar reversal/pairs titles and overlapping family tags are not code-equivalence evidence. The four records retain not-code-compared duplicate status.

The unchanged local stock-pairs alternative matches SHA256 `d3088cbee0bc494513075d8f79ec4a9e940e17f432b9e2a86977f639a1e9d471`, from [je-suis-tm/quant-trading at611b73f2c3f577ac5b28aaa19ac8c43d3236c7a5](https://github.com/je-suis-tm/quant-trading/blob/611b73f2c3f577ac5b28aaa19ac8c43d3236c7a5/Pair%20trading%20backtest.py). Its prior Apache-2.0 grant does not confer data rights. Static imports include NumPy, pandas, matplotlib, statsmodels and yfinance; versions are not fully locked. The original is never executed/imported here.

That fixed NVDA/AMD cointegration example differs from the distance-selected tutorial. The existing [causal adaptation](2026-10-26-stock-pairs-spy-comparison.md) repaired future-aware sizing, calibration, state and information timing; it returned −2.18% CAGR, Calmar −0.09 and 2,341 underwater sessions in its scoped modeled context. Both frozen improvement screens failed. Its strong hindsight pair-hold control is not a prospective target selector. Preserve that negative result, failed early-close probe and closed budget; this new screen does not justify retuning it or reject every pairs mechanism.

## Next bounded questions and controls

The best foundation question is whether **one historical decision can be reconstructed** from a known eligible universe and causal action-consistent inputs, with every availability time present. A zero-financial audit should stop with explicit missing-field evidence before computing tradable returns. This avoids treating today's catalog as a historically investable stock library.

Then isolate one mechanism in a separately authorized/frozen test. Reversal needs same-universe/no-ranking and separate-leg controls; pairs need a fixed pair and a signal-independent exposure control; liquidity needs market-cap-matched holdings and identical costs; copula needs exactly the same pair/dates/costs versus a linear-spread baseline. Same-pair hold is opportunity-cost context, not a beta/exposure match. Model fit or ranking statistics cannot alone improve portfolio Calmar. Retain growth, depth and time underwater alongside it under the canonical scoring contract.

## Validation and scope

Four primary IDs each occur once in the 622-record inventory; all three requested families have explicit machine coverage status. Two web calls checked methods and relevant displayed snippets; no bulk extraction or source export occurred. Licensed fixture hash, local links, JSON shape and scoped whitespace check passed. Shared catalog/checklist and previous evidence were untouched. Zero financial runs, data downloads, package installs, services, brokers or subagents. This document-only screen does not require a financial or full test-suite launch.
