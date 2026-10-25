---
status: active
updated: 2026-10-25
owner: research-maintainers
---

# Saved SPY gate decisions and outcome labels

Work status: complete. Requested2026-10-25: implement decision/outcome records,
then diagnose saved gate behavior. Owners: [research lifecycle](../research-development.md),
[scoring](../research-scoring.md), [architecture](../architecture.md),
[performance operations](../operations/performance.md). No new financial simulation,
strategy tuning, source acquisition, broker operation or MLflow import.

## Fixed diagnostic definitions before output inspection

Reconstruct logs from saved signal/timeline/account evidence, clearly labeled
**reconstructed**, not contemporaneously captured live logs. Compare combined
and price-peak-ablated gates, each on EMA and daily-long bases, at5/10bp plusUSD1.
Use matched5283observed sessions,2005-01-03–2025-12-31,capital300000and original
cash/dividend/cost conventions. Preserve original failed process records; qualified
5bp controls remain separately qualified saved evidence.

Decision inputs are preceding-close features/state, base and capped targets,
preceding-close holdings/cash, and prior21observed-session raw-SPY return. Saved
observed-close date must be strictly before execution-session date and match its
previous source row. Same-session open/close/fills and all future outcomes are
excluded from the decision log and linked separately as realized execution.
Availability is a modeled daily-close boundary, not provider publication proof.

- Warning: yellow/red. Intended reduction: gate target below its own base.
- Already cash: base intends zero AND prior base shares zero. Base exiting today
  (targetzero but prior sharespositive) is separate. Gate-intended cash is not proof
  that a prior position never existed.
- Primary financial anchors: first session of each contiguous intended-reduction
  episode. Warning starts and red entry/exit are secondary event views. Daily
  outcomes are downloadable diagnostics, not independent samples.
- Horizons5/21/63observed sessions. Return=ending saved account equity divided by
  its own preceding-session equity (initialcapital for first row), minus1. Thus
  the decision-session overnight gap, costs and dividends remain included. Both
  paths retain actual subsequent policy decisions; this is a realized policy-path
  comparison, not a one-decision intervention or matched-wealth USD counterfactual.
- Label helped-during-loss only when base returnnegative and gate returngreater
  at an actionable reduction anchor. Missed-positive-move when basepositive and
  gate returnlower. Missed-rebound is that subset with prior21-session raw-SPY
  returnnegative, observable before the anchor. No post-hoc trough labels.
- Unactionable warnings get no avoided-loss/protection credit even if subsequent
  policy paths diverge. Other outcomes distinguish outperformance while base
  positive, worsened base loss, ties/mixed and censored. Return tolerance1e-10.
- Right-censor incomplete horizons: keep null returns/label maturity rather than
  shorten horizon or substitute zero. Event starts at evaluation boundary are
  marked left-censored. Exclude those from primary episode summaries.
- Summaries show evaluable/censored counts, base/gate returns and percentage-point
  gaps. Overlapping windows explicitly counted; do not sum overlapping returns,
  multiply episode averages into full-path P&L or claim statistical independence.

## Acceptance and checks

- Separate decision-input, execution-evidence and matured-outcome files with
  stable IDs, source hashes, schema and method version.
- Refuse misaligned/nonfinite/nonpositive ledgers, target violations, invalid
  state/lag or source hash changes. Validate immutable input manifests first and
  after output generation.
- Meaningful synthetic tests cover future perturbation, overnight anchoring,
  cash-versus-exit distinction, rebounds, unavailable outcomes and invalid inputs.
- Independently recompute saved-window labels and counts; run `make check` and
  inspect a browser-readable report. Preserve all old artifacts.

## Results and completion

The completed findings below are viewed-history evidence,
not a forecast, calibrated correctness label, untouched alpha, loss guarantee or
reason to reopen exhausted financial budgets.

## Completed diagnosis

