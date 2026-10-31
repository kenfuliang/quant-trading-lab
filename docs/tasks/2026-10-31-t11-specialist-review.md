---
status: active
updated: 2026-10-31
owner: research-maintainers
---

# T11 saved-evidence specialist review

Scope: apply installed skills as eight review perspectives within this chat,
not independent reviewers or autonomous agents. Input roots are the preserved
T11 reference pair, prior gate/SOXL/selector studies, hierarchy diagnosis and
current frozen sources. All outcomes were already viewed development evidence.

```text
Data + features + logic + portfolio + risk + execution + robustness
                              ↓
                  Research-management synthesis
                              ↓
            Supported findings / unknowns / next evidence
```

## Review bounds and expected outputs

One pass per work item: DATA, FEATURES, LOGIC, PORTFOLIO, RISK, EXECUTION,
ROBUSTNESS and MANAGEMENT. Zero financial runs, downloads, model fits, parameter
searches, broker calls, new services or agent launches. Source and exports are
read-only. Computation is limited to existing path/hash/coverage checks, aligned
return correlation, empirical tail statistics, order count categories and fixed
Calmar sensitivity. Order counts are not holdings/exposure or PnL attribution.
No new feature candidates, labels or feature-response tests are authorized.

Each output must name observed evidence, its interpretation, verdict and precise
missing artifact. The scope is diagnosis; it does not grant a new experiment
budget or alter the current incumbent. The catalog and existing procedures remain
authoritative; this is a task report, not another skills or policy catalog.

## Findings

Completed eight request-scoped reviews. Findings are multiple perspectives of
one assistant, not independent validation. No financial budget was reopened.

| Work ID / skill | Result | Evidence / blocker | Verdict |
| --- | --- | --- | --- |
| DATA · trade-data-audit | Both official-export hashes match the prior reference audit; closing paths have1508unique sorted positive finite observations and identical calendar hashes | Entire provider history, corporate-action vintages and original daily inputs are not saved; existing reconstruction is aggregate-compatible, not original daily parity | Conditional for descriptive analysis; blocked for full reproduction |
| FEATURES · trade-feature-engineering | Source uses Wilder RSI/SMA tactical features and a separately RAW-seeded SPY EMA/volatility gate | Gate drawdown variable is fixed at0; missing/short QQQ61-bar history falls back to0%60-day return in one helper; incidence and feature quality unknown without logs | Contract risks identified; predictive usefulness not assessed |
| LOGIC · ask-algo / ask-quant | Source preserves multiple tactical branches; cap is applied uniformly; execution acts on changed intentions | Mapping SOXL-only or monthly momentum changes branch behavior, not just target ranking; no branch-ID history or marginal branch PnL | Preserve full baseline; marginal branch claims inconclusive |
| PORTFOLIO · trade-portfolio-analysis | Two matched paths correlate0.914863 over1508daily return intervals; gated export includes506leveraged-long,367inverse-equity,32volatility-product and93other order records | Order categories are not holdings, dollar turnover, factor exposures or PnL; no new portfolio combination tested | Shared return dependence supported; diversification benefit unassessed |
| RISK · ask-risk / performance diagnosis | >5%loss sessions69→49; >10%loss sessions9→6; empirical worst5%mean loss7.49%→6.44% | Six gated losses still exceed10%; gate cannot enforce30%full-path DD; tail estimate is historical and dependent | Tail reduction with residual severe risk, not a loss guarantee |
| EXECUTION · ask-algo / local source review | Order counts1062/998, finite positive recorded prices and ordered create/fill timestamps; prior export literal statuses3andtypes4for all records | Intent completion stops fixed-weight maintenance; staged sell-then-buy delays and fill semantics need event-level audit; complete account reconciliation missing | Structural consistency only; operational readiness unverified |
| ROBUSTNESS · trade-robust-evaluation | Aggregate reference repeatability and same-engine adverse cost evidence exist | Viewed2020–2025, selected winner/trials, missing exposure/restricted controls and input snapshot; no untouched holdout | Descriptive result supported; generalizable improvement/alpha inconclusive |
| MANAGEMENT · trade-research-management / ask-pm | All eight analyses accounted for; latest wave remains closed at10slots, four unique completed policy/cost summaries | Capture failures, omitted comparisons and unknown last submission preserved; no invented performance rows | Review complete; unchanged leaderboard and precise next handoff |

## Data and feature findings

The export pair and candidate paths remain exactly those examined in the
[official export validation](2026-10-29-t11-export-validation.md). Current hash,
ordering/uniqueness,1508-session calendar, positivity and finite-NAV checks pass.
These are account-path checks, not raw ETF OHLC/volume/action qualification.
The original private source is hashed separately; no code changed during review.

The feature review is a contract/source audit, not a new feature search or label
association test. RSI uses native Wilder initialization; SPY tactical SMA200 and
other branch inputs differ from the market gate's first-close-seeded EMA50/200
and20-return sample volatility. RAW-SPY2004seed and adjusted strategy histories
are distinct contracts and must not be interchanged in a local port.

