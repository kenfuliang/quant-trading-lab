---
status: active
updated: 2026-10-28
owner: project-maintainers
---

# Project goals and investment mandate

This document owns user objectives and constraints. The [roadmap](roadmap.md)
owns implementation sequence; [research intake](research-intake.md) owns external
evidence handling. A mandate is not evidence that a return or loss target is achievable.

## User inputs confirmed on 2026-10-25

| Input | Confirmed value |
| --- | --- |
| Intended objective | Double portfolio equity every year while controlling downside |
| Annual growth aspiration | +100% per year; year-one scenario USD 300,000 to USD 600,000 |
| Permitted research scope | Margin, options, and other forms of leverage are allowed for consideration |
| Research data budget | Free/local data only; no paid datasets or subscriptions (confirmed 2026-10-25) |
| Initial data-library focus | US stocks only, daily history; SPY benchmark retained. Other markets deferred for this workstream (confirmed 2026-10-25); see [library plan](data-library.md) |
| Planned starting capital | USD 300,000 |
| Investment horizon | One year |
| Drawdown tolerance | About 30% peak-to-trough is a point to stop and reassess |

The one-year horizon is a planning horizon, not an instruction to deploy today.
Capital deployment, account funding, broker changes, and orders require their own
scope and authorization. The start/end dates of the investment year remain unset.

## Operational interpretation

Research objective: evaluate whether credible strategies can approach the annual
doubling aspiration while controlling drawdown and other downside risks within
the user's tolerance. Compare return/risk tradeoffs; there is no single strategy
that simultaneously maximizes returns and minimizes every kind of risk.

Use USD 300,000 as the scenario capital. Model fees, spread, slippage, financing,
borrow, and data/operating expenses where relevant; disclose omitted items and
tax treatment. Evaluate the +100% aspiration after modeled costs; whether the
user intends the target after personal taxes remains open. Historical results
estimate behavior under assumptions; they do not establish next-year returns.

Drawdown is `(current equity / prior peak equity) - 1`, including the initial
capital baseline. A 30% drawdown from USD 300,000 is USD 90,000; a later peak
changes that dollar amount. Thirty percent is a reassessment tolerance, not a
guarantee, maximum possible loss, automatic liquidation rule, or approved strategy
risk budget. Gaps, liquidity, and execution failures can exceed planned thresholds.

## Decisions still open before strategy selection

- Whether the full capital can be risked or part must remain available as cash;
  liquidity needs and end-of-year withdrawal requirements.
- Specific markets/instruments, standalone short-selling permission, maximum
  leverage and concentration, and permitted option structures. Broad permission
  to consider leverage does not establish numerical limits or permission for every
  structure, such as uncovered option writing.
- Benchmark and dividend/cash policy. Select an investable total-return comparison
  matched to the intended allocation; the existing SPY fixture does not decide it.
- Operational risk budgets: per position, daily loss, portfolio exposure, liquidity,
  and actions for warning, pause, review, and resumption.
- One-year start date, minimum acceptable outcome, and whether drawdown control or
  expected gain takes precedence when candidates trade them off.

Until these are resolved, external research can be cataloged and infrastructure can
be built. Candidate strategies remain unselected; leverage settings and standalone
shorting permission must be explicit before entering implementation defaults.

## Leveraged research and comparison requirements

Margin, options, and other leveraged instruments may be researched. Actual broker
permissions, eligibility, and supported instruments remain unverified. Broad scope
permission does not enable trading or authorize account changes.

Compare strategies at portfolio-equity level using the same USD 300,000 scenario,
not return on option premium or posted margin alone. Report gross/net exposure,
effective leverage, financing/borrow costs, margin utilization and liquidity buffer.
For options, also model volatility sensitivity, time decay, expiry, exercise and
assignment, contract multipliers, and multi-leg execution/assignment risk. A spread's
expiry payoff alone does not describe its interim cash and margin requirements.

Include gaps, volatility jumps, changing margin requirements, forced liquidation,
and joint-position stress scenarios. Show both unlevered/reference behavior where
meaningful and the proposed sizing; leverage is not evidence of a stronger signal.
Margin and some option strategies can lose more than the initial investment; see
[SEC investor guidance on leveraged strategies](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/leveraged-investing-strategies-know-risks-using-these-advanced-investment-tools).

