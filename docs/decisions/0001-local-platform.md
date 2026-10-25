---
status: superseded
updated: 2026-10-25
owner: project-maintainers
---

# 0001: Local platform and state ownership

Superseded on 2026-10-25 by [0002: Configure native capabilities first](0002-native-capabilities-first.md).
The original decision below is retained as historical rationale.

Decision adopted for project planning on 2026-10-25. Implementation state is
tracked in root README.

Use the existing Python/NautilusTrader foundation. Build a modular local platform
with PostgreSQL for transactional metadata and events, immutable Parquet for bulk
market data, and DuckDB for analysis. Keep worker and operator lifecycles separate
within one repository. Start the dashboard read-only.

PostgreSQL adds a local process and migrations, but supports worker and operator
concurrency without a later switch from an embedded operational store. File-based
historical evidence remains valid and is preserved; indexing it does not rewrite it.
DuckDB is an analytical reader, not an additional operational authority.

Reuse Nautilus execution machinery and reconcile with broker observations. Build
durable audit and run-management behavior around it instead of a competing order
state machine. Keep mode/account/feed policy explicit.

The engine choice preserves the user's local, no-QuantConnect requirement.
IBKR paper account enablement remains external. Existing SPY research is a fixed
infrastructure fixture; strategy optimization is outside the current roadmap.

Revisit through a replacement decision if deployment scale, concurrency, data
volume, or engine limitations demonstrate that these choices no longer fit.
