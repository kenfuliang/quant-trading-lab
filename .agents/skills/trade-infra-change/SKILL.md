---
name: trade-infra-change
description: Implement infrastructure changes in this local NautilusTrader project, including data catalog, run records, journal, monitoring, and recovery behavior.
---

# Trading infrastructure change

Find the repository root containing `paper_trading/` and `docs/README.md`.
Read root README for capability status, then `docs/workflow.md` and the affected
module in `docs/architecture.md`. Before proposing new infrastructure, read
`docs/capabilities.md` and prefer compatible native facilities. Use `docs/roadmap.md`
to identify acceptance.
Before documentation changes, read `docs/README.md`.

Follow the development workflow through its completion criteria. Prefer one usable
slice with an observable failure/recovery case. Use fixed fixtures to verify
infrastructure; strategy tuning requires its own research request. Preserve raw
inputs and historical reports.

For migration or journal changes, include duplicate/restart behavior and durable
evidence. For broker behavior, use a fake adapter in offline verification and route
external checks through the matching broker SOP (`docs/operations/paper-connection.md`
for IBKR, `docs/operations/alpaca-paper.md` for Alpaca). Dataset acquisition
uses trade-data-acquisition; saved-input fitness uses trade-data-audit. An
infrastructure change does not implicitly execute either workflow.

Finish with changed paths, actual validation results, canonical documentation
impact, remaining limitations, and next action. A proposed module is not an
implemented capability; update root status only with evidence.
