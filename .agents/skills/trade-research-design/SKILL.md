---
name: trade-research-design
description: Specify a trading research experiment before testing, including hypotheses, controls, chronological evaluation, trial limits and rejection criteria. Use for a new study or a material change to an existing protocol.
---

# Trading research design

Read [research design](../../../docs/research-development.md#research-design)
and the [mandate](../../../docs/goals.md). For external findings, use the source
record under [research intake](../../../docs/research-intake.md); for an extension
of a saved run, inspect its protocol and manifest rather than inferring its rules
from a strategy name.

Establish the available inputs: proposed mechanism, exact trading rule, instrument
universe, data availability at decision time, baseline, evaluation history and
authorized compute/data budget. An incomplete field can remain an explicit
blocker or labeled proposal; it need not interrupt an otherwise useful design.

Produce a reviewable experiment specification:

- A falsifiable hypothesis and what observation would reject it. Separate signal
  improvement from higher exposure or a change in financing assumptions.
- A control and treatment with the intended single change. If several components
  must change together, state why and specify ablations or narrow the conclusion
  to the combined change.
- Exact decision, fill, holding and rebalance timing; eligible universe and its
  point-in-time construction; comparable capital, dividends, costs and financing.
- Metric definitions and direction, benchmark, risk constraints already agreed,
  and any proposed criteria awaiting a decision. The annual-doubling aspiration
  and approximately 30% reassessment tolerance are not automatic passing gates.
- Chronological training/validation/evaluation windows, feature and label
  information boundaries, and boundary positions/costs. Where labels or positions
  span boundaries, specify the gap or purge appropriate to their actual overlap.
- Prior exposure to each dataset, all related attempted variants, a bounded new
  trial count, and the stopping rule. Already viewed SPY history supports
  development diagnostics; relabeling a later slice does not make it untouched.

When no credible protected evaluation is available, finish a development-only
specification with that limitation and a concrete evidence acquisition condition.
Keep the evaluation decision rule fixed before viewing its outcomes; amendments
receive a new revision and preserve what had already been observed.

Return the specification, unresolved decisions, input/source references and a
ready-for-scoped-execution or blocked assessment. A consultation ends there.
Execution requires the requested experiment scope; this skill does not launch
runs, tune parameters or promote a candidate merely by producing the design.
