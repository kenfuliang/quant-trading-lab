---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Fixed daily SPY allocation adaptations

This document owns the local rules in `allocation_overlays.py`. These allocation
methods are local research specifications, not reproductions of a published
strategy or evidence of investment advantage. They use the saved SPY history;
no additional dataset or service is required for these specified adaptations.
The [leverage model](leverage-model.md) owns fills, financing and portfolio state.

```text
Saved SPY closes → lagged sizing input → next-open target exposure
                                             ↓
Prior-close portfolio equity → CPPI sizing → common ledger and costs
```

Build indicators over the full history before slicing evaluation dates. The API
`build_allocation_signal(raw, strategy_id)` uses the same finite, positive,
consistent OHLC and ordered unique DatetimeIndex validation as the
[daily signal contract](daily-strategies.md). It returns `open`, `low`, `close`,
boolean `want_long` and `allocation_factor` in [0,1]. Completed-close decisions
are shifted exactly once; callers must not shift them again. Apply the factor
to the declared nominal exposure before the ledger's sizing/cash-reserve policy.
This means the 10% volatility objective is scaled with nominal exposure; it is
not a promise of 10% realized portfolio volatility at every leverage setting.

| ID | Frozen rule |
| --- | --- |
| 31 | Annualized volatility is the sample standard deviation (`ddof=1`) of the last 20 close-to-close simple returns times sqrt(252). At a completed close, factor=min(1,0.10/volatility), with factor=1 for exactly zero volatility. Hold long when ready. Insufficient history gives zero factor and cash. |
| 32 | Same volatility factor as ID31; hold long only when EMA50 > EMA200. Recursive EMAs use `ewm(adjust=False)` with 50/200 observations required. Otherwise cash. |
| 33 | Compute underlying SPY raw-price drawdown as close/running maximum close−1, including all available past closes. Require 20 closes before decisions. Factor=1 above −10%; factor=0.5 from −10% through −20%, inclusive; factor=0 below −20%. Exposure can recover automatically as the underlying drawdown improves; no permanent halt. |
| 34 | CPPI fixed floor=0.8×initial portfolio capital, multiplier=3. At each open use previous session's closing portfolio equity E and target exposure=min(nominal,3×max(E−floor,0)/E). Nonpositive E means zero target. Floor does not grow with the portfolio peak and earns no interest. |

ID33 uses **underlying raw SPY drawdown**, not portfolio drawdown. It excludes
cash dividends from the sizing signal; dividends remain in the portfolio ledger.
The first 20 closes are a warm-up, while the running high includes that history.
Thresholds compare close/running-high directly with 0.90 and 0.80, avoiding cancellation around exactly −10% or −20%.

ID34 emits constant `cppi_floor_fraction=0.8` and `cppi_multiplier=3.0` columns
for the portfolio-aware ledger. Its allocation factor is 1 after the first
history row; the ledger computes the dynamic CPPI allocation from its own
previous-close equity. It must not infer portfolio equity from SPY prices.
Initial capital supplies the previous-equity baseline before the first evaluated
session. On an unsliced history, the first row has no prior decision and stays
flat; with the saved pre-evaluation warm-up, the first evaluated row is eligible.
Cash-floor interest is zero under the current financing contract.

The floor, volatility target and drawdown thresholds are sizing inputs, **not
loss guarantees or approved live risk limits**. Overnight gaps, costs, financing,
margin changes and discrete trades can breach a CPPI floor or any reassessment
level. A cash allocation may lock in losses; renewed exposure can lose again.
These methods contain no shorting, options or broker instructions.

Offline tests establish causal invariance, warm-up, factor bounds, known sizing
inputs and CPPI metadata. Actual CPPI portfolio behavior requires independent
ledger reconciliation; this module's tests alone do not verify that integration.
