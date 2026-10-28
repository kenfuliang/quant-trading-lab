---
status: active
updated: 2026-10-27
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
| What is the golden pipeline and rule for research evidence, disposition and papers? | [GRS-1.0](research-standard.md); [cycle register](research-cycles.md) |
| Where are study plans, results, failures and lessons linked? | [Generated research evidence index](research-evidence-index.md); [index contract](architecture.md#research-evidence-index) |
| How do offline RSI components hand off frozen work and recover? | [RSI SOP](operations/recursive-research.md); [integration evidence and remaining checklist](tasks/2026-10-27-rsi-integration.md) |
| How do bounded research iterations produce evidence? | [Research development procedure](research-development.md) |
| How do we define, validate and diagnose features? | [Feature engineering](feature-engineering.md) |
| How do we score strategies and choose research directions? | [Research scoring contract](research-scoring.md) |
| What does pinned NautilusTrader already provide? | [Capability matrix](capabilities.md) |
| What contracts govern advisory collaboration? | [Advisory team and public-source review](advisory-team.md) |
| Which teams and skills exist, and how do I select/invoke them? | [Teams and skills catalog](skills.md) |
| What are we building and who owns state? | [Architecture](architecture.md) |
| What folder/content/report foundations have been adopted? | [Foundation adoption task and remaining checklist](tasks/2026-10-27-project-foundation-adoption.md); folder ownership remains in architecture |
| What do we own versus NautilusTrader/MLflow, and when do we modify them? | [Dependency boundaries](architecture.md#project-and-dependency-boundaries) |
| What is next and what proves completion? | [Roadmap](roadmap.md) |
| How do we develop and review a change? | [Development workflow](workflow.md) |
| Where can I browse saved strategy performance? | [Performance browser SOP](operations/performance.md) |
| How do we operate the local environment? | [Local operations](operations/local.md) |
| How do we check IBKR paper connectivity? | [Paper observation](operations/paper-connection.md) |
| How do we restore closed research evidence bundles? | [Evidence recovery SOP](operations/evidence-recovery.md); [scoped real-bundle drill](tasks/2026-10-27-evidence-recovery.md) |
| How do we handle uncertainty or failure? | [Incident and recovery SOP](operations/incidents.md) |
| How do we record a task or incident? | [Templates](templates/) |
| What evidence supports the capability review? | [Review receipt](tasks/2026-10-25-capability-review.md) |
| What evidence completed the working foundation? | [M0 receipt](tasks/2026-10-25-working-foundation.md) |
| Why did we choose this platform design? | [Native-capability decision](decisions/0002-native-capabilities-first.md) |
| Which catalogue strategies are defined, runnable or blocked? | [Strategy-suite protocol](https://github.com/kenfuliang/quant-trading-lab/blob/4586095846c63abf2e0b90dc547654256c3fc45e/research/strategy-suite.md) |
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

## Content structure

For new narrative documents use: purpose/outcome → scope and status → governing
owner → inputs/contracts → method or steps → actual evidence and counterevidence
→ decision/limitations → lesson and next action. Omit inapplicable sections.
Frozen schemas and historical records keep their existing identities and layout.

Keep these dimensions separate:

| Dimension | Meaning |
| --- | --- |
| Document maintenance | Frontmatter status, update date and owner; `active` means maintained |
| Work/cycle state | Actual planned, attempted, blocked, failed or completed work under its contract |
| Evidence classification | GRS development technical report, independently validated research report or negative-results technical report; synthetic engineering explicit |
| Capability/metric availability | Implemented/unverified/blocked/planned capabilities; metric value with units, or missing/undefined/not-applicable/incomparable with reason |

Tasks pair a dated Markdown record with a compact JSON receipt in
`docs/tasks/evidence/`. Plans and raw artifacts retain their named original
locations. Use exact parent/cycle/run references, code/data/environment identity,
UTC runtime times and artifact hashes. The cycle register is an index; browser
pages and MLflow are views, not additional authoritative result stores.

## Choose a report template

| Work product | Template | Role |
| --- | --- | --- |
| Infrastructure change | [Task](templates/task.md) | Scope, acceptance, failure/recovery and actual verification |
| External idea/source | [Research intake](templates/research-intake.md) | Mechanism, provenance, source/data rights and reproduction gaps |
| Research study | [Cycle](templates/research-cycle.md) | Frozen question, controls/budget, every attempt and lesson |
| Operational failure | [Incident](templates/incident.md) | Containment, evidence, reconciliation and recovery |
| Short saved-result comparison | [Decision brief](templates/research-decision.md) | Derived summary of context, results, failures and disposition |
| Substantial research lesson | [Experience paper](templates/research-paper.md) | Scientific narrative only when GRS report-readiness criteria are met |

Templates provide presentation prompts; GRS, scientific procedure and scoring
retain their existing authority. A populated template is not an independent audit
or readiness decision. Link complete annual/temporal tables rather than omit
unfavorable observations to fit a short brief.
