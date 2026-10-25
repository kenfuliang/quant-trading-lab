---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# 0003: Native saved-result reports and isolated local MLflow

User requested this reporting slice on 2026-10-25. Extend
[0002](0002-native-capabilities-first.md) without changing execution-state storage
or runtime selection. [Performance SOP](../operations/performance.md) owns commands.

Render saved SPY curves and independently audited statistics using native
`create_tearsheet_from_stats`. Preserve original evidence and financial definitions;
no strategy run or engine reconstruction is needed for this offline interface.
Use Plotly 6.9.0 for interactive HTML; omit Kaleido for this HTML-only scope.

Use MLflow 3.17.2 for local run browsing/comparison, in a separate environment.
The dependency resolver could not retain the full frozen engine package set with
modern MLflow; its unconstrained fallback selected 1.26.1, which we did not install.
Isolation preserves core dependencies. Both environments have frozen locks.

MLflow owns local SQLite tracking metadata and proxied file artifacts. It is not
an execution journal, broker state authority, live monitor or backup system.
Native HTML reports have a separate loopback-only static server. Small launch and
import scripts connect existing tools; no custom analytics dashboard is introduced.

Source/contract fingerprints identify imports. Completed runs are reused, daily
histories are not duplicated, and generated artifacts can be refreshed. Broader
strategy formats, compare eligibility and native metric recalculation remain M2 work.
Keep M1 and other roadmap gates open despite this user-requested out-of-order slice.
