---
status: active
updated: 2026-10-28
owner: research-maintainers
---

# Saved SPY continuous-sizing transition diagnosis

**Completed, descriptive development diagnosis; incumbent unchanged.** The continuous 20% annualized-volatility cap lost relative to the discrete EMA/volatility gate mainly through different market exposure, especially overnight, rather than transaction costs alone. This explains the fixed saved comparison; it does not prove that removing one class of trades would improve a future portfolio. [GRS](../research-standard.md), [diagnosis SOP](../research-development.md#performance-diagnosis) and [scoring](../research-scoring.md) retain policy ownership. The closed epoch (`../../.local/rsi-calmar-20261028/docs/tasks/2026-10-28-calmar-rsi-epoch.md`; private/local artifact, not published) owns original results and expired budgets.

```mermaid
flowchart LR
 M[Saved manifest + exact hashes] --> T[Freeze posthoc taxonomy]
 T --> Q[Align accounts / signals / trades]
 Q --> D[Exact wealth and return identities]
 D --> L[Protection / missed gains / overlap labels]
 L --> H[Evidence-backed next hypothesis; no new portfolios]
```

## Comparison and result

Both matched contexts contain 5,283 sessions from 2005-01-03 through 2025-12-31, starting USD 300,000, with the same saved SPY inputs, open-trade timing, dividends, fixed 6% debit model,99% allocation and $1 commission. Only execution-cost assumption differs between 5 and 10 bp; compare within each context. Source/parent/code/plan and every manifest artifact passed 116 hash/identity checks before attribution. Six original cases remain present; only the four continuous/discrete paths are decomposed here. The half-EMA controls are preserved, not silently substituted.

At 5 bp, continuous ends$1,586,620.06 versus discrete$1,739,775.65, a$153,155.59deficit and-8.803%lower ending wealth. At 10 bp, the deficit is$154,458.95, or-9.008%. These are ending-wealth ratios, not CAGR gaps. The closed study's lower Calmar, lower CAGR, deeper loss and longer underwater period remain negative evidence; this diagnosis changes no promotion decision.

| Observed component, continuous minus discrete | 5 bp wealth-gap contribution | 10 bp wealth-gap contribution |
| --- | ---: | ---: |
| Overnight | $-133,676.90 | $-133,998.16 |
| Intraday | $-11,927.52 | $-11,853.88 |
| Dividends | $-6,564.60 | $-6,776.60 |
| Commission | $-125.00 | $-121.00 |
| Slippage | $-861.57 | $-1,709.31 |
| Financing | $0.00 | $0.00 |
| **Exact ending wealth gap** | **$-153,155.59** | **$-154,458.95** |

Dollar contributions are exact **observed account differences** and include prior compounding/position-scale differences. They are not isolated effects of changing one decision. Continuous pays$986.57more modeled commission/slippage at 5 bp and$1,830.31more at 10 bp. Financing is zero for both paths in both contexts. Additional fills are 125 and 121 respectively; marked turnover rises from$21,574,968to$23,311,567at 5 bp. Therefore cost differences alone do not account for the deficit. No cost-free counterfactual was simulated.

## What the transitions show

Saved intended targets differ on 448 sessions: continuous is lower on 220 and higher on 228; 4,835 have equal targets. These counts are cost-independent and are not counts of independent opportunities. Same-target days can still have different realized fractional exposures through whole-share rounding, cost effects and prior wealth. Continuous has 236 target cuts and 196 adds across the saved path; a cut is not automatically successful protection.

At 5 bp, sessions with a lower continuous target contribute −3.192 log-percentage points to relative ending wealth; higher-target sessions contribute −5.782 and equal-target sessions−0.241. At 10 bp those contributions are −3.451, −5.995 and +0.006. These are exhaustive date partitions, **not causal attribution of current target**: overnight positions originate before the current opening decision. The three weakest calendar partitions at 5 bp are2020: -5.546 log-percentage points; 2010: -2.463 log-percentage points; 2008: -0.959 log-percentage points. Annual contributions are relative log-wealth changes, not standalone annual Calmar or reset drawdown.

The three worst relative sessions are 2020-03-12, 2020-03-16 and 2020-03-11 at both costs. Continuous intent remains approximately 39.4%, 29.1% and 41.0%respectively while discrete intent is 0%; all three continuous decisions are cuts from the prior target. Thus the evidence supports **remaining too exposed relative to this incumbent during those losses**, not merely late re-entry after a rebound. It does not establish a universal optimal crash threshold or an unobserved market forecast.

Leg-level posthoc labels expose both sides. At 5 bp, lower overnight exposure produces 835 protective negative-return legs (+4.235log-percentage points) but 1,071 missed positive legs (-7.053); 497 of the missed legs follow a negative prior observed close-to-close return (-3.574). Lower intraday exposure yields 872 protective legs (+7.796) and 1,033 missed gains (-7.645); 457 are rebound-subset legs (-4.396). Rebound labels are subsets, not extra losses to add. Higher overnight exposure's gains/losses net to-6.126log-percentage points. Both protection and displaced gains matter.

Counts include tiny realized differences due to rounding/wealth and use the frozen 1e−10 weight tolerance; they are not all material policy changes. At 10 bp some leg counts differ for that reason, despite identical intended targets. Full per-cost counts and values remain in the receipt/private CSV. One-session rebound means a positive current leg after a negative prior close-to-close observation; it is not a learned regime, confirmed recovery or independent event. The initial prior-return context is unavailable for the first two labels and is not fabricated.

## Exact identities and checks

For saved open-only fills, with previous/current shares q⁻/q, previous close C⁻, open O, close C and saved dividends/costs:

`ΔE = q⁻ × (O − C⁻) + q × (C − O) + dividends − commissions − slippage − financing`.

The initial position is zero, so its overnight contribution is zero without inventing a prior evaluated close. The script fails closed on rejected/forced paths, non-opening trade marks, invalid shares, misaligned calendars, nonfinite values, inconsistent signal marks or a material residual. It reads saved fills; it generates no desired shares or new orders.

Divide each component by that path's preceding equity to reconcile every daily return difference. To reconcile compounding exactly, apply each session's common link factor `k = [log(1+r_c) − log(1+r_d)] / (r_c − r_d)` to its component return differences, using the continuous limit at equality. Sum over components/sessions to obtain `log(E_c,end / E_d,end)`. This is a mathematical observed-path allocation, not a counterfactual trading return. Raw sums of daily contributions are not relabeled compounded portfolio returns.

Maximum daily-account residual is below 4e−10 USD; ending-wealth decomposition residual is at most 1.1e−9 USD; relative-log-wealth residual is below 1.2e−15. All decision availability dates precede execution dates, saved decision tables match and signal marks align. Explicit dividend effects differ in dollar and normalized/log attribution because the two prior equity denominators differ; neither is silently substituted for the other.

## Missing evidence, lessons and next hypothesis

**Warnings while already in cash cannot be established.** Saved decisions retain EMA eligibility and effective target, but omit underlying green/yellow/red colour/cap when EMA eligibility is zero. The 1,019 shared EMA-ineligible cash sessions are verified cash states, not verified redundant warnings. Recovering colour would require another saved trace or separately scoped deterministic state reconstruction; none was performed here. No future outcome labels entered the historical policy.

A justified single-stage hypothesis for a later prospective test is to retain the discrete incumbent's no-go ceiling while changing only sizing beneath that ceiling: continuous sizing would never exceed discrete intended exposure. The displaced higher-exposure gains, missed rebounds, extra turnover and possible lower growth are explicit harms; the report does not calculate that portfolio or claim it wins. Freeze its exact mechanism, unchanged accounting and simpler controls under a new budget only after closing the evidence gaps. Do not retune the 20% volatility target from these observations.

## Verification and preserved failure

Six focused synthetic saved-account tests passed: arithmetic, residual rejection, unsupported fill timing, calendar mismatch, log linking and disjoint exposure buckets. These are tests of analysis, not financial simulations. The first analysis invocation failed before reading financial paths because qualification references were relative to the primary evidence root but the invocation used the isolated checkout. The failed log is preserved; re-invoking from the evidence root passed without changing source, inputs or financial rules. This is a technical analysis retry, not a new financial attempt. The failed and successful invocations have the same script identity; only their working directory differs.

[Aggregate receipt](evidence/2026-10-28-spy-transition-diagnosis.json) links the frozen taxonomy, source checks, script/tests and private per-session/annual outputs. Private folder: `.local/spy-transition-diagnosis-20261028/`. No existing evidence was overwritten; no shared checklist, leaderboard or canonical policy was edited. Zero financial runs, network requests, packages/services, broker operations or agents. Missing original per-attempt UTC timestamps remain a limitation of the frozen epoch, not corrected by this diagnosis. A timestamped execution-journal repair remains prerequisite to another financial cycle.
