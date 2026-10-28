---
status: active
updated: 2026-10-27
owner: research-maintainers
---

# Stage development worksheet

Use inside the existing task/cycle under the
[stage procedure](../research-development.md#individual-stage-development).
This worksheet supplies interface detail, not another cycle schema or adoption rule.
Replace each instruction below with the actual fact or an explicit unavailable item.

| Field | Required content |
| --- | --- |
| Identity and scope | Stage ID, current source/function and hash, exact parent/version/evidence; design, implementation or characterization |
| One change and controls | Proposed delta or unchanged policy; upstream/downstream boundaries held fixed; hypothesis, falsifier and GRS cycle/plan reference |
| Inputs | Field meanings/units, source identity, valid ordering, availability/as-of cutoff; qualify provenance and actual data access |
| Outputs | Field meanings/units/bounds, execution alignment; distinguish decisions from evaluation-only fields |
| State and exceptional behavior | Initial state, warmup, unknown/missing inputs, supported reset/replay/restart and required stop behavior |
| Verification | Predeclared finite cases/resource/time bounds, interface and causality invariants, unchanged baseline, negative control, preservation checks |
| Actual evidence | Commands/exits, all attempted checks/failures, hashes/locations; distinguish synthetic checks from financial launches |
| Disposition and next handoff | Unchanged/blocked/provisional/eligible decision under GRS, unresolved prerequisites and next bounded question |

If an item is inapplicable, state why. Missing critical timing, identity or eligibility
stops dependent execution; writing a completed worksheet does not grant permission
to simulate, fit, launch agents or trade.
