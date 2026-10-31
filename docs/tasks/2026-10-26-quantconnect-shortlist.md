---
status: active
updated: 2026-10-26
owner: project-maintainers
---

# Ten QuantConnect research candidates

Status: **description-screened, reproduction unverified**. Reviewed2026-10-26.
Selected for useful mechanisms and different research questions, not a performance
ranking. These are QuantConnect research/tutorial implementations, not a top-ten
list of current competition/Strategies leaderboard entries. The
[lessons](2026-10-26-research-lessons.md) motivate the selection; the
[intake SOP](../research-intake.md) owns subsequent qualification.

Primary discovery: [QuantConnect investment strategy library](https://www.quantconnect.com/learning/articles/investment-strategy-library).
Individual article bodies and method sections were inspected. Legacy tutorial
links redirect to the research URLs below. Generic draft/pending-review page
chrome is not evidence of source quality, replication or account eligibility.

| ID / inspection order | Candidate and primary source | Published mechanism, not a reproduced result | Why inspect it / planned comparison | Inputs and principal qualification gap |
| --- | --- | --- | --- | --- |
| QC10-01 | [Asset Class Momentum](https://www.quantconnect.com/research/15338/asset-class-momentum/) | Select three of five asset-class ETFs by trailing12-month momentum; monthly equal allocation | Extend asset selection beyond sectors; compare equal-weight same universe, SPY and trend rule | Daily ETF prices/actions; exact original tickers/history, source version and actual free-account access unverified |
| QC10-02 | [Momentum Effect In Stocks](https://www.quantconnect.com/research/15364/momentum-effect-in-stocks/) | Rank large-cap stocks by historical momentum | Test stock selection versus ETF-only timing; compare equal-weight same point-in-time universe | Historical membership, market cap, prices/actions; current500-stock list alone creates survivorship concerns |
| QC10-03 | [Volatility Effect In Stocks](https://www.quantconnect.com/research/15381/volatility-effect-in-stocks/) | Select lower-volatility stocks using trailing daily returns in a large-cap universe | Risk-aware asset choice instead of a blanket exposure gate; compare same-universe equal weight and momentum | Daily prices plus point-in-time universe/fundamentals; sector/beta concentration and free access unverified |
| QC10-04 | [Asset Class Trend Following](https://www.quantconnect.com/research/15339/asset-class-trend-following/) | Five asset-class ETFs; ten-month moving-average eligibility and cash otherwise | Compare asset-specific exits against the common SPY traffic light and rotational momentum | Daily ETF prices/actions; precise allocation of inactive slots and decision/fill timing require code inspection |
| QC10-05 | [Residual Momentum](https://www.quantconnect.com/research/15304/residual-momentum/) | Rank standardized stock returns unexplained by Fama-French factors | Ask whether selection adds more than market/factor exposure; compare ordinary momentum | Point-in-time stock universe and causally available factor series; external custom-data loader/rights and short financing need review |
| QC10-06 | [Standardized Unexpected Earnings](https://www.quantconnect.com/research/15369/standardized-unexpected-earnings/) | Monthly stock selection using standardized earnings surprises; published top5% selection | Add an earnings-information mechanism distinct from price timing; compare same-universe momentum/equal weight | Quarterly EPS with historical publication availability; fundamental access and update timing unverified |
| QC10-07 | [Earnings Quality Factor](https://www.quantconnect.com/research/15259/earnings-quality-factor/) | Score earnings quality including accrual measures; long/short research | Explore fundamental selection and potential complementarity to momentum | Point-in-time accounting fields and restatements; borrow/dividends on shorts and source code version unverified |
| QC10-08 | [Pairs Trading With Country ETFs](https://www.quantconnect.com/research/15299/pairs-trading-with-country-etfs/) | Form relative-value ETF pairs from historical price distances, then trade divergence | Examine spread returns rather than outright bullish exposure; compare rolling formation controls | US-listed international ETFs; matched calendars, formation-only selection, short borrow, dividends and spread breakdown |
| QC10-09 | [Intraday ETF Momentum](https://www.quantconnect.com/research/15348/intraday-etf-momentum/) | Use first-half-hour ETF returns to predict the last half-hour direction | Different trading horizon; compare fixed same-session exposure and fee/slippage stress | Intraday history, auctions, spread/fill modeling and free runtime/data availability; daily bars insufficient |
| QC10-10 | [Volatility Risk Premium Effect](https://www.quantconnect.com/research/15382/volatility-risk-premium-effect/) | Sell an approximately one-month ATM straddle with a15% OTM put hedge | Learn an options premium mechanism and its tail-risk tradeoff | Full historical chains/quotes, contract adjustments, assignment and margin; local data absent. An OTM put does not bound a short call's upside loss; broad leverage permission does not approve uncovered writing |

## Evidence and access state

All ten have an official article describing a method. None of these exact source
implementations was cloned, pinned, installed or backtested in this task. Related
families already appear in our catalogue and planned multi-asset work; a new source
name is not a new independent strategy. No claim that these are ten untested
families, ten profitable systems or ten immediately executable free-account jobs.
No CAGR/Sharpe league table is provided: comparable dates/costs/financing and
complete metrics are unverified. Public historical claims stay upstream claims.

The SUE article reports Sharpe0.602 versus SPY0.43 during2009-12-01–2019-09-01;
this is one upstream historical claim, not our result or evidence of superiority
on our dates. Other headline metrics were not consistently qualified during this
screening and remain unassessed. Historical number of tried variants is unknown.
Exact downloadable revisions, author/file identities, code hashes, redistribution
licenses, data rights, engine compatibility, current free-account entitlements,
benchmark and all cost/financing assumptions remain open for every candidate.
No paid dataset, package, credentials or account operation was used.

## Proposed first wave

Start inspection with01asset-class momentum,02stock momentum and03low-volatility
stock selection. They ask whether target selection can improve the return/risk
tradeoff without another T11 threshold search.04trend following is a useful paired
control for01; these momentum/trend variants are correlated, not separate
independent profit sources. ETF candidates expand research scope beyond the
US-stock library lane without authorizing new acquisitions there.

Then inspect05–07to seek incremental factor/earnings information.08–10remain
later, data/execution-dependent references; do not simulate unavailable inputs
using daily SPY proxies. None is accepted as a replacement for T11 or a deployed
portfolio component. The potential for diversification is a hypothesis until
aligned return paths and joint-stress behavior are measured.

```text
Ten sources → source/code/access inspection → feasible frozen shortlist
     → separately authorized bounded reproduction → matched evaluation
```

Before a reproduction: pin the exact code; inspect dependencies/rights and hidden
external inputs; verify eligible free data; define economic hypothesis, point-in-time
universe, capital, sample, controls, costs/borrow/financing, trial ceiling and stop.
Report full/annual return, DD, Sharpe, Calmar, underwater/recovery, execution failures,
turnover and exposure. Do not force a common fee/slippage model across unlike
options/intraday/daily instruments; use declared realistic assumptions and show
comparability limits. No trial budget or automatic next run is created here.

## Subsequent first-three study

The [separate2026-10-26 comparison](2026-10-26-qc-selection-comparison.md) inspected
legacy source examples and tested declared adaptations of01–03with free hosted
data. It preserves interpretation changes, readiness gaps and technical failures.
It does not turn this initial screening into an exact reproduction or performance
validation of the published source implementations.
