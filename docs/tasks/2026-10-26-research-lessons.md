---
status: active
updated: 2026-10-28
owner: project-maintainers
---

# Research lessons through the licensed-candidate comparison

User requested this consolidation on 2026-10-26. This is a dated synthesis of
inspected development evidence, not a replacement for original experiment receipts,
the [mandate](../goals.md), [research procedure](../research-development.md) or
[roadmap](../roadmap.md). Historical attempts and failures remain in their original
records. This is not an exhaustive trial inventory. The initial eight-lesson synthesis
launched no new runs; the bounded selection follow-up below has its own counted
execution record. Different study windows and models cannot form one leaderboard.

| ID | Lesson and observed evidence | Consequence for the next research design | Remaining uncertainty |
| --- | --- | --- | --- |
| L01 | Risk reduction and growth preservation are separate. The retained EMA/volatility SPY gate survived cost/delay challenges versus EMA, but holding still grew faster. Removing price-peak conditions improved the earlier gate's historical tradeoff. [Robustness](2026-10-25-rsi-gate-robustness-review.md), [epoch](2026-10-25-rsi-risk-gate-epoch.md) | Ablate components and compare benefits with displaced growth; do not add rules merely for complexity | Reduced exposure may explain much of the benefit; independent timing alpha is unproved |
| L02 | Smaller drawdown can mean longer recovery. Gated T11 changed CAGR119.67%→92.03%, drawdown51.26%→36.90%, Calmar2.33→2.49 and longest underwater146→199sessions. Annual reset DD was below30% in every gated year but continuous DD was36.90%. [T11 study](2026-10-26-qc504-t11-gate.md) | Measure continuous peaks, annual reset DD, underwater duration, censoring and ending wealth; CAGR retention76.90% differs from wealth retention44.62% | No exposure-matched control; hedge suppression is a hypothesis, not established attribution |
| L03 | Execution affects strategy rankings. Prior standalone sleeves had rejected orders; common staging/reserves/financing produced five observed zero-rejection paths and changed rankings. [Funded execution](2026-10-26-qc504-funded-execution.md) | Qualify execution before ranking signals; preserve rejected paths and compare exact controls | Several execution/allocation changes occurred together; no isolated financing effect or future fill-safety proof |
| L04 | A broader universe does not guarantee improvement. Sector momentum CAGR13.63% versus SPY13.95%; DD29.68% versus31.94%, longest underwater195 versus488sessions. Equal sectors had lower CAGR and deeper DD than SPY. [Sector study](2026-10-25-sector-momentum-comparison.md) | Compare selection with SPY and equal-weight universe under matching assumptions | Results depend on period/universe; independent daily hosted accounting and unseen advantage remain unverified |
| L05 | Small ratio improvements may be cost-fragile. EMA/RSI mixtures lost their Calmar advantage over EMA at10bp. [Recursive review](2026-10-25-recursive-research-review.md) | Test plausible costs and timing before extending a weak candidate; record the dead end | Sensitivity followed inspected results; it is not untouched confirmation |
| L06 | A risk feature is not a profit score. Range and volatility were highly redundant; return associations changed between blocks; few independent gate episodes supported labels. [Feature review](2026-10-25-feature-engineering-skill.md) | Define risk and return targets separately; audit redundancy, release/decision time and independent episode counts | No trained/calibrated predictor or incremental feature advantage established |
| L07 | High CAGR is not annual doubling. Funded T11 CAGR119.67%, but2025return4.04%; ensemble2025return84.46%. [Funded execution](2026-10-26-qc504-funded-execution.md) | Show annual outcomes and regime weaknesses; a full-period winner is not universally best | No tested system demonstrated annual doubling with roughly30% continuous DD |
| L08 | More variants and LLM process structure are not evidence of more alpha. The suite has22SPY adaptations×4exposures, not88independent discoveries; process comparisons did not establish a skill/RL advantage. [Suite](../../research/strategy-suite.md), [recursive review](2026-10-25-recursive-research-review.md) | Count correlated trials and preserve exposure history; prioritize information gain over repeated same-data tuning | No trained RL advantage, independent alpha or complete historical search-count claim |

