---
name: trade-promotion-review
description: Review evidence against scoped criteria to recommend a trading candidate's next research or operational stage. Use for retain, reject, investigate, or stage-readiness decisions; this skill does not deploy strategies or change broker state.
---

# Candidate promotion review

Read [promotion policy](../../../docs/research-development.md#promotion-review),
the [mandate](../../../docs/goals.md), and the criteria for the requested transition.
Identify the exact candidate, current stage, intended next stage, experiment
specification, run/data identities, trial history and evaluation evidence. Review
the relevant [paper SOP](../../../docs/operations/paper-connection.md) only for an
operational transition; a review is not permission to invoke it.
For Alpaca use its [research-to-paper handoff](../../../docs/operations/alpaca-paper.md#research-to-paper-handoff).
Report [evidence transitions](../../../docs/research-development.md#evidence-transitions-are-separate)
separately: aggregate compatibility, daily decision/account reproduction and paper
readiness. None implies the next. Apply the canonical
[comparison review](../../../docs/research-development.md#calmar-comparison-eligibility)
before interpreting a Calmar rank; missing evidence remains unknown.

## Decide from evidence

- Assess each scoped criterion as met, failed, unknown or not applicable with a
  source. Distinguish a missing check from a failed check. If criteria were not
  predeclared, propose criteria and an exploratory decision; do not manufacture a
  retrospective pass or a universal Sharpe/Calmar threshold.
- Check reproducibility, data rights/quality, audit status, evaluation independence,
  costs, uncertainty and mandate fit to the extent required for this transition.
  A higher score alone does not establish an improved strategy or portfolio.
- Preserve open decisions about leverage, concentration, liquidity and loss
  actions. Neither the doubling aspiration nor the 30% reassessment reference
  supplies missing acceptance thresholds.
- Separate research evidence from operational evidence. Backtests cannot prove
  paper connectivity, order/risk/reconciliation behavior, recovery or live readiness.
  Paper observations cannot establish profitability or simulated/live equivalence.
- Resolve issues within the authorized offline review scope without adding approval
  prompts. Missing prerequisites yield a bounded recommendation and next action;
  they do not authorize account changes, broker connections, orders or deployment.

## Return

State the exact transition reviewed and recommend **retain at current stage**,
**advance research**, **investigate**, **reject/retire**, or **not assessed**.
For a requested operational transition, separately report readiness as **supported**,
**blocked**, or **unverified**, limited to verified criteria. Include evidence links,
remaining conditions, explicit unknowns and the next bounded action. Record the
decision under the [development workflow](../../../docs/workflow.md); preserve
superseded candidates and contrary evidence. A recommendation does not execute it.
