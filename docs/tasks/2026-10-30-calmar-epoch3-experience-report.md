---
status: active
updated: 2026-10-30
owner: research-maintainers
---

# Correlation diversification and sector breadth did not improve sector Calmar

Classification: **negative-results technical report**. GRS-1.1; cycles E3-C1/C2,
Calmar epoch3. AI-assisted project research on 2026-10-30; not peer-reviewed,
independently validated alpha or a production-strategy recommendation.

## Abstract

We tested two separately frozen pipeline changes on a fixed ten-sector ETF
momentum portfolio: correlation-aware target selection and sector-breadth market
classification. Twelve new captured financial cases, including matched controls
at 5bp/10bp costs, passed independent account and metric replay. Both challengers
failed the predeclared joint screen. At5bp, incumbent Calmar1.033 fell to0.581 for
correlation selection and0.467 for breadth. Returns, drawdown and recovery also
worsened. The incumbent remains unchanged; failures are retained as research evidence.

## Question and contribution

A prior residual-momentum readiness cycle was blocked by unqualified stock/action
and factor-vintage inputs. This broader goal explicitly continued to another
eligible mechanism using qualified fixed-sector inputs. C1 asks whether reducing
pairwise dependence improves the portfolio while retaining the same risk gate.
After rejection, C2 asks whether participation across sectors improves market
condition classification while retaining the original target picks. No third
mechanism, parameter search, leverage change or retrospective passing rule was added.

## Related work and provenance