```text
Observed weakness → frozen hypothesis + controls → bounded test
       → cost/execution/temporal audit → retain or stop → independent validation
```

## Current decision

Keep T11 and its capped version as development references with different tradeoffs.
No candidate is selected for deployment. The next informative gate question is an
exposure-matched ungated control; separately test whether caps suppress useful
hedges. These are proposals, not executed follow-ups. Viewed2020–2025 history
cannot become untouched by relabeling a split. The hosted studies usedUSD10,000;
capacity and execution at the mandate'sUSD300,000 remain unqualified.

For breadth, inspect the [ten-source QuantConnect shortlist](2026-10-26-quantconnect-shortlist.md)
before freezing any further experiment. This shortlist does not reorder the
portfolio roadmap or authorize code execution, data purchases or broker actions.

## Selection-completion follow-up

The [completed first-three review](2026-10-26-selection-completion.md) owns the
14-launch ledger, controls, final metrics, decision cards and limitations. This
follow-up adds evidence; it does not erase the initial eight lessons or reset
viewed-data exposure.

| ID | New lesson | Research consequence |
| --- | --- | --- |
| L09 | A history-count request returned only210bars on the July3,2023 early close; a wider causal window restored253. ABNB/SNOW short post-listing windows remain excluded. | Qualify calendar/history semantics; do not relax lookbacks or invent missing data. |
| L10 | Broad-stock staging lost an unheld target subscription; the repaired return retained current/delayed targets while preserving feature membership. | Include subscription lifetime in execution contracts; distinguish native completion from valid financial evidence. |
| L11 | Stock momentum CAGR29.62% versus6.47% for equal weight includes a peak-gross difference93% versus69% and different position-count costs. Stress CAGR26.25%, DD30.43%. | Prioritize capital/exposure/concentration controls before claiming alpha; the approximate30% reassessment level remains material. |
| L12 | ETF momentum's CAGR6.25% versus6.00% came with606 versus494underwater sessions and lower Sharpe. | A small Calmar improvement is not overall dominance; keep this direction low priority. |
| L13 | Five lowest-volatility stocks returned2.31% with29.86%DD versus5.96% and18.87% for their control. | Stop this fixed implementation; individual-stock volatility ranking is not a portfolio risk budget. |

Next work is proposed, not launched: resolve theUSD300000 scenario and practical
control confounds, then require independent validation. No trained RL/LLM process
advantage, annual-doubling system, independent alpha or broker promotion follows.

## Stock-risk ablation follow-up

The [five-case gate/sector review](2026-10-26-stock-risk-ablation.md) separately
executes the user-requested concentration/market-gate test. This does not reopen
the prior budget or resolve the earlier USD300000/exposure-validation proposals.

| ID | New lesson | Research consequence |
| --- | --- | --- |
| L14 | Transferring the retained gate to stock momentum changes CAGR29.62%→19.65%, DD29.66%→26.67%, Calmar1.00→0.74 and underwater585→606sessions. | A gate retained on SPY/T11 is not an automatic improvement for another selection process; stop this fixed transfer as a default improvement rather than retuning it on the same history. |
| L15 | Sector-only gives21.07%CAGR/22.87%DD/573underwater sessions, but27of360selections have unknown sectors and are held as cash. PLTR is among those excluded. | Distinguish concentration control from metadata-availability exclusion; qualify historical sector data before claiming a diversification effect. |
| L16 | The36%sector decision cap still permits41.33%peak observed sector exposure under drift/staged fills. Combined controls reduce DD to20.68% but CAGR to14.35% and retain586underwater sessions. | Record target versus actual exposure and growth versus recovery separately; more controls do not imply dominance or a hard loss/exposure bound. |
| L17 | Complete57-security original attribution reconciles within2cents and reveals NVDA+$9844.62, PLTR+$6855.94 and AVGO+$4378.66. IDs can retain older ticker prefixes; yearly security attribution is absent. | Capture chosen IDs, observed classifications and dated display names prospectively; preserve accounting/counterfactual/causal distinctions and disclose missing temporal attribution. |

