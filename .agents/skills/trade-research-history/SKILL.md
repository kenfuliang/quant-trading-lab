---
name: trade-research-history
description: Record or retrieve this project's research hypotheses, attempted variants, results and decisions while preserving failed evidence, historical receipts and evaluation-data exposure history.
---

# Maintain project research history

Read [research-history policy](../../../docs/research-development.md#research-history)
and [documentation conventions](../../../docs/README.md). Use this for the
project's files and experiment evidence. This skill is not authorization to edit
the user's personal Codex memory folder or install persistent personal memories;
those writes require an explicit direct request from the user.

Search narrowly with `rg` through `docs/tasks/`, `research/` and the relevant run
manifests before creating a record. `docs/goals.md` owns the mandate; methodology
documents own rules; dated reports/manifests own observed results; MLflow is a
comparison view, not replacement evidence. Do not create a competing roadmap or
copy policies into a new experiment diary.

For substantive work, use `docs/templates/task.md` and dated records under
`docs/tasks/`; store compact machine-readable evidence under its `evidence/`
folder when useful. Link bulk raw run artifacts in their existing locations.
Record:

- Question/hypothesis and parent record, frozen plan identity and why each change
  was proposed; distinguish predefined rules from changes made after inspection.
- All attempted variants, including rejected, failed, abandoned and inconclusive
  cases; report unknown historical trial counts rather than treating them as zero.
- Input/code/config identities, commands/exits and manifest/artifact references;
  distinguish upstream claims, reproduced measurements and interpretation.
- What evaluation results were inspected, by which development cycle, and how
  that influenced subsequent decisions. Reusing viewed data does not reset its
  independence; incomplete exposure history must remain visible.
- Decision, supporting and contradictory evidence, unresolved limitations and
  next acceptance condition. Absence of a successful run is not a negative return.

Preserve original failures and receipts. Correct history with a new dated
superseding record linking the original and explaining the correction; do not
rewrite historical evidence, erase losing trials or summarize away raw artifacts.
Update a maintained index only to point to authoritative records and their status.
Exclude credentials/account identifiers from tracked records; keep sensitive raw
output in ignored local storage with a redacted reference.

Finish by checking referenced artifacts and document links, and return the new or
retrieved record paths, evidence status and gaps. The bounded local decision journal
in `research/research_controller.py` supports frozen context, reserve/record,
idempotent resumption and explicit branch status; see the
[pilot review](https://github.com/kenfuliang/quant-trading-lab/blob/4586095846c63abf2e0b90dc547654256c3fc45e/docs/tasks/2026-10-25-recursive-research-review.md) for proof
and caller-verification limits. It cannot detect missing historical trials or
authenticate evidence truth. Preserve prior context versions; enumerate actual
receipts and disclose incomplete history instead of inferring completeness from MLflow.

For new-cycle closure, use the [versioned receipt contract](../../../docs/research-standard.md#experiment-receipt-contract)
and [management handoff](../../../docs/operations/recursive-research.md#research-management).
Record validation outcome and single-leaderboard disposition; preserve older
receipts rather than retroactively inserting unavailable identities.
