---
status: active
updated: 2026-10-25
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

## Current bounded improvement goal

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