No overlay replaces the original automatically. Sector-only remains a qualified
risk-control research alternative; historical classification and exposure/capital
controls need qualification before independent validation. No deployment or
additional experiment follows this record.

## Historical-sector and exposure-control follow-up

The [bounded three-case review](2026-10-26-sector-matched.md) preserves the earlier
unknown-as-cash result and adds conditional historical-business sector inferences.

| ID | New lesson | Research consequence |
| --- | --- | --- |
| L18 | All 27 missing selections also lack alternate historical vendor fields. Dated filings support explicit research labels for JD, PLTR, BABA and GEV; native display data confirms GEVW represents GEV. | Keep inferred labels separate from recovered vendor truth, require strictly prior availability, expiry and permanent identity, and disclose researcher choices made after viewing results. |
| L19 | Sector cap gives24.52%CAGR/25.48%DD/0.9622Calmar versus target-matched24.27%/27.03%/0.8980. Actual average gross still differs by0.2865points, and sector wins annual return in only two of six years. | Distinguish reducing exposure from changing allocation; retain the modest conditional risk-control alternative without claiming annual dominance or independent alpha. |
| L20 | Longest underwater remains583 versus584sessions for the matched control and585original; all end below earlier peaks. Sector exposure reaches41.64% despite36%target. | Drawdown depth, recovery time, censoring and target-versus-realized exposure are separate acceptance dimensions. A smaller drawdown does not establish quick recovery or a hard holding limit. |

The five-attempt budget is closed; no further simulations or deployment follow.


## Licensed CAPM framework alternative follow-up

The [CAPM/SPY receipt](2026-10-26-capm-spy-comparison.md) owns the fixed 2016–2025,
USD 300,000 context, preserved failures and the separately approved accounting
retest. Both scoped budgets are closed. These findings do not reproduce the exact
hosted CAPM tutorial or identify a new strategy.

| ID | New lesson | Research consequence |
| --- | --- | --- |
| L21 | A tutorial name does not specify executable behavior. The licensed alternative uses 29 legacy tickers, reverse-regression ranking, framework insights and traded SPY itself 2,331 times. | Pin code and inspect the complete framework pipeline; distinguish the published strategy, official alternative and our dated/costed adaptation before interpreting returns. |
| L22 | A 1% per-security stop did not bound portfolio loss: this unchanged fixed alternative had 99.92% closing DD, 7,995 fills and −51.08% CAGR at 25bp/fill; SPY had 14.82% CAGR/33.57% DD. | Stop this default candidate. Joint entry/exit/re-entry and turnover deserve a separately bounded ablation; no isolated causal cost/risk effect follows from this two-case comparison. |
| L23 | Active holdings omitted retired securities' realized results. Lifetime native net profit plus current-mark unrealized P&L reconciled to USD 0 and preserved every full/annual metric exactly. | Use lifetime accounting for rotating universes; check the definition of mark-to-market versus hypothetical liquidation profit, and reconcile event fees against lifetime native fees. This remains a native-book check, not an independent cash/action replay. |
| L24 | Clipboard-verified editor code still led to a stale-SPY job. Its attempt was retained; a user-approved one-run extension used reloaded source, explicit successful build and emitted case identity. | Verify save/build state before launch, qualify actual run identity before ranking, and count failed/stale simulations in the budget. Never erase a failure or silently widen trials. |

SPY's 84.21% time underwater and 488-session longest decline despite 14.82% CAGR
reconfirm L02: growth, loss depth and recovery duration are different dimensions.
No untouched evaluation, independent alpha or broker promotion follows this record.

## CAPM cost and stock-stop ablation follow-up

The [nine-case receipt](2026-10-26-capm-cost-stop-ablation.md) owns the separate
closed budget: nine qualified fresh cases in ten attempts, with one preserved
instrumentation failure. Both prior 25bp controls reproduce all 11 metric records.
These are fixed-policy contrasts on already viewed 2016–2025 history.

