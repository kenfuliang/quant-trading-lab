---
status: active
updated: 2026-10-26
owner: project-maintainers
---

# First-three selection research: comparison, decisions and lessons

Work status: **scoped development review completed; no strategy selected for investment**.
This is the result owner for the [bounded goal](2026-10-26-selection-research-goal.md).
The [executable protocol](../../research/plans/selection-completion-v1.json) owns
case/source hashes and technical amendments. The [earlier source intake and study](2026-10-26-qc-selection-comparison.md)
own legacy-code inspection and the explicitly declared adaptations. These are
project-owned economic-rule adaptations, not reproductions of the published code
or its advertised performance. All 2020–2025 results are viewed development data,
not independent out-of-sample evidence.

```text
Diagnose history → freeze three candidates and matched controls
   → base comparison + paired cost/delay stress → accounting/temporal audit
   → retain / stop / inconclusive → lessons and next evidence requirement
```

## Experimental context

Nine new financial cases share 2020–2025, USD 10,000 whole-share accounts, native IB
fees and 25 bp slippage, 90% nominal targets, staged MOO execution, 6% debit ACT/360
and zero credit interest. Selection cases reset allocation intent monthly; SPY
is an entry-only 90% target whose cash fraction drifts. Two stock-momentum stress
cases instead use 50 bp and one extra observed-session decision delay, including
matching cash reservation. Stock stress was chosen after viewing its earlier
result; this is disclosed selection history. T11 is a verified cached reference,
with embedded leveraged ETFs and its original daily signals. Equal capital does
not equalize realized exposure, concentration or risk.

The global bound is 14 hosted launches, including diagnostics/failures/retries,
within the existing two-hour window. No parameter search, paid data, broker
operations, publication, deployment or new services are authorized by this review.

## Readiness and technical findings

The order-free probes verified that the 253-bar-count history request returned
only 210 ETF closes on the July 3, 2023 early close; the stock universe also became
zero-ready. A 600 calendar-day request restored the full 253 completed closes.
Strict ordering, uniqueness, finite positive prices, current-slice timestamp
matching and no-future-bar guards remain enforced. Legitimate short post-listing
windows stay excluded: ABNB 54 closes on March 1, 2021 and SNOW 243 on September 1, 2021.
A final order-free coverage retry independently confirmed the monthly-momentum exclusion as SNOW with 243 closes on September 1, 2021. The earlier stock probe had covered only the low-volatility cohort; its valid results and coverage gap remain archived. The new financial runs record their own eligibility counts and hashes. This
establishes a scoped workaround for observed hosted behavior; it does not identify
or patch an upstream LEAN defect.

Two failures are preserved: one diagnostic log was truncated and failed its
checksum; the first broad-stock control stopped with `Target price unavailable`.
The latter received a subscription-lifetime correction for unheld current and
pending delayed targets. `_selected`, history and ranking remain unchanged;
static comparisons identify only the subscription return/helper changes. The
completed stock-momentum source remains unchanged. Matched feature/membership
hashes are required before accepting the repaired control comparison. A completed
native backtest after a runtime error is not a valid full-period financial result.

## Results and decisions