Annual doubling is an aspiration, not an acceptance assumption. Retain lower-return
comparators and record when evidence fails to support the target. Whether to relax
the return aspiration or the risk tolerance if they conflict remains undecided;
leverage permission does not override the 30% reassessment tolerance.

## What success means at each layer

| Layer | Evidence needed |
| --- | --- |
| Platform | Reproducible data/runs, durable audit, observable failures, verified recovery; roadmap acceptance |
| Research | Traceable sources, licensed inputs, independently reproducible results, declared costs, chronological evaluation, uncertainty and adverse scenarios |
| Strategy fit | Compatible capital, horizon, permissions, data budget, liquidity, turnover and downside behavior; explicit benchmark and risk tradeoff |
| Paper operation | Correct order/risk/reconciliation behavior under faults plus supervised broker evidence |
| Investment outcome | Actual net return and downside over the chosen year, reported separately from research and paper outcomes |

Evaluation metrics should include net return, drawdown depth and duration, realized
volatility, tail-loss scenarios, turnover/costs, exposure and concentration, and
time to recovery. Define measurement cadence and cash-flow handling before comparing
candidates. Track shorter-term losses as well as annual results.

One year is an outcome window, not sufficient proof of a persistent edge. A single
profitable year or simulated Sharpe ratio cannot close research validation.

## Strategy search direction

After the open constraints are settled, screen published strategies for goal fit
before implementing them. Compare simple approaches as well as complex models;
complexity must justify added data, turnover, cost and operational requirements.
Record unsuitable candidates and reasons so we avoid repeated searches.

No strategy family has been selected by this mandate. The current infrastructure
milestones remain active while research intake proceeds as a separate planning lane.

## Recursive research objective confirmed on2026-10-25

Build an evidence-guided research process that scores candidate strategies and
research actions from several perspectives, retains prior attempts, explores
alternative mechanisms and pauses/retires specified dead-end hypotheses. Measure
credible research progress and useful uncertainty reduction separately from
investment returns. The user requested primary-source reuse/evaluation first,
parallel work when useful and a review of results in ten hours.

The [bounded program](tasks/2026-10-25-recursive-research-program.md) owns this
initiative's timed deliverables and temporary experiment limits;
[scoring](research-scoring.md) owns score meanings. Existing investment aspiration,
free/local constraint and open investment-risk decisions above remain unchanged.
Recursive instruction/state updates are not evidence of trained RL, improved
future returns, or authority to operate a broker.

## Completed bounded improvement goal: first risk gate

On 2026-10-25 the user authorized goal-backed recursive self-improvement. The
[first risk-gate epoch](tasks/2026-10-25-rsi-risk-gate-epoch.md) defines the measurable
experiment, budgets and stopping conditions. Research success is an audited
retain/retire decision about downside depth, duration and growth tradeoffs;
engineering progress is measured separately. The epoch subsequently resolved representation-only stops without rerunning failed
controls, completed sixteen financial attempts and one component-removal follow-up,
and recorded retain/retire decisions. The combined gate failed; the EMA/volatility
variant passed its specified historical path test. Independent validation remains
outstanding, and the epoch has no remaining financial budget.
This goal does not change the investment mandate or authorize deployment.

## Completed bounded goal: diversification readiness

The user selected the next goal-setting task after reviewing three research lanes.
The [ETF readiness epoch](tasks/2026-10-25-rsi-etf-readiness.md) records the chosen
SPY/IEF/GLD direction, source/native-account prerequisites and60-minute bounds.
Its current historical financial budget is zero; the fixed six-case study remains
a non-executable proposal. The audit completed with a not-ready decision: data/action
qualification and native corporate-action/allocator gaps remain. It does not amend the investment mandate,
reopen the completed epoch or establish asset/weight selection for deployment.

## Latest completed bounded goal: execution robustness

The user authorized continued goal-backed RSI development. The new
[frozen protocol](tasks/2026-10-25-rsi-gate-robustness.md) tests the previously
selected EMA/volatility-only gate against EMA and entry-only holding under three
execution contexts. Its [completion review](tasks/2026-10-25-rsi-gate-robustness-review.md)
records nine attempts, accounting/metric audits and the fixed decision. The candidate
survived this historical challenge and remains a candidate for independent validation.
All nine slots are consumed; no automatic parameter search or next financial epoch.
This advances evidence quality without changing the investment mandate or establishing
unviewed performance, annual doubling or deployment readiness.