| ID | New lesson | Research consequence |
| --- | --- | --- |
| L25 | Cost and the stop interact. Stop-on CAGR is 7.74% with no explicit costs, 6.03% with IB commissions and −51.08% at commissions plus 25bp stress. Stop-off gives 10.87%, 10.66% and 6.18%; the total cost × stop CAGR interaction is −54.13 percentage points. All six monthly selection hashes match. | Separate ordinary fees, slippage stress and stop policy before diagnosing a signal. These are closed-loop effects on quantities, holdings and later orders, not additive dollar cost attribution or measured live execution costs. |
| L26 | The 1% stock stop reduces commission-only full DD from 42.13% to 37.17%, but lowers Calmar 0.253→0.162 and extends longest underwater 716→945 sessions. Annual return improves only in 2017; annual DD is deeper in six years, including 2018 and 2022. | Require annual, continuous and recovery checks together. A per-security loss rule does not establish consistent crash protection or a 30% portfolio loss bound. Stop-on's high turnover merits diagnosis; exact stop/re-entry event attribution remains unverified. |
| L27 | Even the most favorable tested CAPM setting, no explicit costs/no stop, earns 10.87% CAGR versus matching SPY 14.82%. Every CAPM variant has lower Sharpe/Calmar, deeper DD and longer maximum underwater duration than its control. All debit financing charges are zero. | Retain this fixed alternative as negative development evidence; do not promote it or keep tuning its threshold on the viewed history. This does not reject all CAPM ideas, establish a financing effect or complete the broader tutorial catalog. |
| L28 | The first passive selection audit stopped before any close and its end handler masked the initiating exception. Moving audit state off custom native-callback attributes resolved the failure; the control then exactly reproduced prior performance. | Keep audit state at a supported boundary, qualify emitted source identity and preserve failed attempts. Control reproduction supports an instrumentation-only repair; the masked initiating exception remains inferred rather than directly recovered. |

