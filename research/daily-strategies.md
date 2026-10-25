---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Fixed daily SPY signal adaptations

This document owns the exact signal rules in `daily_signals.py`. These are local,
long/cash research adaptations of named strategy families. They do not replicate
an external strategy's entire sizing, stop, portfolio or execution system and do
not claim an established investment advantage. Parameters were fixed before this
comparison; no parameter search is performed.

```text
Full raw OHLC history, including 2004 warm-up
                  ↓
Completed-close features → long/cash decision → shift one session
                                                   ↓
                                  Next-open portfolio simulator
                                                   ↓
                                 Costs, financing, risk and reports
```

`build_signal(raw, strategy_id)` accepts an ordered, unique, nonempty
`DatetimeIndex` with finite positive `open`, `high`, `low`, `close` columns and
consistent price ranges. Optional volume must be finite and nonnegative. It
returns `open`, `low`, `close`, and boolean `want_long`; the flag already applies
the previous session's completed-close decision. The caller must not shift it
again. Build features on all available history before slicing evaluation dates.
Indicator warm-up does not itself create a position. A rule requiring 252 prior
sessions can remain flat briefly after the beginning of 2005 if the available
2004 snapshot contains fewer prior observations.

| ID | Fixed rule evaluated at completed close |
| --- | --- |
| 1 | Long when SMA50 > SMA200; otherwise cash. |
| 2 | Long when EMA50 > EMA200; otherwise cash. |
| 3 | Long when close > SMA200; otherwise cash. |
| 4 | Long when MACD(EMA12 minus EMA26) > its EMA9 signal; otherwise cash. |
| 5 | Long when close > SMA200 and ADX14 >= 25; otherwise cash. The ADX filter can force an exit. |
| 6 | Enter above the maximum high of the **prior** 20 sessions; exit below the minimum low of the prior 10. Hold between thresholds. |
| 7 | Turtle-style adaptation: enter above the prior 55-session high; exit below the prior 20-session low. Long/cash, without pyramiding, unit sizing, trade filters or the original Turtle stops. |
| 8 | ATR close breakout adaptation: enter when close > prior close + 0.5 × prior ATR14; exit when close < prior close − 0.5 × prior ATR14. Hold between thresholds. This is a close rule, not an intraday stop-order fill. |
| 10 | Enter when close > prior session high; exit when close < prior session low. Hold between thresholds. |
| 11 | Enter when RSI2 < 10; exit when RSI2 > 50. Hold between thresholds. |
| 12 | Enter below SMA20 − 2 × population standard deviation20; exit at/above SMA20. |
| 13 | Enter when 20-session population z-score < −1.5; exit when z-score >= 0. |
| 14 | Connors RSI adaptation: mean of close RSI3, signed-streak RSI2 and percentile rank of current one-session return against the **preceding** 100 returns. Enter below 10; exit above 50. Rank is the percentage of preceding returns strictly smaller; ties are not counted. |
| 15 | Enter when five-session close return < −3%; exit when that return >= 0. Hold otherwise. |
| 21 | Long when close / close252sessionsago − 1 > 0; otherwise cash. This local raw-price signal excludes dividends, which the portfolio ledger handles separately. |

EMA and Wilder-style smoothing use pandas `ewm(adjust=False)` recursive seeds,
with the full stated number of observations required before use. RSI averages
positive and negative close changes with alpha 1/period; zero gains and losses
give RSI50, only zero losses gives RSI100. ATR averages true range with alpha
1/14. ADX averages absolute directional imbalance with the same alpha; zero total
directional movement gives zero imbalance. This is a specified recursive
initialization, which can differ from libraries that seed Wilder smoothing with
a simple mean. Bollinger and z-score windows include the completed current close.
Zero price standard deviation gives z-score0. Equal thresholds follow the exact
strict/non-strict comparisons above.

Stateful rules enter only when flat, exit only when held, and otherwise preserve
the target. They reset flat while indicators are unavailable. There is no shorting,
pyramiding, stop fill, option exposure, volatility sizing, or automatic leverage
inside this module. The caller owns all sizing, dividends, costs and financing;
see the [leverage model](leverage-model.md) for that contract. Raw close signals
and synthetic daily execution retain the data limitations of the
[original SPY methodology](README.md).

Offline tests cover prefix/future-mutation invariance for every implemented rule,
boolean output, warm-up, flat-price behavior, RSI hysteresis, and a channel entry
and exit executed at the next open through the existing portfolio ledger. They
also reject duplicate, unsorted, nonfinite and inconsistent inputs. These checks
establish causal implementation behavior, not profitability or a replication of
published research.
