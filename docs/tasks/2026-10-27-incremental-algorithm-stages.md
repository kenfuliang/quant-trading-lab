---
status: active
updated: 2026-10-27
owner: research-maintainers
---

# Simplified algorithm stages and incremental acceptance

Work status: complete. User requested a simpler starting system and measurable
improvement before adopting additional stages. Scope is architecture and research
procedure documentation; no financial experiment or automatic optimizer is launched.

Canonical owners: [architecture](../architecture.md#algorithm-decision-hierarchy),
[experiment procedure](../research-development.md#incremental-stage-experiments),
[acceptance meaning](../research-scoring.md#stage-addition-acceptance).
Infrastructure [M1–M5](../roadmap.md) priority and readiness are unchanged.

## Acceptance

- [x] Two decision blocks form the starting diagram; data/controls/accounting/evaluation remain foundations.
- [x] Optional market, target and strategy-selection additions have explicit parent controls.
- [x] Adoption requires a predeclared benefit and guardrails, with no promise every candidate improves.
- [x] Failure, tradeoff and inconclusive results preserve the incumbent and all evidence.
- [x] Existing detailed component map remains a labeled reference; no new runtime integration is claimed.
- [x] Local documentation, dependency and offline behavior checks pass.

Current inputs are the maintained architecture, research lifecycle and scoring
contracts, plus existing stage experiments. Pre-edit byte snapshots are preserved
privately in `.local/incremental-stages-20261027/`. Existing frozen plans, run
manifests, datasets, failed studies and unrelated work are preserved.

Validation: `make check` exit0;372offline tests, documentation checks and
dependency integrity passed. Private check log and pre/post file identities are
in `.local/incremental-stages-20261027/`; no financial simulations, model fits,
service starts or broker operations were performed. Model definitions and the
implemented machine scoring policy are unchanged. Baseline choice, exact future rule, materiality threshold, chronology
and trial budget must be frozen in a separately scoped experiment before runs.

Canonical impact: architecture now starts with two decision blocks and retains the
expanded map as a reference; lifecycle owns incremental experiments; scoring owns
claim-specific adoption meanings. Infrastructure priorities and frozen study
results remain unchanged. Independent improvement and the integrated runtime are
unverified.
