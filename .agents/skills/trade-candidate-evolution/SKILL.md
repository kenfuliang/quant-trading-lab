---
name: trade-candidate-evolution
description: Propose bounded, evidence-driven changes to a trading candidate after diagnosis, including controls, expected failure modes and experiment accounting. Use to plan the next research iteration, not to optimize historical scores automatically.
---

# Trading candidate evolution

Read [candidate evolution](../../../docs/research-development.md#candidate-evolution),
the [mandate](../../../docs/goals.md), the candidate's exact rule and the relevant
diagnosis and trial history. For a published idea, retain the source/adaptation
distinction established by [research intake](../../../docs/research-intake.md).

Start from a documented weakness or opportunity. If none is supported, identify
the diagnostic needed to decide what to change; avoid inventing a defect from a
low leaderboard rank. A valid outcome is to retain the baseline or stop studying
the candidate.

For each proposed change, give:

- The mechanism and cited observation motivating it; separate an accounting
  fact from a hypothesis about future behavior.
- A precise rule delta to the baseline, anticipated benefit, and a falsifier.
  Include the likely cost: missed recoveries, slower response, turnover, reduced
  diversification, data burden or operational complexity as applicable.
- An unchanged control and one-change rationale. For inseparable components,
  identify ablations or state that only the joint treatment can be evaluated.
- Required free/local inputs and implementation support. New assets require
  verified universe/calendar/corporate-action handling; options, futures and
  shorts need their own contract, financing and execution models. Substitute
  price proxies only as explicitly labeled exploratory studies.
- A bounded trial proposal, prior related attempts, parameter neighborhoods
  justified without viewing protected outcomes, and a stopping criterion.

Rank proposals by information gained relative to complexity and evidence cost,
not their ability to repair a known historical loss. Distinguish prediction,
selection, sizing, portfolio combination and execution changes; higher leverage
alone changes risk rather than proving a stronger signal.

Carry every attempted variant, failure and observed evaluation period forward.
If earlier test outcomes informed this proposal, treat them as development
evidence and identify what independent evaluation remains. Never erase a failed
trial or rename a consumed holdout to restore apparent independence.

Deliver a bounded candidate proposal and its next experiment specification or
design gaps. Stop after that deliverable unless implementation/execution was
explicitly included in the request. When it was included, preserve the proposal
before execution and use the declared budget; exhausted trials trigger a recorded
decision rather than an unbounded search for a passing score.
