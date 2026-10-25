---
name: trade-robust-evaluation
description: Evaluate whether a trading candidate's apparent improvement survives independent evaluation, search bias, parameter and cost sensitivity, uncertainty, and adverse scenarios. Use for evidence assessment rather than generating new variants.
---

# Robust research evaluation

Read [evaluation policy](../../../docs/research-development.md#robust-evaluation),
the [mandate](../../../docs/goals.md), and the candidate's frozen experiment
specification. Start from run manifests, daily ledgers, the complete trial history,
and the record of which data/results informed development. Request only missing
evidence necessary for the scoped decision; a summary table permits a limited
review, not an invented statistical assessment.

## Evaluate

- Establish what was fixed before evaluation: hypothesis, comparisons, parameters,
  splits, costs, decision criteria and trial budget. If criteria were chosen after
  viewing results, label that assessment exploratory rather than retroactive proof.
- Trace all attempted variants and prior views of evaluation data. The existing
  SPY suite is already viewed development evidence. Walk-forward labels do not
  restore independence when their scores selected the winner; identify an unused
  evaluation path or report that confirmatory evaluation is unavailable.
- Compare executable timing, dates, cash/dividend policies, capital, exposure and
  costs. Separate signal improvement from additional leverage. Apply the relevant
  instrument model; missing borrow, margin or derivative mechanics limit claims.
- Examine parameter neighborhoods, folds/regimes, turnover, higher costs and
  adverse scenarios. Use uncertainty methods suited to dependence, sample length
  and the selection process; disclose assumptions and inadequate samples. Do not
  apply an independent-observation bootstrap or an automatic Sharpe cutoff by default.
- Preserve all outcomes. A failed criterion is not permission to alter the frozen
  candidate and reuse its evaluation sample as though untouched.

## Return

Give an **improvement supported**, **rejected**, **inconclusive**, or **not assessed**
research verdict, scoped to the evidence. Include input identities, comparison
eligibility, tested criteria and results, trial/data exposure limitations,
uncertainty, missing checks and the smallest useful next action. Distinguish checks
actually run from proposals. Do not infer paper/live readiness or guaranteed loss
limits. Record durable evidence under the [development workflow](../../../docs/workflow.md).
