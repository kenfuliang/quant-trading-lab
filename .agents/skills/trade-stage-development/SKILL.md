---
name: trade-stage-development
description: Specify, implement or verify one trading pipeline stage within a bounded RSI cycle, including its data timing, component interface, unchanged controls and evidence handoffs.
---

# Develop one trading stage

Read [current status](../../../README.md), the [stage procedure](../../../docs/research-development.md#individual-stage-development)
and [RSI handoffs](../../../docs/operations/recursive-research.md). GRS owns cycle,
evidence and adoption rules; this skill supplies the component-development handoff.
For an existing stage, inspect its actual current implementation and parent evidence
before treating an architecture label or historical winner as the incumbent.

Resolve whether the request is contract/design work, implementation or evaluation.
Carry out the requested scope; a design-only deliverable does not start an experiment.
For engineering-only validation, use finite synthetic component checks and report
zero financial runs. A financial study needs its own qualified inputs, frozen plan
and supported runner; the current RSI coordinator has no financial adapter.

Use the [stage worksheet](../../../docs/templates/stage-development.md) inside the
existing cycle/task record. Specify decision-relevant versus evaluation-only fields,
units, availability/cutoff/execution times, warmup, missing/unknown behavior, state
and invariants. An output already aligned to the execution event must retain that
alignment; examine the producer and consumer before adding a shift or delay.
Record exact parent and proposed source identities, one changed boundary and an
unchanged upstream/downstream control. A characterization can keep the source
unchanged; it establishes interface behavior, not a strategy improvement.

Select only the relevant installed workflows from the [catalog](../../../docs/skills.md):

- Retrieve prior failures with trade-research-history; freeze the hypothesis,
  falsifier and finite bounds with trade-research-design. Use candidate evolution
  when proposing a rule change, rather than inventing one for a contract exercise.
- For feature changes use trade-feature-engineering; for data fitness use
  trade-data-audit. Prediction/label questions go to ask-ml, trading logic/timing
  to ask-algo and portfolio constraints to ask-risk. Advisers return designs;
  consultation alone does not launch agents, fitting or simulation.
- Implement through trade-infra-change and the canonical package boundaries.
  Keep financial source/evidence identities immutable; current ports receive
  new versions. Use the pinned engine interface when it already supplies the seam.
- Verify observable interface behavior, causal prefixes and failure paths. Include
  an intentionally wrong integration or rejected input when that meaningfully
  tests the contract. Keep accounting-only future fields out of decision inputs.
  A forecast score or passing unit check is not a portfolio improvement result.
- For an authorized financial comparison use trade-experiment only with the
  frozen supported runner, then diagnosis/robust evaluation and promotion review.
  Missing prerequisites yield a blocked financial handoff, not a substitute result.

Close with the stage worksheet, actual changes/checks and failures, preserved
artifacts, scoped disposition and next eligible question through research history.
A missing critical interface/timing field stops dependent work. Use GRS's existing
adoption criteria; this skill never adds a second score or grants a fresh budget.
