---
status: superseded
updated: 2026-10-25
owner: project-maintainers
---

# Initial infrastructure roadmap (historical snapshot)

Superseded by the [capability-led roadmap](../roadmap.md) on 2026-10-25.
This snapshot records the earlier plan; it does not define current priorities.

This file owns delivery sequence and milestone acceptance. Root README owns
observed capability status. Each milestone needs linked verification evidence
before completion. Infrastructure is the active priority; research uses fixed
fixtures to verify the platform.

| Milestone | Deliverable | Acceptance evidence | Status |
| --- | --- | --- | --- |
| M0 Working foundation | Doc ownership, workflow, SOPs, project skills, repeatable local checks | Links resolve, skills validate, offline checks pass | Complete: [evidence](../tasks/2026-10-25-working-foundation.md) |
| M1 Local runtime | Packaged configuration, explicit modes, PostgreSQL startup, migrations, health checks | Fresh disposable setup works; invalid config fails before connection; secrets stay outside logs | Planned |
| M2 Data catalog | Versioned ingestion and Parquet publication with quality receipts | Repeat import deduplicates; bad data is isolated; exact source bytes and transformation version trace to output | Planned |
| M3 Run registry and journal | Durable run lifecycle, event append/dedup, artifact indexing | Forced worker crash leaves inspectable state; restart does not duplicate accepted events; identified inputs reproduce a fixture | Planned |
| M4 Operations visibility | Read-only dashboard, health/freshness checks, backup and restoration | Worker failure and stale data become visible; fresh-location restore recovers catalog, journal, and artifact references | Planned |
| M5 Paper execution | Bounded execution, risk checks, reconciliation, recovery controls | Fake broker covers partial fills, rejects, duplicate events, disconnect after submit, restart; supervised IBKR paper evidence then confirms integration | Planned; external verification depends on IBKR access |

M0 completion means this operating foundation exists, not that the target platform
has shipped. M1–M4 can proceed without broker access. Fake broker testing in M5
can also proceed independently; external verification cannot.

## Goal and research planning lane

[Goals](../goals.md) records USD 300,000 scenario capital, a one-year horizon, and
about 30% drawdown as the user reassessment tolerance. Remaining mandate decisions
must be resolved before selecting strategies. [Research intake](../research-intake.md)
owns source screening; three initial candidate references are cataloged but have
not been reproduced or adopted. This lane informs later data/execution requirements
without replacing M1 or initiating strategy experiments.

## Next work packet: M1

Create one local runtime slice: explicit mode/configuration validation, local-only
PostgreSQL startup with persistent storage, an initial migration, and a health
command. Keep existing observer commands compatible. Record a startup/teardown
receipt and dependency checks in a task. Use disposable storage to verify fresh
startup and migration; retain local operational storage on ordinary stop.

Define database schema when implementing its real first use. M1 establishes
migration plumbing; M2 and M3 introduce catalog and journal schemas respectively.

## Later scope

Live-money execution needs a separately scoped readiness decision and verified
paper-operation evidence. Hosted deployment, multi-user access, high-frequency
infrastructure, and strategy/model optimization are future scope, sequenced when
an actual requirement justifies them.
