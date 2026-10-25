---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# 0002: Configure native capabilities before adding infrastructure

Adopted 2026-10-25 after reviewing pinned NautilusTrader v1.231.0 docs, source
and installed interfaces. Supersedes [0001](0001-local-platform.md).
The [capability matrix](../capabilities.md) owns detailed findings and limits.

## Decision

Reuse native catalog, configuration, execution, risk, portfolio, run/results,
reporting, persistence and reconciliation where compatible with our current
Python TradingNode/legacy backtest path. Prove configuration and behavior before
adding replacements. Keep runtime migration a separate decision.

Withdraw the unconditional PostgreSQL-first and DuckDB architecture choice.
Native Python kernel backing selects Redis; separate PostgreSQL adapters and Rust
event-store source do not prove drop-in compatibility. Select durability storage
after capture/restart/restore evidence. SQL metadata or DuckDB may still be
justified later by a demonstrated workload.

Use native reports before extra analytics libraries. Add narrow project receipts,
comparison eligibility, health views and mandate-specific policies where native
facilities do not satisfy requirements. Preserve raw data, historical reports
and independent reconciliation evidence.

## Consequences

The roadmap begins with native configuration/catalog proof and reporting, then
persistence verification. Recovery remains required; it is not complete because
an upstream module exists. Backend compatibility on macOS is unresolved.
Native defaults are not proof of IBKR realism or leveraged/options readiness.

Revisit when a reproducible native limitation, deployment requirement or measured
workload justifies new storage, tooling or runtime migration. Record evidence and
a replacement decision rather than letting a support module redefine the roadmap.
