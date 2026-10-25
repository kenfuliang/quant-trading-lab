---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Capability review and roadmap revision

Work status: complete. Milestone: M0a in the
[roadmap](../roadmap.md). Scope requested: review pinned upstream docs, build a
capability matrix, and revise the roadmap based on native capabilities.

## Acceptance and outcome

- Matrix identifies source evidence, installed availability, verification limits,
  reuse decision and actual gap for each reviewed capability.
- Roadmap and architecture use native modules first, keep IBKR external gates,
  and withdraw speculative PostgreSQL/DuckDB prerequisites.
- Original roadmap retained as a superseded historical snapshot; original
  decision superseded by decision 0002 with a replacement link.
- No vendor/runtime/broker configuration or historical result changes.
- Offline probe, documentation check, existing project checks and doctor pass.

The [matrix](../capabilities.md) owns findings. The reviewed topic set includes
overview, concept index, architecture, getting started, configuration, data/catalog,
accounting/margin, execution, cache/message bus, streaming, event sourcing,
reconciliation, reporting/visualization, options/Greeks and IB integration. Focused
implementation and upstream test inspection resolve doc/runtime ambiguity.

## Evidence

Vendor commit: `27a8e54e7ac3c57d6cbf8891f0283dfbaee97317` (v1.231.0), clean.
Workspace branch `main` has no commits; no baseline project SHA is available.
The [offline audit JSON](evidence/2026-10-25-nautilus-capabilities.json) records
UTC time, package/platform, imported surfaces, hashes and configuration findings.
Run `.venv/bin/python scripts/audit_nautilus_capabilities.py` to refresh stdout;
preserve this dated receipt when later behavior changes.

The probe checks 18 imports and 16 matching Python source files. This is import /
configuration evidence, not a node, catalog, database, broker or strategy test.
The package-level BacktestNode export is absent while the explicit legacy node
import works. This is a recorded compatibility finding, not an unresolved failed
project check. Plotly/Kaleido are absent; PostgreSQL backing and Rust event-store
source are not wired into our current node by their mere presence.

Final verification on 2026-10-25:

- Offline capability probe: exit 0; 18 module imports passed, 16 Python source
  comparisons matched, no mismatches. No database/node construction.
- `make check`: exit 0; local doc targets/metadata passed, dependency check passed,
  all six existing fixture/configuration tests passed.
- `make doctor`: exit 0; engine 1.231.0, paper loopback port, zero execution clients.
- Vendor checkout remained clean after review.
- Final documentation-only consistency check passed after completion receipt update.

Existing engine-path `Timestamp.utcnow` deprecation warnings occurred during the
fixture tests; they did not fail checks. No package update was made. Upstream
source links in the matrix are pinned to the inspected commit; external HTTP
availability and link anchors were not validated by offline documentation checks.

## Changed owners and limitations

Canonical matrix added; roadmap, architecture, decision map, root capability status
and local backup planning corrected. New offline probe and immutable evidence
receipt support repeatable availability checks. Existing SOP authorization remains.
Original implementation, dependencies, strategy parameters and saved reports stay
unchanged. No strategy experiment, upstream integration suite, database restore or
broker connection was performed. M1 is next planned work, not started by this review.

Evidence finalized at 2026-10-25T07:19:34.477237+00:00.
Audit script SHA-256: `19ca06664431c024c8ef3177fb924511e3ad8af70e882f179a72cc36df36e656`.