Two source behaviors merit explicit instrumentation:

- `GateCore.update` sets `dd=0.0`; its peak tracker is not an active portfolio or
  price drawdown brake. It classifies trend/volatility with hysteresis. Adding an
  actual portfolio-DD rule would be a new strategy change, not repairing a
  mistakenly omitted guaranteed30%stop.
- `_t11_feaver_bear` starts QQQ60-day return at0and leaves it there if a61-bar
  history request is empty/short. This can make missing history indistinguishable
  from flat return. No evidence in this review establishes that it occurred in
  either reference run. Log availability/end timestamps and explicit invalid
  reasons before claiming a causal bug or automatically changing behavior.

Do not estimate predictive accuracy or fit a market classifier from these exports:
original per-session feature values and matured independent labels are absent.

## Portfolio and risk findings

Returns are daily simple account-equity changes with each path's ownUSD10000
2019-12-31anchor; matched start/end intervals are verified before correlation.
Pearson correlation0.914863 describes two related versions of the same strategy,
not two independent alpha sources or a crisis-diversification guarantee.

The gated export has998orders across13observed instruments; inverse and volatility
positions are represented. The latest six-ETF selection universe excludes many
of these possible positions, explaining why it is not a clean bullish-basket
ablation. Counts do not prove their profits, time weights or economic leverage.
Long shares of leveraged/inverse products can carry substantial underlying risk
without negative account cash or direct account borrowing. Zero observed debit
interest does not establish an unlevered portfolio.

Empirical ES95 here is minus the mean of the worst `ceil(.05*1508)=76`daily
simple returns. It is7.4888%ungated versus6.4414%gated. Observed losses strictly
below−5%occur69/49times; losses below−10%occur9/6times. These are overlapping
market episodes, not independent trials or prospective risk bounds. The gate
reduces tail severity without satisfying the30%full-path drawdown aspiration.
The [hierarchy report](2026-10-31-t11-hierarchy-headroom.md) retains the
36.90%cross-year drawdown and293-day recovery evidence.

## Execution and robustness findings

The source's90%reserve multiplies branch weights and gate cap at target creation.
It is **not continuously maintained realized exposure**: after an intent finishes,
unchanged intent returns without new maintenance trades. Prices, partial fills,
waiting and drift must be distinguished from target weights. Red at a completed
close is not immediate liquidation; the controller uses staged MOO reductions,
waits for open orders and then submits buys. Native daily timestamps and order
labels alone do not independently prove executable opening prices or intraday
risk. No synthetic timing test is treated as a real execution audit.

Prior same-engine native cost stress weakens full gated T11Calmar2.492→1.713
at25→50bp, a different metric convention from custom2.494. Cost changes alter
quantities/orders as well as debits, so a simple fee-subtraction attribution is
not valid. Whole-shareUSD10000tests also do not certifyUSD300000capacity or
identical percentage paths. These remain separate future modelling questions.

Reproduction of summary numbers is useful engineering evidence. Multiple uses
of the same already-viewed six years, related sources and hand-selected variants
do not supply independent validation or a probability of beating the incumbent.
No finite achievable upper bound or forward Calmar expectation was established.

## Reconciled next handoff

The seven analytical perspectives agree that the next prerequisite is a bound,
source-identified session record joining **branch ID, proposed targets, features,
gate/cap, own orders/fills, realized holdings and account changes**. Questions
about branch-specific caps, target risk, rebounds and execution are hypotheses
until that join exists. Macro conditioning alone cannot explain target risk;
execution correctness alone cannot establish signal quality.

A finite next task proposal is one **zero-financial-run evidence-readiness audit**
for that session contract against the existing reference pair: inventory exactly
which fields exist, map all missing producers, verify availability/timing on saved
or synthetic fixtures, and deliver pass/blocked per field. No strategy optimization
or new run is initiated by this review. A later financial collection needs its
own qualified route and explicit finite allowance; this report grants neither.

## Checks and closure

- [x] Eight expected work items returned findings, evidence limits and verdicts.
- [x] Original export hashes checked against prior audit; matched path calendars,
  ordering,1508rows, positive finite values and fill/create ordering checked.
- [x] Aligned correlation, empirical tail statistics and order-category counts
  computed from saved inputs; no accounting/financial replay.
- [x] Fifteen existing synthetic export, precision, indicator and conformance
  tests pass. They do not establish provider or native-engine parity.
- [x] Public report and private source/diagnostic artifacts bound in the receipt.
- [x] Leaderboard receives a no-new-score closure link, not fabricated metrics.
- [ ] Complete feature/branch/gate/holdings trace and independent ledger replay.
- [ ] Untouched generalization, verified alpha, or paper/live readiness.

[Review receipt](evidence/2026-10-31-t11-specialist-review.json) owns per-work-item
status and artifact hashes. Private raw sources and exports remain ignored;
no original evidence was modified or published.
