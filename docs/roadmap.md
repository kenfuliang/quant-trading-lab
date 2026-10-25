---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Infrastructure roadmap

This file owns priority, sequence, dependencies and acceptance. Root README owns
current capability status. The [capability matrix](capabilities.md) supplies the
reuse evidence; [architecture](architecture.md) owns module responsibilities.

## Sequence

```mermaid
flowchart LR
    A[Capability review] --> B[M1 Native configuration and catalog proof]
    B --> C[M2 Native reports and thin comparison]
    C --> D[M3 Persistence and recovery proof]
    D --> E[M4 Operational visibility]
    E --> F[M5 Risk policies and paper execution]
    P[IBKR access and permissions] --> F
```

All milestones are owned by project-maintainers; the user owns account access and
investment-policy choices. Milestones specify order rather than committed calendar
dates. No new platform implementation starts as part of this documentation review.

| Milestone | Deliverable and native reuse | Acceptance evidence | Status / dependencies |
| --- | --- | --- | --- |
| M0 Working foundation | Workflow, documentation ownership, SOPs, skills, local checks | [Original completion receipt](tasks/2026-10-25-working-foundation.md) | Complete; later design revisions do not invalidate that historical receipt |
| M0a Capability review | Source-backed matrix; distinguish installed interfaces, configuration and runtime proof | [Review receipt](tasks/2026-10-25-capability-review.md) and offline interface probe | Complete for the scoped review, not operational validation |
| M1 Native configuration and catalog baseline | Existing TradingNodeConfig, native logging/status and ParquetDataCatalog; explicit mode validation and input receipts | Fixture catalog write/read preserves values/timestamps/instrument identity; duplicate/invalid-input behavior documented and verified; config serialization round-trip; invalid/mismatched modes fail before connection | Planned; next work packet; C01–C04, C21 |
| M2 Native reports and thin comparison | PortfolioAnalyzer, ReportProvider, tearsheets and native result/run IDs; small saved-run index | Locked visualization dependencies verified separately; saved fixture native report reconciled against its account/return policy; two saved runs compare with matched periods/capital/costs; mismatches visibly flagged | Partial: [saved-SPY reporting slice](tasks/2026-10-25-local-performance-browser.md) explicitly requested before M1; general importer/compatibility and native metric recalculation remain planned; C04, C16–C18 |
| M3 Persistence, capture and recovery | Prove current-node cache/streaming/state facilities; select backend from behavior evidence; reuse reconciliation | Written backend decision; disposable write/restart/restore exercise; captured message coverage and crash-loss window measured; restore to separate location; no blind resubmission under unknown outcomes | Planned after M2; C09–C15; Mac/backend compatibility is an open technical risk |
| M4 Operational visibility | Native logs/status and selected persistence outputs; read-only freshness/health and incident views where missing | Dead worker, stale/missing feed, capture failure and unresolved state visible; private account data redacted; source timestamps and mode shown | Planned after M3; C21; no custom chart suite assumed |
| M5 Mandate-specific risk and paper operation | Native risk states/limits and IB execution/reconciliation; missing portfolio policies | Offline fixtures cover risk rejection, duplicates, partial fills, disconnect after submit, restart, mode/account errors; supervised IBKR paper evidence verifies bounded operation | Planned after M3/M4; C06–C08, C14, C19–C20; external verification blocked pending IBKR access and selected data permissions |

M1–M4 and offline M5 fixtures do not require IBKR access. Integration milestones
stay incomplete while required external evidence is missing. Live deployment
needs a separately scoped readiness decision; paper success is not profitability proof.

## What changed and why

The [initial roadmap](history/2026-10-25-initial-roadmap.md) assumed PostgreSQL
startup/migrations first, followed by a general catalog and event registry. Source
review found native catalog, run/results, risk, persistence, streaming, reports and
reconciliation facilities. The replacement [decision](decisions/0002-native-capabilities-first.md)
removes an unconditional database choice and puts proof of native behavior first.

- M1 now proves native configuration/catalog behavior, rather than a new SQL store.
- M2 brings native reporting and a minimal cross-run comparison forward. The user
  subsequently requested local MLflow plus native reports using saved SPY results;
  this delivered slice does not complete all M2 acceptance or execution persistence.
- M3 scopes durability around actual capture/recovery gaps. It does not preselect
  PostgreSQL, a custom journal, or a runtime migration.
- M4 focuses on operational health. Custom charts wait for a demonstrated native gap.
- M5 reuses execution/risk/reconciliation without building another OMS.
- DuckDB, QuantStats, additional frameworks and an always-on SQL run registry are
  deferred until a requirement justifies their maintenance cost.

## Next work packet: M1

Create a scoped offline baseline task using the current pinned legacy interfaces.
Validate explicit modes before connection. Round-trip a small synthetic market-data
fixture through a temporary native catalog and record actual duplicate/invalid-input
semantics. Keep raw source bytes separate from normalized catalog data and attach
provenance/quality receipts. Verify config serialization and preserve observer commands.

This is a framework behavior task, not a strategy experiment. Do not install a
database or migrate runtimes to complete it. Record implementation/data identity,
commands and exits; update matrix verification only for behavior actually exercised.

## Goal and research planning lane

[Goals](goals.md) owns investment constraints and unresolved decisions;
[research intake](research-intake.md) owns screening external findings. Existing
public-repository entries remain unverified candidates. These inform later data,
risk and instrument requirements without replacing infrastructure priority.

Before leveraged/options execution, resolve portfolio risk budgets, instrument
permissions, margin/assignment behavior and feed policy. Validate native models
against the intended broker behavior.

## Later scope

Hosted deployment, multi-user access, broad parameter search, machine-learning
platform adoption and live-money operation remain future scope. Expand after an
observed need and verified foundations establish the case.