Work status: **complete**. [Final browser review](http://127.0.0.1:8765/gate-decisions/20261025-v2/index.html)
and ignored `.local/performance/gate-decisions/20261025-v2/` preserve derived
artifacts. Eight gate/base pairs produced42,264decision records and126,792future
outcome windows. A scalar independent implementation checked every window's
anchoring, return gap, maturity/censoring and label. All187parent artifacts and
frozen source bytes were verified before/after reporting.

### Warning usefulness versus warning counts

At either cost, on the full5,283-session path:

| EMA overlay | Warning sessions | Intended-reduction sessions | Warnings while base already cash | Warning on base exit |
| --- | ---: | ---: | ---: | ---: |
| Combined price-peak/trend/volatility gate |2076|1057|1007|12|
| Price-peak-ablated trend/volatility gate |1247|228|1007|12|

These session counts reconcile exactly to warnings. They are not independent
alarms or successful forecasts. Both gates share the same1,007already-cash warning
sessions because the base EMA independently remains flat. For example,2008-01-10
used2008-01-09inputs, both targetszero and prior base shareszero. In2008there are
247such warning sessions;21-session subsequent base/gate returns on these daily
anchors are zero under this model. The reduction-episode analysis intentionally
does not award these warnings avoided-loss credit.

### Matched21-session reduction-episode outcomes

Boundary starts excluded; each horizon includes the anchor's overnight gap,
costs and actual subsequent policy changes. Positive-base underperformance is
split into prior-decline rebound and other positive moves.

| Gate/base and cost | Episodes | Helped during base loss | Missed rebound | Other missed positive move | Worsened base loss | Outperformed positive base | Mean gate advantage,pp |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Combined/EMA,5bp |23|5|7|6|2|3|−0.059|
| Ablated/EMA,5bp |21|4|6|4|2|5|+0.426|
| Combined/EMA,10bp |23|5|7|6|2|3|−0.057|
| Ablated/EMA,10bp |21|5|6|4|2|4|+0.421|

All these21-session anchors are complete; one adjacent pair overlaps for each EMA
policy. Cost can move a small outcome across a label boundary; counts need not
match between5/10bp. No hypothesis test or independent success-rate claim follows.
Daily-long-base comparisons and5/63-session views remain available in the package.

### Concrete cases, ablated EMA at5bp

| Anchor and outcome close | Base account return | Gate account return | Gate advantage | Diagnosis |
| --- | ---: | ---: | ---: | --- |
|2020-03-03→2020-03-31,21sessions|−22.42%|−3.90%|+18.52pp|Helped during a base loss after reducing target100%→50% |
|2022-03-10→2022-04-07,21sessions|+5.27%|+2.02%|−3.25pp|Missed rebound: preceding21-session SPY return−4.44% |
|2020-06-15→2020-07-14,21sessions|+7.35%|+3.70%|−3.65pp|Missed positive move; prior SPY returnpositive, so not labeled rebound |

At the same2022-03-10anchor, the10bp63-session view ends2022-06-08with base−2.67%
and gate−4.61%: worsened-base-loss, rather than the21-session missed-rebound label.
Labels are horizon-specific; they are not a permanent judgment of that decision.

**Concentration diagnostic, exploratory after viewing labels:** for ablated EMA
at5bp,21-session reduction-episode mean advantage is+0.426ppbut median−0.253pp.
Excluding the single2020-03-03anchor gives mean−0.478pp. This deletion is an
explanation of concentration, not a new strategy or a replacement result; keep
the full sample. A large crisis benefit and many smaller opportunity costs can
coexist. It does not prove removing crisis protection would improve the strategy.

## Implementation and validation receipt

- Implemented pure saved-data transformations in `reporting/decision_labels.py`,
  saved-evidence CLI `scripts/gate_decision_review.py`, HTML review and eight
  focused regression tests. No simulator is called.
- Logs separate decision-time fields from observed execution and matured labels;
  raw price drawdown is retained for audit but ablation explicitly records its
  active gate input aszero. Trigger flags are not exclusive causal explanations.
- Version1report is preserved. Browser inspection found cash warnings were
  unavailable in an episode-only view. Version2adds all daily already-cash warning
  anchors and a200-row display cap, with full CSV downloads. Financial paths and
  label definitions were unchanged; both output manifests remain verified.
- Browser checks inspected default summary,2020help,2022missed rebound,2008cash
  warnings, and10bp/63-session horizon switching. Screenshot/check receipts live
  in ignored `.local/gate-decision-analysis/`.
- Canonical lifecycle documents the implemented reconstruction and planned
  prospective emission boundary; README/performance SOP/scoring notes updated.
  No infrastructure milestone or runtime scoring-policy version changed.
- Final checks and exact output/source identities are recorded in the
  [machine receipt](evidence/2026-10-25-gate-decision-labels.json).

Remaining limitations: no live/contemporaneous capture or verified publication
latency; no isolated single-action causal estimate or matched-dollar loss
attribution; no untouched evaluation; same stylized ex-date dividend cash and
execution assumptions as saved studies. Prospective pre-execution log emission
still needs implementation in a newly scoped experiment. No strategy tuning,
financial simulation, new market-data acquisition, broker action, service start,
MLflow import, commit or publication occurred.

Final validation: `make check` exited0 with208tests,74documentation files and no broken dependencies. `git diff --check` passed. Independent source-feature/cash checks covered211,320values in addition to126,792window checks. No original run artifact or exhausted financial budget was modified.
