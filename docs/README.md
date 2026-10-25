---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Documentation map and conventions

This file owns documentation organization and maintenance rules. Read it before
creating or changing project documentation. Dates use America/Los_Angeles;
runtime timestamps use UTC.

## Find the canonical owner

| Question | Owner |
| --- | --- |
| What works now and how do I start? | [Root README](../README.md) |
| What objective and constraints guide strategy selection? | [Goals and mandate](goals.md) |
| How do we reuse online research? | [Research intake and source registry](research-intake.md) |
| How do bounded research iterations produce evidence? | [Research development procedure](research-development.md) |
| How do we define, validate and diagnose features? | [Feature engineering](feature-engineering.md) |
| How do we score strategies and choose research directions? | [Research scoring contract](research-scoring.md) |
| What does pinned NautilusTrader already provide? | [Capability matrix](capabilities.md) |
| What contracts govern advisory collaboration? | [Advisory team and public-source review](advisory-team.md) |
| Which teams and skills exist, and how do I select/invoke them? | [Teams and skills catalog](skills.md) |
| What are we building and who owns state? | [Architecture](architecture.md) |
| What is next and what proves completion? | [Roadmap](roadmap.md) |
| How do we develop and review a change? | [Development workflow](workflow.md) |
| Where can I browse saved strategy performance? | [Performance browser SOP](operations/performance.md) |
| How do we operate the local environment? | [Local operations](operations/local.md) |
| How do we check IBKR paper connectivity? | [Paper observation](operations/paper-connection.md) |
| How do we handle uncertainty or failure? | [Incident and recovery SOP](operations/incidents.md) |
| How do we record a task or incident? | [Templates](templates/) |
| What evidence supports the capability review? | [Review receipt](tasks/2026-10-25-capability-review.md) |
| What evidence completed the working foundation? | [M0 receipt](tasks/2026-10-25-working-foundation.md) |
| Why did we choose this platform design? | [Native-capability decision](decisions/0002-native-capabilities-first.md) |
| Which catalogue strategies are defined, runnable or blocked? | [Strategy-suite protocol](../research/strategy-suite.md) |
| How are leveraged SPY simulations financed and sized? | [Leverage research model](../research/leverage-model.md) |
| What assumptions govern the SPY fixture? | [Research methodology](../research/README.md) |
| What did a particular run produce? | That run's report and manifest in `reports/` |

## Maintenance rules

- Maintain one owner for each concept; other documents link to it.
- Team rosters, skill inventories, routing and readiness belong in [the catalog](skills.md).
  Other maintained documents link there; historical receipts preserve their dated observations.
- Maintained documents under `docs/` use `status`, `updated`, and `owner`
  frontmatter. Status is `draft`, `active`, `proposed`, or `superseded`.
- `active` means the document is maintained. Capability availability is stated
  separately as implemented, unverified, blocked, or planned.
- Update freshness when substantively changing a document. Preserve historical
  dates and observations as historical evidence.
- Root README owns current capability status. Roadmap owns sequencing and
  acceptance criteria; a checked milestone needs linked evidence.
- Architecture describes the target and identifies the current implementation.
  A diagram alone never proves that a module exists.
- Decision records explain choices. Supersede a decision with a replacement link
  rather than silently rewriting its history.
- Task records are scoped work/evidence, not a competing roadmap. Store actual
  tasks in `docs/tasks/` when needed; use the template as a starting point.
- Run reports are historical evidence. Preserve them; corrections use a new
  report with a link to the original. Keep sensitive operational evidence in
  ignored `.local/` and publish only a redacted summary.
- Add links here when adding a new canonical owner. Avoid empty documents and
  speculative directory scaffolds.

Project skills under `.agents/skills/` route to these owners. They do not carry
independent copies of policy or imply permission for broker actions.
