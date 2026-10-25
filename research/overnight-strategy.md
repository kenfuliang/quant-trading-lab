---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Precommitted close-to-next-open SPY exposure

This document owns catalogue ID19's signal and execution schedule. The family is
locally feasible using the saved daily SPY opens, closes and dividend records;
classifying it as necessarily requiring intraday history was too restrictive.
Actual closing-auction fills and order deadlines remain unverified by daily bars.
This is a fixed local adaptation, without a claim of established alpha.

```text
Precommitted overnight exposure plan
              ↓
Buy at modeled session close → carry shares/debt overnight
                                           ↓
                        Interest and dividend accounting
                                           ↓
                           Sell at next modeled open
```

`build_overnight_signal(raw, strategy_id=19)` validates the full OHLC frame through
[daily signal validation](daily-strategies.md), returns `open`, `low`, `close`, a
boolean `want_long`, and constant `execution_schedule='overnight'`. The constant
long plan is shifted once to preserve the shared interface: first row false,
subsequent rows true. Build on warm-up history before evaluation slicing. There
are no fitted parameters and no close-dependent entry condition. Because the plan
is predetermined, using the current close as the execution mark does not use that
close to choose whether to trade.

The portfolio simulator must explicitly support this schedule. Its ordinary
next-open-only long/cash execution is insufficient. Enter a whole-share long
position at each evaluation session's close and fully exit at the next session's
open. The close entry may use the configured exposure, cash reserve and financing
constraints. Apply $1 commission plus 5 basis points adverse spread/slippage on
**each** entry and exit, with the existing rounded fill-price convention. Credit
ex-date dividends on shares held from the preceding close before the opening
exit. Charge debt interest for calendar days held overnight, including weekends,
using the configured annual rate/day-count convention. Intraday cash after the
opening exit earns the model's zero cash interest. The final session can enter
at its close; retain and mark that position at the final close, with the entry
costs included and no invented subsequent opening exit or liquidation fee.

The [leverage model](leverage-model.md) owns portfolio sizing, financing, dividends
and margin assumptions. Implementation and independent ledger evidence must
confirm the special execution schedule; signal tests alone do not prove its
portfolio returns. Daily opens/closes are research execution marks, not proof
that a real broker can fill the modeled size at auction or charge the assumed
costs. Overnight gaps can be large; a daytime low is not an overnight trading
price and cannot be used to liquidate after the position has already exited.

Signal tests cover the one-session shift, schedule tag, preserved price/date
columns, warm-up slicing, deterministic output, invalid inputs and independence
from current or future price changes. No broker connection or order is involved.
