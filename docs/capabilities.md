---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# NautilusTrader capability matrix

This is the canonical capability/reuse assessment for our pinned dependency, not a
claim that the project operates every upstream feature. Root [README](../README.md)
owns current project status; [roadmap](roadmap.md) owns delivery sequence.

## Version and evidence rules

Reviewed upstream tag **v1.231.0**, commit
`27a8e54e7ac3c57d6cbf8891f0283dfbaee97317`, with a clean vendor checkout.
Installed package is 1.231.0, Python 3.12 on macOS ARM64. The repository contains
legacy Python/Cython and Rust/PyO3 surfaces together. Tagged documentation includes
both; version pinning alone does not make every example compatible with our node.

Our current observer uses `nautilus_trader.live.node.TradingNode`; the SPY fixture
uses the legacy `BacktestEngine`. Keep those interfaces explicit. This review does
not migrate runtimes or install extras.

Evidence levels:

- **Source:** pinned documentation and implementation inspected.
- **Import/config:** module/symbol availability and configuration inspected offline.
- **Behavior:** a particular behavior exercised; existing project tests cover only
  the limited fixtures recorded in their reports. Source inspection is not behavior evidence.
- **External:** actual database/broker integration exercised. None added in this review.

Reproducible probe: `.venv/bin/python scripts/audit_nautilus_capabilities.py`.
The [recorded JSON](tasks/evidence/2026-10-25-nautilus-capabilities.json) contains
module hashes, installed/source matches, imports, optional dependencies, and observer
settings. Missing symbols are findings, not failed financial or operational tests.

## Matrix