[Open the comparison browser](http://127.0.0.1:8765/selection-completion-v1/index.html).
[Aggregate metrics and provenance](evidence/2026-10-26-selection-completion.json)
include all source hashes, native run IDs, attempts, checks and limitations.
[Annual CSV](http://127.0.0.1:8765/selection-completion-v1/annual.csv) contains all 60 case-years;
[artifact hashes](http://127.0.0.1:8765/selection-completion-v1/manifest.json) identify the outputs.

Base and stress rows are separate cost/timing contexts. T11 is cached, not a tenth
fresh financial run. UW means below the continuous prior equity peak; calendar
duration excludes recovery day. All cases end below a prior peak, so recovery is
right-censored. These ranks are descriptive, not significance tests.

| Case | CAGR | Max DD depth | Sharpe | Calmar | Longest UW sessions | UW calendar days |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ETF momentum | 6.25% | 26.12% | 0.510 | 0.239 | 606 | 882 |
| Stock momentum | 29.62% | 29.66% | 1.049 | 0.999 | 585 | 847 |
| Low-volatility stocks | 2.31% | 29.86% | 0.233 | 0.077 | 593 | 862 |
| SPY holding | 13.62% | 29.79% | 0.785 | 0.457 | 488 | 708 |
| Equal-weight ETFs (5) | 6.00% | 26.45% | 0.525 | 0.227 | 494 | 720 |
| Equal-weight stock universe | 6.47% | 18.86% | 0.664 | 0.343 | 552 | 805 |
| Equal-weight low-vol universe | 5.96% | 18.87% | 0.615 | 0.316 | 573 | 835 |
| Stock momentum · 50 bp + delay | 26.25% | 30.43% | 0.957 | 0.863 | 603 | 875 |
| Equal-weight stocks · 50 bp + delay | 6.19% | 18.12% | 0.650 | 0.342 | 553 | 806 |
| T11 (cached) | 119.67% | 51.26% | 1.690 | 2.335 | 146 | 214 |

Annual-return snapshot; use the browser for annual DD, Sharpe, Calmar, annual
underwater duration and continuous-peak underwater fractions:

| Year | ETF momentum | Stock momentum | Low volatility | Modeled SPY |
| --- | ---: | ---: | ---: | ---: |
| 2020 | 3.08% | 92.16% | -6.51% | 16.05% |
| 2021 | 20.00% | -0.14% | 9.74% | 25.72% |
| 2022 | -7.33% | 2.49% | -1.81% | -16.66% |
| 2023 | 9.76% | 38.30% | -2.05% | 23.56% |
| 2024 | 2.86% | 53.81% | 7.63% | 22.87% |
| 2025 | 11.21% | 13.39% | 7.98% | 16.55% |

### ETF momentum — retain only for independent validation; low priority

**Hypothesis and variant.** Percentage momentum selects three of the five frozen
ETFs monthly, versus equal weight of all five. Case IDs `asset`/`ew_asset`; exact
source and matched membership/eligibility hashes are in the executable protocol
and evidence receipt. Accepted financial attempts 4 and 8; supporting diagnostic
attempts 1–2 include the preserved truncated-log failure. Legacy-code deviations
remain those in the original intake.

**Supported finding.** Net CAGR improves 6.00%→6.25%, and drawdown depth 26.45%→26.12%.
This narrowly passes the predeclared growth mechanism test. It beat its equal-weight
control in five of six calendar years.

**Contradictory evidence.** Sharpe declines 0.525→0.510; longest underwater increases
494→606 sessions. The 2024 return was 2.86% versus 7.28% for equal weight. Five annual
wins did not produce a large compounded advantage. It trails modeled SPY on CAGR,
Sharpe, Calmar and longest underwater duration, while offering smaller drawdown.

**Contribution evidence and lesson.** Native full-period P&L includes SPY +USD 2242.79,
EFA +USD 2219.59 and VNQ −USD 1258.19. These are accounting contributions, not isolated
sleeve returns or a causal explanation of a particular year. A slightly better
Calmar can coexist with worse Sharpe and much longer recovery.

**Next evidence requirement.** No more same-data horizon tuning. Before allocating
further research budget, test the small advantage independently and separate
ranking from three-versus-five-name concentration and turnover. ETF-specific cost
sensitivity was not tested in this epoch. Retain is not investment selection.

### Stock momentum — retain for independent validation; most promising growth direction

**Hypothesis and variant.** Five highest 252-session percentage-momentum stocks
from its historical monthly 50-name universe, versus eligible-universe equal weight.
Case IDs `stock`/`ew_stock`; stress IDs `stress`/`ew_stress`. Accepted financial
attempts 5, 10, 12 and 13; failed control attempt 9 is excluded. Subscription repair
changes the control/unrun stress subscription return only, not the completed
stock source. Membership and eligible-feature hashes match in both pairs.

**Supported finding.** Base CAGR 29.62% versus 6.47% for its broad control;
Sharpe 1.049 versus 0.664; Calmar 0.999 versus 0.343. It beat that control in five of
six calendar years and modeled SPY in four. Under the combined 50 bp-plus-delay
stress, CAGR 26.25% still exceeds the paired control's 6.19% by 20.06 percentage points.

**Contradictory evidence.** Base drawdown 29.66% exceeds the broad control's 18.86%,
and longest underwater 585 exceeds 552 sessions. Stress raises drawdown to 30.43% and
longest underwater to 603 sessions; ending wealth is 85.40% of base, despite CAGR
retention of 88.64%. Cost and delay were changed together, so neither effect is
isolated. This crosses the user's approximate reassessment level, not a newly
approved automatic risk limit. It has not qualified the desired risk behavior.

**Where gains/losses occurred.** Annual returns were 92.16%,−0.14%, 2.49%, 38.30%, 53.81%
and 13.39%; growth was not steady annual doubling. 2021 and 2025 trailed modeled SPY.
Native full-period P&L: NVDA+USD 9844.62, PLTR+USD 6855.94, ZM−USD 1496.05 and GEVW−USD 1048.80.
NVDA represents 20.54% of positive security P&L; NVDA and PLTR together 34.84%. This is
full-period accounting concentration, not year-by-security or factor attribution.

**Lesson and next evidence requirement.** This is the strongest development growth
candidate among these three, but the broad control's peak gross was 68.98% versus
93.23%, and native fees were USD 932 versus USD 434.90. The control does not isolate
momentum alpha from exposure, concentration, position count and minimum fees.
Next resolve the USD 300,000 capital/whole-share effect and use predeclared
concentration/exposure controls; then require independent validation. Dollar
turnover, average exposure, betas, issuer/sector concentration and diversification
with T11 were not measured. No broker promotion or 30% loss guarantee follows.

### Low-volatility stocks — stop this fixed variant

**Hypothesis and variant.** Select five stocks with lowest sample volatility of 252
daily returns, using its daily historical universe and monthly portfolio decisions,
versus equal weight of that eligible universe. Case IDs `lowvol`/`ew_low`; accepted
financial attempts 6 and 11, supported by the archived low-volatility cohort probe 3.
Source, membership and eligible-feature hashes identify the matched inputs.

**Supported finding.** The variant earned 2.31% CAGR versus 5.96% for its control,
with 29.86% versus 18.87% drawdown. It fails the predeclared smaller-drawdown test.
Sharpe 0.233 versus 0.615, Calmar 0.077 versus 0.316 and longest underwater 593 versus
573 sessions also favor the control. It beat the control only in 2021 and 2022;
2020 and 2023 were particularly weak relative years.

**Contribution evidence and lesson.** Native P&L includes JNJ+USD 1101.51, COST+USD 684.70,
FPL−USD 354.51 and MCD−USD 308.44. Selecting individually low-volatility stocks does
not define a low-risk portfolio: five-name concentration, correlations, universe
lifecycle, realized exposure and costs still matter. The broad control's peak
gross was 68.64% versus 89.44%; this prevents a pure volatility-factor conclusion,
but does not rescue the fixed small-account implementation.

**Next evidence requirement.** Stop tuning this variant on these years. A future
risk-budgeted or covariance-aware diversified portfolio is a different hypothesis
requiring its own frozen controls and evidence. This result does not disprove the
entire low-volatility literature.

## Lessons and research direction

1. **Qualify operational state before scores.** A valid history count can fail on
   early closes, and a valid signal can lose an unheld subscription during staging.
   Preserve failed and partial paths; native completion alone does not prove a
   valid full-period experiment.
2. **Match more than nominal dollars.** Same universe/costs/target budget do not
   match actual exposure or concentration. Whole-share granularity and fixed fees
   make the USD 10,000 fixture unsuitable for an unqualified USD 300,000 decision.
3. **Growth, loss depth and recovery disagree.** ETF momentum's small CAGR/Calmar
   advantage comes with 112 extra underwater sessions; stock momentum's growth comes
   with 585 sessions underwater and a stress drawdown beyond 30%. Annual-reset DD
   cannot replace continuous DD: stock momentum's worst annual-reset DD is 25.14%,
   while full continuous DD is 29.66%.
4. **Accept negative outcomes and keep the search bounded.** Stop this low-volatility
   variant, deprioritize ETF momentum's small edge, and prioritize the stock-control
   confounds before new stock parameters. These are evidence-based research-budget
   decisions, not claims of financial alpha.
5. **Next research is proposed, not launched.** Resolve scenario-capital/realized
   exposure and concentration controls, measure missing turnover/exposure inputs,
   then use independently specified validation. All viewed 2020–2025 years remain
   development data; a renamed chronological split is not untouched.

No strategy here establishes annual doubling with the desired downside behavior.
Cached T11 CAGR 119.67% accompanies 51.26% drawdown and a 2025 return of 4.04%; it is a
reference tradeoff, not evidence of doubling every year. No trained RL, LLM skill
advantage, statistical alpha or deployment readiness has been established.

## Interpretation limits

The broad stock control's observed peak closing gross exposure was only 69%,
versus 93% for stock momentum. Whole-share granularity and minimum fees at USD 10,000
can disadvantage a broad universe. Matching universe, dates, eligibility, costs
and nominal budget does not isolate ranking alpha from concentration, exposure
and position-count costs. Average exposure and an exposure/concentration-matched
counterfactual are unavailable. The mandate's USD 300,000 capacity is untested.

Hosted adjusted inputs and underlying publication/adjustment integrity remain
provider-dependent. Native P&L consistency is not an independent cash/fill/dividend
reconstruction. Drawdown uses daily closing equity and does not bound intraday or
future losses. Risk-free return is zero in Sharpe; credit interest is zero. Low-volatility and momentum universes also have different selection cadences; only within-family controls share the matched input hashes. Dollar turnover and average exposure are unavailable, so fills/fees are activity evidence, not a turnover estimate. Different signal families and stress contexts cannot be collapsed into one causal leaderboard.


## Execution and acceptance record

Hosted execution closed at 2026-10-26 22:02 UTC, before the fixed 23:18:40 UTC deadline.
All 14 launches are counted: two initial diagnostic cases, nine initial financial
cases and three technical retries (logging, subscription lifetime, and missing
momentum-cohort diagnostic coverage). Nine accepted financial cases plus cached
T11 produce 60 annual rows. There are no remaining hosted slots and no live run.
The initial low-volatility stock probe remains valid for that cohort; its
acceptance-coverage gap is distinct from native runtime failure.

| Attempt | Kind | Case | Result | Native ID prefix |
| ---: | --- | --- | --- | --- |
| 1 | diagnostic | asset_probe | failed-truncated-diagnostic | `9094a87ca9d5` |
| 2 | technical-retry | asset_probe | completed-verified | `30632326df1b` |
| 3 | diagnostic | stock_probe | completed-verified; original low-vol cohort only, coverage gap preserved | `2f2de7367e34` |
| 4 | financial | asset | completed-verified | `af801b158783` |
| 5 | financial | stock | completed-verified | `6a0914cbbdc6` |
| 6 | financial | lowvol | completed-verified | `3457aa240001` |
| 7 | financial | spy | completed-verified | `671ea52b5737` |
| 8 | financial | ew_asset | completed-verified | `9aff03263b9f` |
| 9 | financial | ew_stock | failed-target-price-unavailable | `6047dd04f6b5` |
| 10 | technical-retry | ew_stock | completed-verified | `dd9ff6cd3156` |
| 11 | financial | ew_low | completed-verified | `7a3fb4b0d9ce` |
| 12 | financial | stress | completed-verified | `21340033b9ac` |
| 13 | financial | ew_stress | completed-verified | `52c6813f9600` |
| 14 | technical-retry | stock_probe | completed-verified | `0bd037e6268a` |

Implemented and verified within this protocol: complete checksummed summaries;
source/control identity; independently derived 1508-session calendar; annual/full
NAV compounding, return moments, Sharpe and Calmar; annual/continuous drawdown and
underwater consistency; matching historical membership/eligible-feature hashes;
SPY exact parity; cached T11engine/baseline-manifest compatibility; zero rejected,
non-MOO or pending orders in accepted cases; and native P&L plus financing residual
below USD 0.06. All nine new cases incurred zero debit interest; cached T11incurred
USD  0.276 under the same model. This does not independently reconstruct fills/cash.

The offline suite, browser selectors, source restoration and file manifests are
recorded in the final evidence receipt. Browser checks cover all 2020–2025 annual
views and all three ranking choices, comparing 1710 displayed cells. Native-browser
screenshots show both the full and 2025 annual tables. The private project template
was restored with exact clipboard/hash verification; no additional backtest was
launched for restoration.

Remaining unverified items are research/strategy-fit limits, not hidden completed
checks: independent raw hosted-input and cash/fill reconstruction; unseen alpha;
average exposure/dollar turnover/factor or issuer-risk attribution; scenario-capital
and market-impact capacity; intraday/future loss bounds; taxes; and paper/live
operation. The other seven shortlisted candidates remain queued. No publication,
commit, deployment, paid service, broker action, new agent, new service or MLflow
import was performed in this epoch.