[Lopez de Prado's research overview](https://www.quantresearch.org/Innovations.htm)
describes dependence/concentration-aware allocation methods; C1 is our small
specified greedy heuristic, **not HRP**. [StockCharts' percent-above-average documentation](https://chartschool.stockcharts.com/table-of-contents/market-indicators/percent-above-moving-average)
describes a breadth measure and whipsaw limitations. C2 substitutes fixed-sector
ETFs for a constituent-stock breadth universe and adds our declared staged gate.
No third-party strategy code or claimed performance is reproduced. New versioned
study modules fork our existing project accounting; original studies remain frozen.

## Data and information timing

Inputs are the preserved issuer-v2 bundle and source manifest qualified in the
[parent accounting task](2026-10-28-sector-issuer-qualification.md). Ten fixed ETFs
are XLB/XLE/XLF/XLI/XLK/XLP/XLRE/XLU/XLV/XLY, with SPY used by the incumbent gate.
Already-viewed evaluation spans2017-02-01–2025-12-31, with2016warmup;2017is partial.
The personal/local restated-history scope is not original point-in-time vintage
proof or permission to redistribute raw data. No data was acquired in this goal.
Monthly decisions use completed closes; features/gates shift once to the next
open. All cash/split/dividend/receivable assumptions and calendars are matched.

## Methods, controls and trial history

The [live task and frozen plans](2026-10-30-calmar-epoch3.md) specify exact rules,
criteria and actual launches. C1 keeps the highest volatility-adjusted momentum
sector and greedily chooses two from the top six to minimize mean positive
63-return correlations, with a declared12-decimal numerical tie rule. C2 uses
breadth above200-close SMA, fixed20/40/60/70percent thresholds and five-close staged
recovery. These rules were implemented and source-bound tested before C1 financial
outcomes; no financial parameter changed after viewing rejection.

USD300000;98percent target, whole shares, sell-first cash-feasible next-open fills;
5bp/10bp each side plusUSD1/order; zero borrowing, cash interest and taxes. Target
caps are not continuous intraday exposure limits. At each cost, C1 compares the
challenger with fresh gated top-three and gated equal-weight sectors; C2 compares
breadth with fresh gated and ungated volatility-adjusted top-three. Fresh gated
incumbents reproduce parent files byte for byte. Require10percent Calmar lift at
both costs, no lower CAGR, deeper daily-close DD or longer underwater duration,
and no simpler-control domination. Shared maximum12cases; all12used, zero retries.

## Results

The table gives5bp results; the machine receipts and local comparison contain
both costs, all controls,108annual rows and21/63/252-session rolling diagnostics.
Calmar is full-path CAGR divided by full-path drawdown magnitude; underwater
includes recovery and reports session/calendar durations with censoring.

| Variant | Calmar | CAGR | Max DD | Sharpe | Longest underwater sessions / days |
| --- | --- | --- | --- | --- | --- |
| Retained gated top-three | 1.033047 | 12.8871% | 12.4748% | 1.0029 | 300 / 436 |
| Correlation-aware selection | 0.581100 | 9.5850% | 16.4946% | 0.8023 | 402 / 585 |
| Gated equal weight | 0.703734 | 9.9458% | 14.1329% | 0.8797 | 489 / 709 |
| Sector-breadth gate | 0.467210 | 7.8778% | 16.8615% | 0.7180 | 527 / 768 |
| Ungated top-three | 0.492530 | 14.6128% | 29.6689% | 0.8632 | 170 / 248 |

At10bp, retained Calmar1.003744 exceeds correlation0.543798 and breadth0.433162.
Neither challenger satisfies any primary growth/depth/recovery improvement guard.
The lack of simpler-control domination alone is insufficient for promotion.

The combined browser report and charts are at
`.local/calmar-epoch3/review/index.html`; comparison/annual CSVs and standalone
`epoch3-comparison.png` are siblings. Per-cycle interactive reports, decisions,
ledgers, selections, contributions and temporal series remain under that private
root. Sources are [C1 receipt](evidence/2026-10-30-calmar-epoch3-c1.json) and
[C2 receipt](evidence/2026-10-30-calmar-epoch3-c2.json), not copied upstream results.

## Diagnostics and counterevidence

C1 reduced mean positive decision-time pairwise correlation0.5597→0.3939 over107
monthly selections with identical gate traces. Average exposure was essentially
unchanged, but trades430→468 and5bp slippageUSD15040.91→USD17807.99. A better
correlation feature did not improve portfolio outcomes; cost and displaced leaders
are plausible channels, not an independently identified causal decomposition.

C2 retained identical monthly picks. It spent291red sessions versus68, reduced
average exposure0.8609→0.7668 and increased trades430→487. The largest5bp annual
return gaps were2023(-17.22pp),2020(-7.75pp) and2022(-6.68pp). Conservatism did not
prevent deeper losses relative to the retained gate, and recoveries lengthened.
No decomposition treats cash warnings as independent tradable bets.

## Robustness, failures and limitations

Both cost contexts reject both fixed rules. Independent Fraction replay verifies
all twelve accounts with zero account differences and full/annual/rolling metric
checks. This is arithmetic verification within a model, not an independent
researcher, untouched holdout, liquidity/capacity test, execution realism proof or
future guarantee. History was already viewed; twelve correlated development cases
and two manually selected mechanisms supply no formal statistical alpha claim.
No threshold neighborhoods, alternative universes or future live observations
were tested. Restated data, whole-share rounding, illustrative costs, a short
2016seed and fixed ETF scope limit generalization.

Intentional synthetic failure and timeout traces are retained; they were expected
capture probes, not losing financial cases. One reporting invocation lacked
`PYTHONPATH` and failed before producing output; it was corrected without rerunning
a financial case. No financial failure or hidden retry occurred. Font-cache
warnings during PNG rendering did not prevent artifact generation; the chart was
visually inspected. All adverse financial cases remain sealed.

## Reproducibility and scope

[Terminal audit](evidence/2026-10-30-calmar-epoch3-terminal.json) verifies shared
journal chain, one-worker timing, exact plans/source snapshots/input hashes,
reservation-before-launch,12sealed cases and read-only cached restarts. It records
1080annual,168full and108rolling metric checks. Financial usage12/12; both branches
retired; no remaining slot. Closed commands must not be repurposed into a new
allowance. Current source and frozen snapshot hashes, build identity, actual exits
and private artifact references are retained in the cycle receipts. Generic RSI
financial adapters and broker readiness are not enabled by this local fixed study.

## Lessons and next question

Correlation reduction and more frequent red states are intermediate properties,
not substitutes for net portfolio outcomes. Retain the incumbent and both negative
baselines; do not tune the failed thresholds after inspection under the closed
budget. A next goal should investigate decision-time information quality or
resolve qualified residual-momentum inputs, rather than assume another sizing or
breadth variation will improve Calmar. The shared allowance ended at the actual
case cap, with no new goal, broker operation, deployment, commit or publication.