| ID / need | What upstream supplies and source | Current availability / verification | Decision and remaining gap |
| --- | --- | --- | --- |
| C01 Runtime composition | Kernel, message bus, data/risk/execution engines; [architecture](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/concepts/architecture.md), [kernel](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/nautilus_trader/system/kernel.py) | Legacy `TradingNode` import passes; our observation configuration exists. No successful IB session recorded | **Configure/reuse.** Add explicit project modes and health receipts around native config, not another engine framework |
| C02 Data types and ingestion | Instruments, ticks/bars/books, wranglers and custom data; [data guide](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/concepts/data/index.md) | SPY fixture converts data locally; general ingestion not verified | **Reuse/extend.** Provider provenance, quality checks, calendar/adjustment policies and source licenses remain our responsibility |
| C03 Historical catalog | `ParquetDataCatalog` write/query/consolidation facilities; [implementation](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/nautilus_trader/persistence/catalog/parquet.py) | Module/class import passes; no catalog round-trip performed in this audit | **Configure.** Verify round-trip, coverage/duplicates and source receipts before adding catalog tooling; no replacement Parquet query engine |
| C04 Simulation and run configuration | `BacktestEngine`, catalog-backed `BacktestNode`, run config identity; [run guide](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/concepts/backtesting/apis-and-runs.md), [legacy node](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/nautilus_trader/backtest/node.py) | `backtest.node.BacktestNode` imports, `BacktestRunConfig.id` exists. `from nautilus_trader.backtest import BacktestNode` is unavailable locally | **Reuse.** Verify exact legacy entrypoints; add only cross-run code/data/config identity and discoverability missing from native results |
| C05 Fill/cost/latency models | Configurable fill, fee, latency and margin simulation; [fill models](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/concepts/backtesting/fill-models.md), [account/margin guide](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/concepts/backtesting/accounts-and-margin.md) | Existing fixture uses explicit illustrative fills/costs; broader models source-reviewed only | **Configure/validate.** Defaults are not IBKR execution realism; realistic inputs/assumptions must be demonstrated separately |
| C06 Execution/order lifecycle | Commands, order/position state, fills, execution algorithms; [execution](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/concepts/execution.md) | Existing synthetic fixture exercises a limited order path; observer has zero execution clients | **Reuse.** Do not build a competing OMS or independent order state authority |
| C07 Pre-trade risk controls | Validation, rate limits, notional cap; ACTIVE/REDUCING/HALTED states; [config](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/nautilus_trader/risk/config.py), [engine](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/nautilus_trader/risk/engine.pyx) | Config import/fields verified. Project-specific limits and halted/reducing behavior not exercised | **Configure/extend.** Reuse native gates; add mandate-specific portfolio drawdown, leverage, feed/account policy only where absent |
| C08 Balances, PnL and margin | Cash/margin accounts, portfolio and margin models; [accounting](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/concepts/accounting.md) | Cash fixture reconciled historically; margin/live portfolio behavior unverified | **Reuse/validate.** Broker margin and liquidation behavior are not established by a generic simulation model |
| C09 Cache persistence | Configurable database backing; [cache config](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/nautilus_trader/cache/config.py), [kernel wiring](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/nautilus_trader/system/kernel.py) | Current Python kernel accepts Redis or no backing; observer backing is disabled. No database connection tested | **Configure after proof.** Verify native backend on our deployment platform before custom state storage |
| C10 PostgreSQL cache | Postgres adapter/PyO3 class and integration tests; [adapter](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/nautilus_trader/cache/adapter.py), [tests](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/tests/integration_tests/infrastructure/test_cache_database_postgres.py) | Adapter and PyO3 symbol import; standard Python kernel does not wire Postgres. Upstream integration tests skip non-Linux; no Mac connectivity/restore proof | **Defer/resolve compatibility.** Presence is not drop-in support; do not start a Postgres-based replacement on this evidence |
| C11 Data/event streaming | `StreamingConfig`, `StreamingFeatherWriter`, config snapshot and writer subscription; [config](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/nautilus_trader/persistence/config.py), [kernel](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/nautilus_trader/system/kernel.py) | Config import passes; observer streaming is disabled | **Configure/validate.** Verify captured types, flush/crash loss and replay coverage. Feather streaming is distinct from historical Parquet and a complete durable journal |
| C12 External message bus | Redis stream backing and serialization options; [message bus](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/concepts/message_bus.md), [kernel](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/nautilus_trader/system/kernel.py) | Source-reviewed; observer has no external backing; no Redis test | **Defer until needed.** Native extension route for external consumers; retention/delivery and operational behavior need verification |
| C13 Durable event store | Rust-native capture/replay/recovery design; [event sourcing](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/concepts/event_sourcing.md) | No `event_store` field on current `TradingNodeConfig`; no `EventStoreConfig` PyO3 export in installed wheel. Not wired into current legacy node | **Defer runtime adoption.** Determine exact compatibility and required capture coverage before building or adopting a journal |
| C14 Recovery/reconciliation | Startup, in-flight checks and optional continuous order/position polling; [reconciliation](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/concepts/reconciliation.md), [config](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/nautilus_trader/live/config.py) | Startup reconciliation defaults true; some periodic checks default unset. Observer has no execution client, so these are not broker-verified | **Configure/verify.** Native reconciliation first; fault fixtures and later paper evidence remain necessary |
| C15 Component state | Native `load_state`/`save_state` and lifecycle handling; [kernel config](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/nautilus_trader/system/config.py) | Both disabled in observer; no restart/restore test | **Configure selectively.** Distinguish strategy state, execution cache and event history; graceful saving alone is not crash recovery |
| C16 Metrics and tabular reports | `PortfolioAnalyzer`, `ReportProvider`, benchmark-relative stats; [reports](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/concepts/reports.md), [analyzer](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/nautilus_trader/analysis/analyzer.py) | Modules import. Existing SPY reporting is custom and separately audited, not evidence native metrics match its dividend/cash policy | **Reuse/validate.** Reconcile inputs/metric definitions before replacing custom calculations; preserve historical reports |
| C17 Interactive reporting | Plotly tearsheets, custom charts/themes, optional static export; [visualization](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/concepts/visualization.md), [implementation](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/nautilus_trader/analysis/tearsheet.py) | Plotly 6.9.0 installed; two saved-SPY HTML reports rendered and inspected; Kaleido absent, static export untested | **Configure extras later.** Use native reports before introducing QuantStats or building charting |
| C18 Strategy comparison | Native run IDs/results, benchmark overlay and metrics; [result structure](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/nautilus_trader/backtest/results.py), [tearsheet](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/nautilus_trader/analysis/tearsheet.py) | Local MLflow 3.17.2 compares two saved SPY portfolios; input validation and repeat import verified for this format; general ingestion unimplemented | **Extend narrowly.** Thin run index/comparison table with consistent capital, dates, costs and evidence labels; not a new analytics engine |
| C19 IBKR market data/execution | Instrument discovery, data client, execution client and status reports; [IB guide](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/integrations/ib.md), [execution](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/nautilus_trader/adapters/interactive_brokers/execution.py) | Imports/config available. Current observer requests delayed/frozen data; broker login/quote/execution success unverified | **Configure/verify.** Keep paper identity gate; paper access/entitlements external dependencies |
| C20 Options and Greeks | OptionContract/OptionSpread, GreeksCalculator, IB BAG contracts and exercise-position tracking option; [options](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/concepts/options.md), [Greeks](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/concepts/greeks.md), [IB config](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/nautilus_trader/adapters/interactive_brokers/config.py) | Types/calculator import. Exercise tracking setting exists and defaults false; no chain/Greeks/spread/exercise behavior tested | **Reuse/validate.** Check legacy/PyO3 types, adapter-specific feeds, licensing, assignment/margin behavior; no blanket end-to-end support claim |
| C21 Logging/health/operator view | Native logging, lifecycle and engine status surfaces; [logging](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/concepts/logging.md), [live guide](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/concepts/live.md) | Doctor and bounded observer exist; no persistent freshness/health view | **Configure then extend.** Read-only health/freshness and incident evidence are project gaps; tearsheets are not a live operations console |
| C22 Deployment and parallelism | Wheels, Docker, example programs, upstream Makefile/test tooling; [README](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/README.md), [architecture](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/concepts/architecture.md) | Mac wheel imports; upstream integration suite and deployment not run | **Reuse/verify.** One concurrent node per process; separate processes for parallel comparisons. Upstream development targets differ from our Makefile |

