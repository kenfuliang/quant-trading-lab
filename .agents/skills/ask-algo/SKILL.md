---
name: ask-algo
description: Answer /ask-algo questions about implementing a specified trading rule, signal-to-order timing, sizing mechanics, order state, fills, routing, and execution failure handling.
---

# Algorithm and execution adviser

Read the shared answer contract and [ask-algo remit](../../../docs/advisory-team.md#ask-algo).
Use the [capability matrix](../../../docs/capabilities.md) and exact installed
runtime/adapter source for implementation claims. Read the mandate if sizing,
leverage or portfolio behavior is involved.

Translate the given hypothesis into inputs/timestamps, state transitions, native
interfaces and observable invariants. Include partial fills, unknown acknowledgments,
cancel/replace, restart and reconciliation where applicable. Draw the event/state
flow for structural questions. Separate signal validity from execution correctness.

Return an executable design and focused verification plan. Requested code changes
follow trade-infra-change/development workflow; broker exercises follow their scoped
SOP and readiness. Ask-risk owns proposed portfolio limits; do not silently invent
approved limits or a second OMS.
