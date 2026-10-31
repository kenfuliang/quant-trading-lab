---
status: active
updated: 2026-10-28
owner: research-maintainers
---

# Traffic-light gating of volatility-adjusted sector momentum

Classification: **development experience report with a negative joint-screen result**.
The [protocol](2026-10-28-sector-gate-v1.md), [frozen plan](../../research/plans/sector-gate-v1.frozen.json)
and [completion receipt](evidence/2026-10-28-sector-gate-v1.json) own this cycle's evidence.
The [golden standard](../research-standard.md) owns adoption. No candidate is promoted.

## Abstract

Six fixed, captured, independently reconciled cases compared a retained SPY
EMA/volatility traffic-light overlay against ungated volatility-adjusted sector
momentum and SPY hold. Over2017-02-01–2025-12-31, the overlay increases Calmar
from0.492530 to1.033047 at5bp and from0.482229 to1.003744 at10bp: relative gains
of109.74% and108.15%. Maximum drawdown falls from about29.7% to12.5%.
However, CAGR falls by1.726/1.743percentagepoints and longest underwater duration
increases from170sessions/248days to300sessions/436days at both costs.
The frozen requirement to improve Calmar without worse growth or recovery fails.
This is evidence of a risk/return tradeoff, not independent financial alpha.

## Method and prior knowledge

One sizing-stage change; monthly sector picks, input identities, cash actions,
whole-share accounting and cost/financing assumptions match the parent. The
[protocol](2026-10-28-sector-gate-v1.md) specifies the EMA50/200,20-return volatility thresholds,
five-close staged recovery, caps1/.5/0, first2016bar initialization, next-open
execution, monthly selection while in cash, and off-cycle reuse of monthly picks.
The historical price-peak component stays disabled. No thresholds, windows or
reentry rules were tuned after outcomes. No price-source or dependency changes.

Initial capital USD300000,98%full target,USD1/nonzeroorder and5/10bp adverse
fills per side, zero cash yield, no shorting or borrowed financing. SPY uses
entry-only hold with dividends in cash, exactly as in the parent; its mean gross
exposure is93.795%, not continuously rebalanced98% or a dividend-reinvested index.
Gated sector mean exposure is86.091%, versus97.949% ungated at5bp. There is no
exposure-matched constant-risk control in this six-case scope, so the overlay's
incremental predictive value cannot be isolated from lower participation.

Data are qualified private local raw prices and issuer-reconciled distributions,
including payment dates and2025splits. The evaluation window contains2242sessions;
2017is partial, anchored2017-01-31. Raw2016warmup is an explicit new gate seed,
not exact parity with the older2004-seeded SPY fixture. History has already been
viewed and is restated; this is not an untouched holdout. No training or RL.

## Matched full-period results

| Cost bp | Policy | Calmar | CAGR | Max DD | Sharpe | Longest underwater sessions / days | Orders |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | Gated sectors | 1.033047 | 12.8871% | 12.4748% | 1.0029 | 300 / 436 | 430 |
| 5 | Ungated sectors | 0.492530 | 14.6128% | 29.6689% | 0.8632 | 170 / 248 | 389 |
| 5 | SPY hold | 0.434733 | 13.8848% | 31.9387% | 0.8517 | 489 / 709 | 1 |
| 10 | Gated sectors | 1.003744 | 12.5665% | 12.5196% | 0.9809 | 300 / 436 | 429 |
| 10 | Ungated sectors | 0.482229 | 14.3099% | 29.6745% | 0.8481 | 170 / 248 | 387 |
| 10 | SPY hold | 0.434540 | 13.8829% | 31.9485% | 0.8514 | 489 / 709 | 1 |

CAGR uses calendar elapsed years from the initial anchor. Drawdown is peak-to-trough
NAV loss magnitude; Calmar=CAGR/maxDD. Sharpe uses daily returns, sample standard
deviation,252annual sessions and zero risk-free rate. Underwater duration includes
the recovery session, retains censored episodes, and is not the duration of the
deepest drawdown unless those episodes coincide. The longest episodes above are
observed recovered, not right-censored.

At both costs, the challenger passes the Calmar and drawdown guards and is not
strictly dominated by SPY. It fails the predeclared CAGR and both duration guards.
The fixed10%Calmar minimum was not changed to accommodate the outcome. Headline
ranking and joint-screen disposition remain separate in the single leaderboard.

## Annual evidence

5bp results below; both cost levels, annual Sharpe/Calmar and annual underwater
metrics are in the saved comparison (`../../reports/bounded-study/sector-gate-v1-20261028/index.html`; private/local artifact, not published)
and its 54-row annual CSV (`../../reports/bounded-study/sector-gate-v1-20261028/annual-comparison.csv`; private/local artifact, not published).
Annual drawdown resets from the preceding year's last close. Annual Calmar uses
simple calendar-period return/annual maximum drawdown, not annualized partial-year
CAGR. Full-period and annual scores answer different questions.

