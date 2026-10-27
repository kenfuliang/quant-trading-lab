---
status: active
updated: 2026-10-27
owner: research-maintainers
---

# Research decision brief template

Complementary presentation template. Copy only for a concrete saved
cycle/task; replace prompts and remove inapplicable branches. Aim for one page
of core findings and link complete tables. This brief derives from authoritative
evidence; it does not replace the [cycle record](research-cycle.md), its machine
receipt or the [experience paper](research-paper.md).

Follow [GRS](../research-standard.md) for claims/disposition/report readiness,
[scoring](../research-scoring.md) for eligibility, units and comparison meanings,
and [research development](../research-development.md#performance-diagnosis) for
temporal definitions. Do not amend frozen criteria while writing the brief.

## Decision at a glance

- Title / as-of date / author and reviewer:
- Cycle/task, standard and exact incumbent → challenger references:
- Evidence classification: development technical report / independently validated
  research report / negative-results technical report; label synthetic engineering
  explicitly when applicable:
- Disposition and reason under GRS; identify the exact source decision:
- Most useful finding, strongest counterevidence and material limit:

Keep document maintenance status, cycle state, evidence class and metric
availability separate. State no run as no run, not a zero return. Keep failed
required gates visible even when a headline result looks attractive.

## Question and comparison contract

- One question, changed stage, mechanism and falsifier:
- Frozen plan / incumbent / challenger / simpler controls / prior attempts:
- Universe, matched dates, capital, costs/financing and decision/fill timing:
- Primary criterion, meaningful effect, guardrails and tolerance: link the frozen
  definitions rather than restating a different rule:
- Data/code/config/environment identities; previous fitting/evaluation access:
- Comparability: comparable / declared controlled treatment / incomparable, with
  reason; identify any intended difference in exposure, universe or execution:
- Required checks: pass / fail / unknown, each with its audit reference:

## Results: choose the applicable branch

Every cell needs value + units + source, or an explicit missing, undefined,
not-applicable or incomparable reason. For a delta, state its direction and units
(for example, percentage points); do not combine unlike metrics into a score.

For financial results with eligible account paths:

| Measure / frozen definition | Incumbent | Challenger | Simpler control | Difference / status and source |
| --- | --- | --- | --- | --- |
| Full-period net CAGR | | | | |
| Maximum drawdown magnitude; observation frequency | | | | |
| Sharpe; return frequency and risk-free assumption | | | | |
| Calmar; horizon and drawdown convention | | | | |
| Longest underwater period; sessions and censoring | | | | |
| Recovery/deepest episode; dates and recovered/open status | | | | |
| Cost, financing, turnover and effective exposure; where supported | | | | |

Annual evidence: link the complete year-by-strategy table or CSV containing
annual return, annual drawdown, Sharpe and Calmar where defined. Identify partial
years and coverage. State annual-reset versus carried-peak conventions explicitly;
do not confuse longest underwater duration with the deepest drawdown episode.
Summarize favorable **and** unfavorable years in the narrative.

Temporal evidence: link the declared rolling-return/Sharpe, worst-period and
underwater tables/figures with their observed-session windows and coverage. Keep
open/left- or right-censored episodes labeled. Include ES/tail diagnostics only
when the frozen design and available artifacts support them.

For infrastructure or research-process fixtures instead:

| Process measure | Simple baseline | Proposed workflow | Source / scope limit |
| --- | --- | --- | --- |
| Reference-checked errors / invariant failures | | | |
| Distinct correctly resolved questions | | | |
| Duplicate/redundant attempts | | | |
| Logical attempts versus observed process/financial launches | | | |
| Resource use and wall time; equal limits | | | |
| Failure/restart/artifact-integrity outcomes | | | |

Label task exposure as known development fixtures or genuinely withheld evidence
as supported. Financial metrics are not applicable to synthetic engineering.
Passing fixture checks or resolving more questions does not establish alpha.

## Diagnosis, failures and missing evidence

- Where did gains/losses or process differences arise? Cite actual attribution,
  episodes, decisions or traces; state when attribution is unavailable:
- Alternative explanations: exposure, cost, universe, timing or selection effects:
- Failed/partial/unexecuted cases and their impact; exact attempt/audit references:
- Robustness and adverse evidence; missing/undefined/incomparable metrics:

## Lesson and next evidence

- Decision source and exact version retained, provisional, rejected or otherwise
  disposed under its existing GRS decision; operational readiness separately:
- One actionable lesson and the regression/preflight/procedure it changes:
- Smallest next uncertainty and evidence condition; separate finite scope required:
- Paper-style report eligibility: refer to GRS; link a report only if it exists:

## Evidence footer

Link the authoritative task/cycle, JSON receipt, frozen plan, source report,
input/output manifests and audits. Record run IDs/hashes and environment identity.
Use safe aggregate references for private/restricted artifacts; state local
availability and access limits. Link the read-only audit/review command rather
than a command that restarts an exhausted financial budget. Name unavailable
reproduction evidence explicitly.
