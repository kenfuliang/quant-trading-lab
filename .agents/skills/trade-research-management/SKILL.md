---
name: trade-research-management
description: Reconcile research work across owners, dependencies, budgets, results and lessons; close completed cycles into the canonical tagged leaderboard with evidence, failures and lessons.
---

# Research management

Read [management handoff](../../../docs/operations/recursive-research.md#research-management),
[documentation conventions](../../../docs/README.md) and the
[catalog](../../../docs/skills.md). GRS owns scientific acceptance; roadmap owns
priority; original plans, journals and receipts own execution truth.

1. Name the requested program and exact evidence root. Retrieve prior work through
   trade-research-history. Freeze the review scope, expected work IDs, owners,
   source identities and verification budget before assessing the submissions.
2. Use the [management template](../../../docs/templates/research-management.md)
   to link each work item to its contract, reservations, all outputs, failures and
   lesson. Reconcile limits against actual reservations, including unsuccessful
   starts; elapsed deadlines do not create a new allowance.
3. Where compatible, run the read-only [inventory helper](../../../scripts/current/research_management.py)
   on a caller-declared manifest. Report unsupported evidence formats explicitly;
   hash equality proves identity, not completeness or scientific validity.
4. Distinguish component completion, verified evidence, integration readiness,
   financial evidence and operational readiness. Preserve dissent and adverse
   findings. Route scientific disputes to trade-robust-evaluation and disposition
   to trade-promotion-review; use ask-director for priority conflicts.
5. Close with an evidence-linked work table, missing/failed evidence, dependencies,
   budget usage, lessons and one finite next-task proposal. Record through
   trade-research-history and refresh existing navigation, retaining original files.
6. Reconcile every completed cycle with the existing `docs/leaderboard.md` in its
   owning research checkout under the [leaderboard closure contract](../../../docs/operations/recursive-research.md#leaderboard-closure-contract).
   Upsert tagged, evidence-linked outcomes and lessons in its one table; include
   failed/blocked/inconclusive and synthetic outcomes as appropriate unranked rows.
   Bind the change or verified no-change to the closure receipt; preserve original
   evidence. An unavailable owner is an explicit reconciliation blocker, not a
   reason to create another leaderboard or reopen a closed experiment.

Completion requires accounting for every expected submission, or explicitly naming
its absence. Avoid opening a competing portfolio roadmap or result store. Requested
management updates may write their scoped records; dispatch, new experiments,
services, broker actions and publication require their own task authorization.
This skill supplies instructions and read-only reconciliation, not a scheduler.