## Important limits on reuse

1. No node, database, broker client or strategy was started by the capability probe.
   Import/configuration success does not prove financial correctness or recovery.
2. Python/Cython and Rust/PyO3 types are not interchangeable by assumption. Several
   docs discuss both runtimes; validate each call against the installed surface.
3. Native streaming, cache persistence and event sourcing solve different problems.
   The reviewed event-store guide explicitly says writer failure can leave a session
   continuing uncaptured: it is not an automatic trading halt. That implementation
   is not our current observer's journal.
4. Native risk controls do not establish the user's portfolio risk budget or prove
   annual doubling is feasible. [Goals](goals.md) remains the mandate owner.
5. Dataset immutability, source rights, strategy selection evidence, backup restore,
   process supervision and operator actions still need project-specific decisions.
6. No additional analytical database or reporting library is justified yet. Revisit
   when native configuration and a concrete unmet requirement provide evidence.

## Reading map

The reviewed entrypoints are [overview](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/concepts/overview.md),
[concept index](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/concepts/index.md),
[architecture](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/concepts/architecture.md),
[getting started](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/getting_started/index.md),
[integration index](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/integrations/index.md),
[API reference index](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/docs/api_reference/index.md), and
the focused documents linked by row. Source and upstream test inspection resolve
availability questions; tests found in the repository were not run by this audit.

Source links are commit-pinned upstream references to files inspected locally under
ignored `vendor/nautilus_trader/`. They are not a claim that external links were
network-validated by this offline review. See the
[v1.231.0 upstream tree](https://github.com/nautechsystems/nautilus_trader/tree/v1.231.0)
for repository navigation.
Refresh this matrix after dependency/runtime upgrades or newly verified behavior.

## Subsequent reporting verification

The [performance-browser receipt](tasks/2026-10-25-local-performance-browser.md)
records later C17/C18 implementation. The earlier audit JSON is an immutable
snapshot before Plotly installation. Native precomputed-statistics rendering is
verified; PortfolioAnalyzer metric equivalence, catalog and execution persistence
remain unverified. MLflow uses a separate environment and app-owned SQLite store.
