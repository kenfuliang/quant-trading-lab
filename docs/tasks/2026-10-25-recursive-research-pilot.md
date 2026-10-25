---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Recursive research pilot: frozen initial questions

Status: design fixed before new financial simulation outputs. Supporting work under
the [ten-hour program](2026-10-25-recursive-research-program.md), not investment
selection or a replacement portfolio roadmap. Existing viewed2005–2025 SPY is
explicit development evidence. All outcomes, attempts and failures are retained.

## Cycle1: understand the existing sizing tradeoff

Question Q1: does the higher saved Calmar of EMA plus volatility targeting establish
better directional prediction, or a sizing/cost tradeoff? Fixed reference cases are
ID2 and ID32 at1x nominal exposure, original costs and all5283 evaluation sessions.
Measure CAGR, drawdown/recovery, annual outcomes, actual exposure, dividends and
fees. Existing ratio/exposure evidence can reject an unqualified predictive-alpha
claim; an unavailable matched-risk counterfactual remains a named uncertainty.
This action reads saved results and requires no new financial trial. It must not
claim that the10% volatility objective is a10% weight cap. A shallow drawdown is not
necessarily a shorter recovery or better growth outcome.

Next decision: retain a sizing tradeoff as a reference and investigate a distinct
mechanism rather than optimizing another volatility threshold on the same history.
If basic hashes/accounting do not agree, stop for integrity investigation first.

## Cycle2: test timing complementarity in one net SPY account

Question Q2: can fixed combinations of the existing EMA and RSI2 long/cash targets
improve the development-sample return/drawdown tradeoff under the same account and
cost model? No weights are fitted. The two interior weights below are simple
predeclared illustrations, not a search for an optimum.

| Case | Fixed intended long/cash signal mixture | Purpose |
| --- | --- | --- |
| ema-control | 100% ID2 | Reproduce existing1x control and verify wrapper parity |
| rsi-control | 100% ID11 | Reproduce existing1x alternative timing control |
| mix-equal | 50% ID2 +50% ID11 | Equal-mechanism allocation illustration |
| mix-trend-heavy | 75% ID2 +25% ID11 | A second fixed modest alternative-timing allocation |

Use the original saved raw SPY snapshot with2004 indicator warm-up and evaluate
2005-01-03–2025-12-31. Existing already-lagged directional targets are combined as
`allocation_factor=sum(weight_i*want_long_i)`; do not shift again. `want_long` is
factor>0. One net SPY account uses USD300000, nominal1x,99% sizing reserve, whole
shares,1USD commission per actual net trade,5bp adverse side cost,6% illustrative
ACT/360 borrowing, zero cash interest, dividends and the existing margin contract.
Defaults are for this offline model, not broker quotes or approved risk limits.

This is not summing independently scaled equity curves or pretending fixed fees
scale linearly with sleeve capital. Shared net holdings/trades use the existing
portfolio ledger and separate Decimal audit. No shorting, other instruments,
MLflow import, service start or source refresh is involved.

Primary descriptive comparison: net CAGR versus full-path daily-close drawdown
magnitude, with explicit Pareto tradeoffs. Secondary diagnostics: Sharpe, Calmar,
annual outcomes, actual exposure, costs, recovery and common-loss behavior.
Record worsened outcomes. A mixture is a descriptive improvement only when it
truly dominates a declared control on both primary dimensions; otherwise state
the tradeoff or rejection. Sample choice and prior views preclude a fresh alpha
claim even if every metric improves. No strategy is promoted operationally.

Before launch verify plan/source/code identities, source coverage, costs and case
budget. Reserve all four financial attempts in program state before execution.
Financial control outputs must match the old ID2/ID11 cases within1e-7USD ledger
rounding tolerance and exact trade direction/quantity/fill records; discrepancies
stop comparative interpretation. New output directories remain immutable.

## Cycle3: conditional cost sensitivity, not permission to tune

Only if Q2 completes and a named net-cost uncertainty remains, freeze a separate
maximum four-case study before launch. Candidate/control rules and weights stay
fixed; compare the specified original5bp cost against a declared10bp per-side
stress with all other accounting unchanged. Different cost contexts are not pooled
into one Pareto ranking. A cost-sensitive candidate is retained as such or its
cost-robustness claim rejected; do not choose a cheap-cost scenario as a new winner.
This possible follow-up is not launched or counted as completed by this document.

## Resource/termination and comparison

The whole program ceiling is12 new financial attempts, failures included; initial
pilot reserves4 only at launch. At most3 workers, one coordinated study at a time.
Saved-result replay/control reuse is labeled explicitly. No financial trial starts
after18:44 UTC; review19:14 UTC. A branch can stop earlier on useful rejection.
No new API/data purchase, broker operation, commit or publication is authorized.

Controller evaluation uses the same available questions/actions and source outcomes
for the proposed allocator and a fixed-order/breadth-first baseline with equal
budgets/protections. Record fixtures/replay versus fresh outcomes separately. Do not
strip safety or evidence protections from the baseline to make it lose. Count
critical errors, unique questions resolved, redundant work and costs; report ties.
A few decisions are a feasibility pilot, not proof of a superior research policy.