The [browser comparison](http://127.0.0.1:8765/capm-ablation-v1/index.html) contains
90 annual rows and full/annual factor contrasts. No paid data, new threshold
search, unseen validation, trained RL advantage or deployment follows this test.


## Licensed-candidate readiness and causal adaptation follow-up

The [G-Score receipt](2026-10-26-gscore-spy-comparison.md) and
[causal Dual Thrust receipt](2026-10-26-dual-thrust-spy-comparison.md) preserve the
negative CAPM baseline and the aggregate bounded trial history.

| ID | New lesson | Research consequence |
| --- | --- | --- |
| L29 | G-Score's current quarterly ROA field throws a retirement error. The provider's migration notice identifies legacy ratio values dated before actual filings; restoring compatibility on the old engine would not qualify causality. No legacy run or G-Score financial case was launched. | Treat API compatibility, point-in-time availability and free entitlement as separate gates. Stop a blocked implementation before returns; do not silently substitute annual ratios or use an obsolete biased feed. |
| L30 | The licensed Dual Thrust plot example computes a range including the current session's eventual high/low/close, then reads it at the open. The fallback uses only five prior completed SPY sessions, next-minute execution and explicit costs. | License permission does not establish statistical validity. Pin and preserve the original, test availability boundaries, and name material repairs as adaptations instead of exact reproduction. |
| L31 | The first intraday control reconciled native accounting but emitted no fee-model name because its closing audit only inspected invested positions. A fill-time observation repair reproduced all 11 metric records exactly and confirmed the native IB model. | Observe execution when it occurs. Flat-at-close checks miss intraday exposure and model evidence; preserve the rejected metadata attempt and require path reproduction after passive repairs. |
| L32 | Causal Dual Thrust has −3.80% CAGR/34.06% continuous closing DD versus SPY14.65%/33.16%; longest underwater2,493 versus488sessions. It beats the daily intraday control but loses in nine of ten years. Annual reset DD never exceeds10.43%, while minute DD reaches34.76% despite8.25%mean gross. | Stop this fixed adaptation as an improvement. An inferior control is not enough; annual resets and low average exposure can conceal persistent capital erosion. Preserve costs/borrow and temporal evidence; short-side causation, zero-cost expectancy and other markets remain untested. |

The aggregate budget is closed at5/6attempts, including G-Score's blocked probe
and the preserved intraday observation failure. Three financial cases qualify
for this comparison; the candidate fails its frozen improvement screen. All30
annual rows and seven browser chart metrics are checked. No new simulation,
parameter optimization, independent alpha, annual-doubling result or promotion
follows these lessons.


## Licensed stock-pairs readiness follow-up

The [stock-pairs receipt](2026-10-26-stock-pairs-spy-comparison.md) owns this
separately bounded causal adaptation and its actual financial disposition.

| ID | New lesson | Research consequence |
| --- | --- | --- |
| L33 | The new adapter repeated a previously known history-count problem: a300-bar request stopped on the2016-11-25early close. The existing600-calendar-day workaround then supplied exactly250strict-prior aligned observations on all2,514sessions, with zero probe orders. | Carry known interface/calendar regressions into each new data adapter before financial runs. A wider acquisition window does not permit changing the fixed modeling lookback; preserve both the failure and the unchanged250-session rule. |
| L34 | The licensed pairs plot example sizes on future full-sample maxima, applies an ordinary ADF reference after estimating residuals, mixes price-SD and z units, and resets holdings each row. Native adjusted modes also use full action history. The declared adaptation uses causal sizing, cointegration-specific calibration, persistent dimensionless state, RAW execution and known-action SCALED_RAW history; all price/action/library gates pass. | Separate code permission, causality, statistical correctness and economic validity. Name material repairs as a mechanism adaptation; a successful input gate is not a reproduced performance claim or evidence that the strategy works. |
| L35 | The properly qualified pair still loses: −2.18%CAGR,25.62%DD,−0.41Sharpe and2,341underwater sessions versus SPY13.64%/31.26%/0.86/488. It has only one positive year and six flat years. Flat annual paths have undefined Sharpe/Calmar and zero resetDD while continuous losses persist. | Stop the fixed adaptation. A statistical go/no-go test, lower mean exposure or meeting a drawdown reference is not a profit score. Preserve continuous loss state and undefined ratios; do not assign zero or reward inactivity as success. |
| L36 | Holding the source's two surviving stocks gives64.66%CAGR with65.70%DD and1.27Sharpe, far above the pair's return but outside the loss reference. The pair itself was selected in hindsight and the hold control is not exposure/beta matched. | Use the control to diagnose opportunity cost, not to claim a repeatable stock-selection edge. Portfolio construction, point-in-time selection, loss risk and unseen validation need their own evidence before considering this growth prospectively. |

The five-attempt budget is closed: one failed input probe, one successful probe
retry and three qualified financial cases. Both fixed pair improvement screens
fail. All30annual rows, native accounting and seven browser metrics pass; CAPM
and Dual Thrust negative evidence remain unchanged. No new optimization or
deployment follows this lesson record.


## Golden-standard rollout and first cycle

[GRS-1.0](../research-standard.md) now owns pipeline and evidence requirements.
These entries preserve both a blocked new cycle and successful older evidence.

| ID | New experience | Research consequence |
| --- | --- | --- |
| L37 | [GRS-C001](2026-10-27-grs-c001-continuous-sizing.md) stopped after one control path because historical effective0/1 leverage diagnostics differed from current nominal1 representation. Trades and all other fields match; the frozen gate remains failed. | Carry known compatibility contracts into preflight. Preserve the consumed attempt and do not mistake invalid evidence for strategy loss or silently restart a closed budget. |
| L38 | [GRS-R001](2026-10-27-ema-volatility-experience-report.md) re-audits the older nine-path robustness result: gate improves on EMA in three contexts, while holding grows faster. No new financial path or algorithm improvement was created. | Paper-style experience sharing should name its comparison, selection history, costs and counterevidence. A rigorous retrospective report cannot stand in for a failed new experiment or independent future validation. |

## Sector momentum traffic-light gate: risk depth versus time

[Gate-v1 experience report](2026-10-28-sector-gate-experience-report.md) records six audited cases. Calmar
roughly doubles and drawdown falls from29.7%to12.5%; CAGR falls and underwater
duration increases170to300sessions. Broad SPY risk signals can suppress profitable
sector rotations (2022), and full red episodes include missed rebounds.
Record risk benefits and time/growth costs separately; headline ranking does not
override the frozen joint screen. No promotion, independent alpha or live claim.
