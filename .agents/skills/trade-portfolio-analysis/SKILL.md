---
name: trade-portfolio-analysis
description: Assess whether trading candidates improve an existing research portfolio through aligned return analysis, exposure attribution, joint stress losses and implementable allocation. Use for portfolio combinations rather than ranking standalone Sharpe ratios.
---

# Portfolio research analysis

Read [portfolio policy](../../../docs/research-development.md#portfolio-analysis)
and the [mandate](../../../docs/goals.md). Identify the reference portfolio,
candidate versions, dated equity/position ledgers, cash flows, instrument models,
proposed allocation rule and evaluation criteria. Unknown risk budgets remain
unknown; the approximately 30% drawdown reference is not an approved hard cap.

## Analyze

- Verify compatible valuation timestamps, currency, calendars, capital and
  cash-flow treatment before deriving returns. Explain overlap and exclusions;
  do not silently forward-fill stale asset values or treat missing returns as zero.
  Summary Sharpe/Calmar/return metrics cannot establish correlation or joint losses.
- Measure standalone and marginal contributions, shared market/factor exposures,
  concentration, leverage, turnover, drawdown duration and simultaneous stress
  losses. Low full-period correlation alone does not establish crisis diversification.
- Compare the proposed combination with the same reference portfolio and simpler
  allocations. Distinguish fixed starting allocations with drifting weights from
  periodic rebalancing, and include the actual rebalance costs and cash policy.
- Keep weight selection inside development/validation data. Record allocation
  trials and evaluate the frozen combination separately; optimizing weights over
  the whole displayed history yields an exploratory result.
- For joint margin accounts or derivatives, use a portfolio-equity ledger covering
  cash, financing, margin, multipliers, expiry/assignment and joint liquidation as
  applicable. Summing isolated leveraged equity curves does not prove implementable
  cross-margin performance. With missing mechanics, label the result a limited
  allocation illustration and identify the needed model.

## Return

Provide an evidence-backed comparison, uncertainty and stress findings, allocation
assumptions, material incompatibilities and a **beneficial**, **not beneficial**,
**inconclusive**, or **not assessed** research conclusion. Separate measured facts
from proposed weights/limits; candidates remain research proposals, not selected
investments. Preserve evidence through the [development workflow](../../../docs/workflow.md).