## Completed bounded goal: multi-asset enablement and readiness

The user next authorized unlocking multi-asset trend and relative strength using
free/local data, then comparing with SPY/the frozen risk gate. The
[bounded protocol](tasks/2026-10-25-multi-asset-unlock.md) defined implementation,
qualification and a conditional ten-case comparison. The
[review](tasks/2026-10-25-multi-asset-unlock-review.md) records implemented signal/
allocator seams and the **not-ready** historical result. No financial case ran;
unused conditional slots do not carry into another epoch automatically. Full
historical comparison remains outstanding until its explicit data/model prerequisites
are verified. This readiness completion does not mean multi-asset trading is unlocked.

## Blocked bounded goal: source qualification and native comparison

The user authorized resolving the remaining data/accounting blockers and then
running the comparison. The [90-minute protocol](tasks/2026-10-25-multi-asset-qualification-v2.md)
defines32source artifacts across six domains, four synthetic native probes and
at most ten new financial attempts. Its
[active checkpoint](tasks/2026-10-25-multi-asset-qualification-v2-checkpoint.md)
records issuer/payment/calendar progress and tested native accounting. After three
consecutive goal turns with the same missing price input, the objective is blocked:
permission-qualified price data is pending and the historical comparison has not
run. The older completed readiness goals do not supply automatic
budget carry-over or evidence of profitable results.

## Completed bounded research goal:2026-10-28

[RSI Calmar epoch2](tasks/2026-10-28-rsi-epoch2.md) seeks audited same-context Calmar improvement under unchanged growth,drawdown and recovery guards. Its immutable contract owns finite execution bounds; GRS owns research disposition. This bounded evidence goal does not replace the investment aspiration or guarantee improvement. Status:completed bounded research; both cycles rejected after twelve audited cases. No qualifying improvement or remaining slots; incumbent retained.

## Blocked bounded goal: sector target selection

The [sector-selection RSI study](tasks/2026-10-28-sector-selection-rsi.md) tests a
different opportunity mechanism: volatility-adjusted ranking across fixed sector
ETFs, not another SPY participation change. Its first phase is free/local input
qualification with zero currently executable financial slots. Only qualified
inputs plus an immutable execution freeze enable the conditional eight-case
comparison. Missing inputs close as a blocked-readiness finding; strict Calmar,
growth, drawdown and recovery criteria stay prospective. This does not change
the mandate, reopen exhausted epochs or imply deployment readiness.

The [third-turn audit](tasks/evidence/2026-10-28-sector-selection-blocked.json)
records the goal tool's blocked disposition: no required local sector inputs or
qualified bundle arrived. Zero financial attempts; comparison remains incomplete.
Resume needs the actual authorized local input and valid original bounds.

## Completed fresh bounded goal: issuer-qualified sector comparison

[Issuer-v2 comparison](tasks/2026-10-28-sector-comparison-issuer-v2.md) follows
[issuer/accounting qualification](tasks/2026-10-28-sector-issuer-qualification.md).
It owns new eight-attempt bounds, February2017common start, strict Calmar/growth/
drawdown/recovery criteria and remaining runner/capture gates. The prior explicit
failed-readiness stop branch is closed separately, not counted as a completed
financial comparison. No new outcome, strategy adoption or deployment is implied.

Issuer-v2 comparison outcome: eight audited cases complete; the strict joint
target fails only the10bp drawdown guard despite18%Calmar gains.
[Report](tasks/2026-10-28-sector-selection-experience-report.md) preserves the
research lead, negative criterion and unchanged incumbent. No slots remain; the bounded comparison is complete with a rejected financial
target. Terminal evidence and preservation checks own closure.

Issuer-v2 terminal verification passed: eight captured/audited cases, zero retries,
no financial failures, no unused slots; leaderboard and report updated,489offline
tests passed. This completes the bounded research objective with a rejected joint
financial target, not a claim of adopted alpha. No further cycle starts automatically.
