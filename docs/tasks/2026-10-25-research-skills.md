---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Research skills construction and evaluation

**Completed:** nine project-local skills, canonical lifecycle and routing, structural
validation, paired behavioral evaluation and one targeted revision/retest. **Measured
incremental answer-quality benefit: not demonstrated in this small evaluation.**
No strategy returns, Sharpe/Calmar, operational readiness or unattended research-loop
capability were improved or established by this task.

## Scope and canonical impact

User requested parallel construction of the nine proposed research skills followed
by usefulness evaluation. Three author lanes each owned three skills. Coordinator
owned [research development](../research-development.md), [routing/readiness](../skills.md)
and evaluation. Root README, docs map, architecture and trade-project were updated;
portfolio roadmap priorities/milestone readiness remain unchanged. There are now
19 project-local skill entrypoints: five advisers, five prior workflows and nine new
research workflows. Session discovery may need refresh; direct SKILL.md paths work.

```text
Design → data audit → bounded experiment → diagnosis → candidate proposal
                             ↓                            ↓
                     robust evaluation ← next design revision
                             ↓
                 portfolio analysis → promotion review
                             ↓
                 project research history → next question
```

Instructions support a requested stage or bounded cycle using existing artifacts.
They do not launch a scheduler, add a generic optimizer or implement missing broker,
portfolio-instrument, catalog or research-history storage capabilities.

## Evaluation design and outcomes

The [frozen protocol](evidence/2026-10-25-research-skills-eval-protocol.json) defines
nine realistic tasks and three 0–2 checks per task: 54 possible points per arm.
Two fresh agents received identical raw inputs, output limits and side-effect scope;
one also read the nine skills and relevant canonical procedure. They received no
expected answers or prior conversations. A separate fresh agent graded anonymized
A/B answers, with coordinator arithmetic checks. Author agents did not grade their
own instructions. A documented arithmetic typo in the interval-count expectation
was corrected before any answer was read or graded; tasks/inputs stayed unchanged.

| Task / skill | Baseline | With skills | Observed behavior in both arms |
| --- | ---: | ---: | --- |
| Research design | 6/6 | 6/6 | Bounded four trials, falsifiable controls, viewed-history and open-risk constraints |
| Data audit | 6/6 | 6/6 | Found ordering/duplicate/OHLC/negative-volume/missing-close defects; checksum did not override invalidity/rights gaps |
| Experiment | 6/6 | 6/6 | Detected mismatched cached artifact hash and stopped at preflight |
| Performance diagnosis | 6/6 | 6/6 | Accurate saved-ledger metrics and annual evidence; sizing versus predictive-alpha distinction |
| Candidate evolution | 6/6 | 6/6 | At most two new variants, explicit controls/falsifiers/harms and preserved earlier failures |
| Robust evaluation | 6/6 | 6/6 | Identified repeated-test selection,2x/1x and zero/5bp confounding; no fabricated uncertainty |
| Portfolio analysis | 6/6 | 6/6 | 249 exact common observed intervals, correlation 1; excluded mismatched two-day interval and left summary-only C unassessed |
| Promotion review | 6/6 | 6/6 | Simulation audit did not establish operational paper execution readiness |
| Research history | 6/6 | 6/6 | Retained failed/no-return, rejected negative and exploratory positive attempts; created linked output records |
| **Total** | **54/54** | **54/54** | **Tie; no measured advantage** |

The reviewer confirmed hashes, metric/annual arithmetic, interval exclusions and
history output artifacts. This is artifact-quality review, not a complete execution
trace audit. Frozen input bytes and the original failure receipt remain unchanged.
Full raw inputs/answers/helpers and blinded grading remain in ignored
`.local/research-skill-eval/`; the compact
[evaluation receipt](evidence/2026-10-25-research-skills-evaluation.json) preserves
identities, scores, limitations and artifact hashes. No portable automated harness
is claimed.

## Observed correction and fresh retest

Outside the saturated rubric, coordinator inspection found the equipped diagnosis
said volatility sizing was capped at 10%, although its numerical exposure analysis
was correct. The method actually targets 10% annualized volatility with a 1x nominal
exposure cap. The canonical diagnosis procedure now explicitly separates volatility
units from allocation/exposure limits.

A fresh evaluator received only the original diagnosis task, relevant skill/procedure
and raw evidence, without the suspected problem or expected answer. Its new answer
explicitly states the 10% volatility objective and 1x cap, reproduces the metric/annual
comparisons and retains uncertainty about causal alpha. This targeted correction
passed; it does not change the initial paired scores or demonstrate general benefit.
Initial/final procedure hashes are both recorded in the receipt.

## Validation and limitations

- All nine skill-creator frontmatter/name/scaffold validations exited 0 using the
  existing isolated MLflow environment's PyYAML. No dependency installed.
- All nine canonical section links resolve. Project documentation checks passed.
- `make check` exited 0: 64 offline regression tests plus docs/dependency checks.
- No new strategy study, paid data, MLflow import, broker operation or publication
  was part of this task. Existing strategy-suite and review work was preserved.
- Existing Git base is a5a73ec9a6fd65395d40fdace7994172d1dc42f8 with earlier dirty work;
  that SHA alone does not identify current skill/package bytes. Receipt hashes do.

One evaluator per arm, the same model family, nine cases and a saturated rubric do
not establish statistical superiority, failure rates or independent financial
validation. The experiment skill was tested on invalid-cache preflight, not a
successful new-study run. Paper/live transitions and a full autonomous cycle remain
unverified. Output length was not a success criterion; the skills need to earn their
context cost through future observed task quality or reduced rework.

## Decision and next evidence

Keep the nine skills available as explicit, reusable workflow/handoff contracts.
Do not advertise a measured improvement over the already capable baseline. During
actual requested research tasks, select only the narrow skill needed, record omitted
checks/rework, and add new behavioral cases from real failures before revising it.
Evaluate proposed instruction changes on fresh cases rather than tuning only to this
fixture set. Financial effectiveness requires separately scoped experiments and
independent evaluation under the mandate; it is not inferred from skill scores.
