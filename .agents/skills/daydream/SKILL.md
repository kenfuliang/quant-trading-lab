---
name: daydream
description: Rehearse concrete future workflows to expose plausible failure modes, hidden assumptions and cross-system mismatches. Use for daydreaming, premortems, what-could-go-wrong reviews, or challenging design reliability before declaring readiness. Covers specs as well as implementations; use ordinary code review for a diff or debugging for a reproduced runtime fault.
---

# Daydream

Mentally operate the proposed system through time, then challenge the story with evidence. Produce grounded scenarios that change confidence or identify a missing proof. Finding many issues is not the objective; supported findings and honest uncertainty are.

## Frame the pass

Read the user's requested mode, current artifact/baseline, canonical owners and accepted decisions. Choose a bounded workflow and state what evidence exists: proposal, declaration, code, executed test or observed operation. A general reliability question also needs this distinction; do not answer it from architectural principles alone.

Discussion/review is read-only. Preserve that mode: findings and implications, with fixes only if requested. Running operations, changing specs, implementation, deployment and sending messages need their applicable authorization. Missing runtime evidence does not authorize building the application.

## Rehearse, then challenge

```text
Concrete goal + starting state → actions over time → state at each seam
                               → plausible failure → check against owners
                               → defect / covered risk / unknown / tradeoff
```

1. **Operate it.** Pick a representative task and real or explicitly synthetic values. Trace the actor's intent through UI, typed request, server decision, persistence, response and later readback where applicable. Track stable identity, scope, revision, quantities/money and ownership across those seams. End at an observable outcome; a list of components is not a walkthrough.
2. **Perturb the story.** Choose the pressure most likely to expose a mismatch: changed context, stale response, concurrent use, partial failure, lost response, retry, reversal, restore, awkward viewport or future maintenance. Follow the resulting sequence concretely. Include an ordinary shortcut a competent implementer could plausibly take; state which contract that shortcut would violate rather than assuming it is implemented.
3. **Try to disprove the concern.** Inspect the specific rule, declaration, implementation or test that could prevent it. Explain what that evidence proves and where its protection ends. Read a relevant image when a finding depends on its pixels. A named guard is evidence of intent; its declaration alone does not prove runtime execution. Existing safeguards change classification, not the underlying requirement for proof.
4. **Check the assumptions.** Separate observed source behavior from adopted replacement rules and example-specific values. Ask whether the test oracle is independent, whether a snapshot reserves anything, and whether matching IDs/types imply the right business target. Select only relevant questions; do not manufacture unknowns already settled by evidence or the user.

For an unbuilt system, report a conditional implementation hazard, not an observed bug. When code or documents contradict a contract, identify the precise conflict even if no runtime reproduction is available. Simulations are reasoning aids, not LY/native behavior evidence or executed test results.

## Classify and report

Use a short table or equivalent prose. Each material item needs a concrete trigger/sequence, consequence, owner/evidence locator and next proof needed. Distinguish severity of the consequence from certainty that the failure exists.

| Classification | Evidence threshold |
|---|---|
| Concrete defect | Actual artifacts conflict, or an observed/reproduced result violates the owner contract. State static contradiction versus runtime reproduction. |
| Covered but unproven risk | Owner already defines prevention/acceptance, but applicable execution evidence is absent. Link the existing task; this is not a newly missing policy. |
| Uncovered hazard | Plausible causal sequence has no located control or accepted boundary after checking relevant owners. State search scope and affected operation; absence of a search hit is not proof of universal absence. |
| Unknown behavior | Evidence cannot establish the intended result; name the missing fact and the operation it affects. Preserve adopted defaults and gate only the dependent branch. |
| Accepted tradeoff | Existing scope/decision intentionally permits or defers the behavior. Explain impact without silently reopening it. |

Do not turn every hypothetical into a blocker. Derive importance from the actual stock/money/data/access/task consequence; do not rank by novelty, reviewer confidence, issue count or visual score. Exact parity and operational correctness are separate claims.

If fresh reviewers are requested or authorized, give distinct perspectives the raw scoped artifacts and neutral question, without the author's intended findings. Consolidate duplicates and disagreements by evidence; agreement is not ground truth. If the author reviews alone, say so when independence matters.

## Stop and calibrate

Finish when the selected workflow and its most consequential perturbations have evidence-backed dispositions, with unresolved uncertainty explicit. There is no issue quota and no exhaustive-scenario or zero-future-defect claim. Stop after one bounded pass; reopen for changed evidence/scope or a concrete counterexample, not another opinion or score.

End with what is established, the strongest remaining failure possibility, and what cannot yet be known. Use readiness language only at the demonstrated stage: specified, statically checked, or runtime verified. If a concern is already covered, retain its unproven status instead of either calling it fixed or inventing another task. Return artifacts to existing owners; create no parallel tracker or automatic review loop.