| Year | Gate return | Gate DD | Ungated return | Ungated DD | SPY return | SPY DD |
| --- | --- | --- | --- | --- | --- | --- |
| 2017 partial | 19.088% | 4.569% | 19.088% | 4.569% | 18.679% | 2.524% |
| 2018 | -0.266% | 12.475% | -0.924% | 17.641% | -4.267% | 18.523% |
| 2019 | 22.770% | 2.917% | 27.904% | 2.917% | 29.335% | 6.270% |
| 2020 | 16.022% | 11.644% | 18.412% | 29.669% | 17.026% | 31.939% |
| 2021 | 19.325% | 7.483% | 19.329% | 7.484% | 26.654% | 4.808% |
| 2022 | 4.659% | 10.755% | 11.245% | 14.533% | -17.047% | 22.934% |
| 2023 | 17.799% | 8.548% | 15.054% | 13.672% | 23.722% | 9.142% |
| 2024 | 14.128% | 6.736% | 14.131% | 6.738% | 22.703% | 7.759% |
| 2025 | 3.730% | 8.408% | 8.290% | 11.333% | 16.192% | 17.290% |

The gate beats ungated annual return in2018and2023 at5bp;2017is identical.
It trails in2019,2020,2021,2022,2024and2025. At10bp it also narrowly exceeds2024,
showing why tiny cost-dependent annual differences should not become new rules.
In2022, the ungated selected sectors return11.245%, while the gate returns4.659%:
a broad SPY risk signal can constrain sectors that are still making money.

## Protection, missed rebounds and temporal effects

The gate spends1767sessions green,407yellow and68red. There are18cap changes after
the initial execution;125sizing decisions versus107monthly ungated decisions.
Every red execution day ends with zero ETF shares; prior dividend receivables
remain legitimate NAV. Cash is nonnegative in every audited account.

At5bp, ungated's deepest episode is2020-02-19–2020-03-23 (-29.669%). Gated's deepest
is2018-10-01–2018-12-24 (-12.475%). Worst rolling21-session return improves from
-28.980% to-10.315%; worst daily return improves from-10.627% to-4.556%.
These are observed development path statistics, not future loss limits.

The gate's longest underwater episode starts2022-04-20, bottoms2022-06-17 and
recovers2023-06-30:300sessions/436calendar days, despite only10.755%loss in that
episode. This shows why Calmar and maximum drawdown alone miss time costs.

All red episodes, rather than selected favorable crash dates, are preserved in
paired analysis (`../../.local/sector-gate-v1/result-analysis.json`; private/local artifact, not published). They are
2020-03-10–2020-05-11 (44sessions) and2025-04-10–2025-05-14 (24sessions).
At5bp their ungated close-to-close returns are+1.903% and+4.223%, versus gated
+1.091% and-0.394%. A crash avoidance signal can avoid a deep interim trough yet
miss enough rebound to lose over the complete red interval. These intervals are
close-to-close, including the first execution day's overnight exposure and sale
costs; flat end-of-day positions do not imply zero interval return.

Saved normalized daily-return differences are grouped by observed gate state.
They are descriptive paired outcomes, not additive compounded-wealth attribution,
independent regime samples, or proof that all gains/losses were caused by a
particular threshold. Both costs include all orders. At5bp gate fees areUSD430
versusUSD389, while modeled adverse slippage isUSD15040.91 versusUSD15323.00;
lower exposure offsets turnover in dollar slippage. No free execution assumption.

## Verification, failures and disposition

All six financial attempts completed, with six passed independent policy/account/
contribution/metric audits and exact zero NAV difference. Fresh ungated/SPY files
match the parent across32ledger/trade/contribution/event/summary/annual/temporal
files. Audit uses separate Fraction accounting, independent economic-factor and
sector-ranking construction, and independent EMA recurrence/volatility/state logic.
Synthetic checks reject corrupted gates and verify causal prefixes/recovery.

Four bounded synthetic child probes include two successes and intentional failure
and timeout. Their negative logs and partial artifacts are preserved. Cache-only
restart launches zero financial cases. Original sector inputs, eight parent cases
and549older C01–C06artifacts are preserved. There are no historical financial
failures or retries in this cycle. Qualification engineering failures are separate
from financial results.

The standalone HTML and its54annual rows are generated from saved artifacts.
Browser opening of its local file was blocked by browser URL policy; rendered
visual appearance is unverified. Numerical/table payload and saved files are
checked separately. No alternate browser or server workaround was attempted.

**Disposition: reject the fixed joint improvement target; retain both observed
risk benefit and opportunity cost.** Keep the ungated comparison reference;
do not silently promote a new universal incumbent or initiate a follow-up run.
The next proposed question is whether an exposure-matched control explains most
of the benefit, or whether broad-market gating should be conditioned on selected
sector strength. Either is a separately frozen task, not authorized tuning here.
Native NautilusTrader execution, brokerage parity, independent alpha and live
readiness remain unverified.
