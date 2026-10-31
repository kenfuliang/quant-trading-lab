---
status: active
updated: 2026-10-31
owner: project-maintainers
---

# Local platform architecture

This document owns module responsibilities, state authority and target structure.
Root [README](../README.md) owns shipped capability status;
[matrix](capabilities.md) owns upstream assessment; [roadmap](roadmap.md) owns sequence.
This target replaces the earlier custom-catalog/PostgreSQL-first architecture.

## Project and dependency boundaries

This section owns the division of responsibility between this repository,
NautilusTrader and MLflow, and the decision to configure, extend, upgrade or patch
upstream. It applies the existing [native-first decision](decisions/0002-native-capabilities-first.md)
and [reporting decision](decisions/0003-local-performance-browser.md); it does not
change their priorities or establish new implementation readiness.

```mermaid
flowchart TD
    P[Project: research rules, data contracts, risk policy and evidence]
    P --> N[Supported NautilusTrader interfaces]
    P --> M[Supported MLflow tracking interfaces]
    N --> E[Engine: data, execution, portfolio and native analytics]
    M --> T[Tracking: runs, parameters, metrics and artifacts]
    E --> R[Project: reconciled results and provenance]
    R --> M
    B[Broker observations: external account truth] -. reconciliation .-> E
```

These are ownership boundaries, not evidence that the live execution path is
configured. The [capability matrix](capabilities.md) records what is available,
configured and behavior-verified; root README owns current project status.

| Concern | What we build and own | What the dependency provides |
| --- | --- | --- |
| Strategy and research | Economic hypotheses, causal features, strategy rules, labels, trial budgets, chronological evaluation, costs and interpretation | NautilusTrader strategy/actor interfaces and simulation facilities; it does not select a profitable strategy for us |
| Data | Provider rights, frozen source snapshots, instrument/calendar/adjustment policy, quality gates and transformation provenance | NautilusTrader typed market data and native catalog/provider interfaces; source presence alone does not qualify our dataset |
| Trading runtime | Node configuration, adapters at project seams, account/mode policy, recovery tests and operational supervision | NautilusTrader engines, native order/execution routing, cache, portfolio and reconciliation facilities; configured support varies by adapter/runtime |
| Risk | Portfolio loss/leverage/concentration budgets, risk-gate logic and failure actions with explicit validation | NautilusTrader native order validation, limits and trading controls; these do not guarantee a drawdown ceiling |
| Financial results | Metric definitions, cash/dividend/financing assumptions, independent reconciliation and comparison eligibility | NautilusTrader analyzer/reports/tearsheets where compatible; MLflow records the values we supply rather than auditing their financial correctness |
| Experiment tracking | Importers, stable source/run fingerprints, tags, metric naming/units and links to preserved receipts | MLflow experiments/runs, parameter and metric logging, artifact storage APIs and browser comparison |
| Storage and operations | Select/configure storage, retain original evidence, test backups/restore, operate local services and protect credentials | Native persistence interfaces and MLflow-managed tracking stores; neither an interface nor a successful import proves recovery |
| CI and maintenance | Test our policies, adapters/importers, reports and integration against pinned versions; preserve failures | Upstream CI tests upstream code; their passing checks do not validate our application |

The offline research ledger is a declared, independently reconciled fixture. It
is not a second live order-management system or proof of native margin behavior.
We prefer native runtime/reporting capabilities before building replacements and
keep custom calculations when required by a documented financial contract.

State authority and durability are defined [below](#state-authority-and-durability).

### Configure, extend, upgrade or patch

Use the lowest-cost supported path that satisfies a concrete requirement:

| Choice | When to choose it | Required evidence before adoption |
| --- | --- | --- |
| Configure | The pinned release already supplies the required behavior | Effective configuration, an offline behavior check, failure/restore checks where relevant and a recorded readiness limit |
| Extend in this project | Project-specific strategy, policy, transform, report or importer fits a supported public interface | A small explicit interface/adapter, tests for timing/accounting/failure behavior and preserved upstream IDs; prefer public APIs over private internals |
| Upgrade a dependency | A supported newer release fixes the issue or exposes the needed capability | Release/API compatibility review, isolated environment, deliberate direct/lock updates, project regression/integration checks and rollback plan |
| Modify upstream source | A minimal reproduction shows a defect or missing core capability that configuration, supported extension and an acceptable upgrade cannot resolve | Separate fork/branch, pinned upstream base plus patch commit, regression test and license/attribution review; contribute upstream when appropriate |

Examples: implement a new strategy using NautilusTrader's strategy interface;
implement a new research score and log it through MLflow's tracking client; review
an upgrade if a needed supported API is absent; patch the engine or tracking server
only for a demonstrated defect that belongs there. Avoid replacing an entire
engine, tracker or database to solve a narrow missing integration.

A source patch is a maintained dependency: build/package it reproducibly, record
its provenance in run receipts, run the applicable upstream tests plus our
integration tests, and track an upstream issue/PR or an explicit local rationale.
Record the owner, removal/upgrade condition and rollback version. Ordinary checks
stay offline; broker validation requires its separately authorized SOP.

Installed files in `.venv` or `site-packages` are outputs, not an editable source
of truth. Keep project code here and upstream changes in a separately pinned
source fork/package. A reinstall must reproduce the same implementation. A
monkey-patch or private-API workaround needs the same explicit exception record,
regression tests and exit condition as an upstream patch.

### Version and artifact ownership

The direct requirements and frozen locks own installed versions; avoid copying
version numbers into competing policy lists. Keep the core engine and MLflow in
their existing separate environments, as documented in [local operations](operations/local.md)
and the [performance SOP](operations/performance.md). Updating one does not
implicitly authorize changing the other.

Track application code, configuration templates, setup/import scripts, dependency
locks and redacted audit receipts in Git. Generated environments, account secrets,
MLflow's local SQLite/server state and generated local artifacts stay outside Git
under the existing storage/ignore policies. A public repository is not permission
to publish credentials or datasets with unverified redistribution rights.

## Algorithm decision hierarchy

[GRS-1.1](research-standard.md#minimal-pipeline) owns the minimal two-decision
pipeline, optional stage versions and adoption rules. This section owns the
expanded component wiring only; it does not maintain another version sequence.
The [cycle register](research-cycles.md) points to actual experiment records.
Data qualification, accounting and baseline protections stay present throughout.

### Reference: expanded component view

The map below preserves the optional full hierarchy. Its numbers identify
functional blocks, not mandatory development stages or V0–V3 versions. **I** means
an existing component within a named research scope, **P** means proposed
integration/model, and **U** means an unverified claim. Root [README](../README.md)
owns current availability. The map is not evidence of an autonomous running system.

Green boxes are existing scoped components (**I**). Amber dashed boxes are
proposed components or common interfaces (**P**). An existing algorithm may need
an adapter to expose its intermediate state or targets; source presence alone
does not prove that connection. Alternative models and sizing methods are choices
to compare, not instructions to average or stack every output.

```mermaid
flowchart TD
    subgraph L1["1 · Inputs and features"]
        DATA["I · Historical data<br/>Prices, actions, universe and provenance"]
        CHECK{"I · Declared input checks pass?"}
        FEAT["I · Causal features<br/>Returns, EMA, RSI, ADX, ATR, volatility"]
        STOP["I · Block dependent experiment<br/>Keep failure evidence"]
        DATA --> CHECK
        CHECK -->|Pass| FEAT
        CHECK -->|Fail or unknown| STOP
    end

    subgraph L2["2 · Market understanding"]
        RULE["I · Rule baseline<br/>EMA / volatility traffic light"]
        GMM["I · Gaussian mixture<br/>Current return-distribution membership"]
        HMM["P · HMM alternative<br/>State persistence and transitions"]
        RETURN["I · Ridge baseline<br/>Next-session intraday return estimate"]
        STATE["P · Common state interface<br/>State estimates, uncertainty, as-of time"]
        RULE --> STATE
        GMM --> STATE
        HMM --> STATE
    end
    FEAT --> RULE
    FEAT --> GMM
    FEAT -.-> HMM
    FEAT --> RETURN

    subgraph L3["3 · Strategy and target selection"]
        ASSET["I · Existing ranking policies<br/>Sector / ETF / stock momentum; low volatility"]
        ELIG["P · Common eligibility / ranking interface<br/>Instrument IDs, ranks, availability"]
        ROUTER["P · Strategy router<br/>Specialist budgets or cash; fixed rules first"]
        ASSET --> ELIG --> ROUTER
    end
    FEAT --> ASSET
    STATE --> ROUTER
    RETURN -->|Separate return estimate; no assumed profit score| ROUTER

    subgraph L4["4 · Proposed positions"]
        TREND["I · Trend / breakout policies<br/>EMA, MACD, Donchian, Turtle adaptation"]
        REVERT["I · Reversion policies<br/>RSI, Bollinger, z-score"]
        STATS["I · Statistical policies<br/>Ridge long/cash; pairs adaptation"]
        COMPOSITE["I · Composite policies<br/>T11; existing ensemble alternative"]
        COMBINE["P · Common target interface and combiner<br/>Instrument weights; overlap and cash accounting"]
        TREND --> COMBINE
        REVERT --> COMBINE
        STATS --> COMBINE
        COMPOSITE --> COMBINE
    end
    ROUTER --> TREND
    ROUTER --> REVERT
    ROUTER --> STATS
    ROUTER --> COMPOSITE
    ELIG -.->|Universe restrictions where compatible| COMBINE

    subgraph L5["5 · Portfolio size and risk"]
        SIZE["I · Choose one declared sizing policy<br/>Fixed exposure, volatility target, traffic light or CPPI"]
        LIMIT["I · Scoped portfolio checks<br/>Sector limits, cash reserve and buying power"]
        SIZE --> LIMIT
    end
    COMBINE --> SIZE
    RULE -.->|Optional explicit gate treatment| SIZE

    subgraph L6["6 · Historical simulation and accounting"]
        EXEC["I · Study-specific execution model<br/>Timing, fills, rejected orders and costs"]
        BOOK["I · Account and reconciliation<br/>Positions, cash, dividends and financing"]
        EXEC --> BOOK
    end
    LIMIT --> EXEC

    subgraph L7["7 · Evaluation and research review"]
        METRIC["I · Separate outcome / risk / evidence views<br/>Return, DD, Sharpe, Calmar, underwater, contribution"]
        REVIEW["I · Bounded research decision<br/>Retain, reject, tradeoff or investigate"]
        NEXT["I · Freeze the next approved experiment<br/>Rules, controls, data, costs and trial budget"]
        METRIC --> REVIEW --> NEXT
    end
    BOOK --> METRIC
    NEXT -.->|Research iteration; no live policy change| ROUTER

    classDef existing fill:#e4efdf,stroke:#55754b,color:#203020;
    classDef proposed fill:#fff0cf,stroke:#b58a35,stroke-dasharray:6 4,color:#493917;
    class DATA,CHECK,FEAT,STOP,RULE,GMM,RETURN,ASSET,TREND,REVERT,STATS,COMPOSITE,SIZE,LIMIT,EXEC,BOOK,METRIC,REVIEW,NEXT existing;
    class HMM,STATE,ELIG,ROUTER,COMBINE proposed;
```

### Handoffs and evidence boundaries

| Boundary | Required output / interpretation |
| --- | --- |
| 1 → 2 / 3 | Validated as-of features, instrument identity, source and adjustment policy, missing/warmup status. Each study qualifies its own data. |
| 2 → 3 | Distinguish regime membership, risk forecasts and return forecasts; include horizon, model version and availability time. A mixture posterior is not a calibrated crash probability. |
| 3 → 4 | Eligible specialists/instruments, nonnegative capital budgets including cash, selection reason and effective time. Proposed until the router and compatibility adapters are tested. |
| 4 → 5 | Instrument-level proposed weights with provenance for each specialist; prevent duplicated capital and unintended cancellation of hedges. Per-policy universe rules remain intact. |
| 5 → 6 | Permitted targets, selected sizing policy, effective time and check outcomes. Predictive red signals and failed operational requirements have different meanings; neither implies a guaranteed drawdown ceiling. |
| 6 → 7 | Modeled fills/rejections, account path, fees/actions/financing, source identity and reconciliation. Local synthetic ledgers and hosted LEAN paths retain separate execution contracts. |
| 7 → next experiment | Matured outcomes, comparable controls, all trials, falsifiers and a frozen next plan. Full-sample winner labels cannot become earlier trading inputs. |

No generic router, state exporter, common position combiner or automatic model
retraining is implemented by these diagrams. **U:** unseen selection advantage,
a calibrated future-stress forecast, native parity across all local policies,
the combined hierarchy at USD300,000, and paper/live operation of this hierarchy.
A failed input check blocks this research path; it does not specify automatic
cancellation or liquidation of an external broker account.

The state examples are defined in [statistical models](../research/model-strategies.md);
other policy owners are [daily signals](../research/daily-strategies.md),
[allocation methods](../research/allocation-strategies.md),
[feature engineering](feature-engineering.md) and
[research scoring](research-scoring.md). The [suite protocol](../research/strategy-suite.md)
and dated [T11](tasks/2026-10-26-qc504-t11-gate.md),
[stock-selection](tasks/2026-10-26-selection-completion.md) and
[sector-control](tasks/2026-10-26-sector-matched.md) receipts retain their own
results, rights, data and execution limits. Negative results remain evidence,
not recommendations to allocate capital.

## Target flow

The [bounded Alpaca paper slice](operations/alpaca-paper.md) extends the pinned
native live-client interfaces in project code because no Alpaca adapter is
installed. It uses a flat-start, one-share, single-session policy and independently
checks broker state; it is not a second general OMS or a supported full adapter.
Required general report/restart methods reject explicitly. The IBKR observer and
target flow below are preserved; offline replay and paper observations have
separate MLflow evidence labels.

The [proposed local data library](data-library.md) specifies source snapshots,
instrument/action contracts, qualification and phased independent-provider
coverage. The [Alpaca pilot](tasks/2026-10-25-alpaca-us-stock-pilot.md) verifies a
bounded fixed-route data downloader and native catalog bar/instrument round-trip;
general ingestion remains planned. The dated
[provider screening](tasks/2026-10-25-independent-data-review.md) is separate from
this subsequent runtime proof and does not itself establish authenticated access.

```mermaid
flowchart TD
    S[Source data] --> V[Project validation and provenance receipts]
    V --> C[Nautilus Parquet catalog]
    C --> D[Native data engine]
    B[IBKR data adapter] --> D
    D --> T[Strategies and actors]
    T --> R[Native risk engine plus configured policies]
    R --> E[Native execution engine]
    E --> I[IBKR execution adapter]
    I --> G[IB Gateway paper]
    G --> I
    I --> E
    E --> P[Native cache and portfolio]
    D --> P
    P --> A[Native reports and analyzer]
    A --> H[Native tearsheets and small comparison view]
    E --> K[Configured persistence and streaming]
    K --> O[Read-only operational health view]
```

This is a responsibility map, not an exhaustive message sequence. Native message
bus/lifecycle link these modules. Project policy checks use the native trading path;
operators must not bypass the risk engine to submit broker orders. No execution
client or new persistence path has been configured in our observer.

## Reuse and extension responsibilities

| Module | Native responsibility | Project work where evidence shows a gap |
| --- | --- | --- |
| Catalog and ingestion | Typed market data, Parquet storage/query | Source rights, frozen input hashes, normalization identity, quality/calendar policies |
| Node configuration/lifecycle | Kernel, engines, actors/strategies, start/stop | Explicit mode/account/feed binding, config/dependency identity, process supervision |
| Runs/results | Native run/config IDs, results/statistics | Small artifact index and comparison eligibility checks; preserve native IDs |
| Execution | Orders, fills, positions, routing/reconciliation | Fault validation and procedures; no duplicate OMS |
| Risk and portfolio | Native validation, rate/notional limits, trading states, balances/PnL | Mandate-specific drawdown, leverage, concentration, feed and margin-buffer policies |
| Persistence | Current-node backing, streaming and component-state hooks | Select backend after restore proof; assess capture coverage before extending audit gaps |
| Analytics | Analyzer, reports, benchmark comparisons and tearsheets | Account/cash-flow/cost definitions and small cross-run selection view |
| Operator view | Native status/logging inputs | Read-only health/freshness/uncertainty and incident evidence |

The saved-result reporting slice now uses native precomputed-statistics HTML and
local MLflow in an isolated environment. MLflow-owned SQLite/artifacts track
historical experiments; they do not own broker/execution state. See the
[performance SOP](operations/performance.md) for the implemented path and
[decision 0003](decisions/0003-local-performance-browser.md) for its rationale.

The explicitly requested [leverage research model](../research/leverage-model.md)
uses a separate offline cash/share ledger with independent Decimal reconciliation.
It feeds the comparison renderer and a separate MLflow experiment. It does not
configure native margin execution or establish broker behavior.

The [strategy catalogue suite](../research/strategy-suite.md) now extends the
offline research path with causal signal adapters, optional sizing overlays and
separate worker processes. An inventory of 100 candidates is distinct from the
22 simulated adaptations. The renderer shows unmet data/execution prerequisites;
it does not fabricate results for unsupported candidates.

The [research development procedure](research-development.md) and [cataloged project skills](skills.md#available-research-workflows)
provide the instruction layer for scoped research. They use existing artifacts/tools; they do not implement an
autonomous optimizer, scheduler, new datastore or broker promotion path.

## State authority and durability

Broker observations establish externally accepted orders, fills and account state.
Native engine/cache/portfolio maintain local working state. Reconciliation explains
discrepancies before resuming; a stale view cannot establish broker truth.

Frozen inputs, run manifests and audit receipts establish historical project
evidence provenance. Corrections produce new linked versions rather than replacing
the original evidence.

MLflow owns its tracking metadata and imported artifact copies. A FINISHED run
means the tracking/import operation finished; it does not establish profitable,
reproducible, approved or broker-ready trading behavior. MLflow is not our live
execution journal or a substitute for backing up original evidence.

Catalog data represents normalized historical observations. Frozen source bytes
and provenance receipts identify what generated them; catalog files alone do not
establish immutability or provider licensing.

Our Python TradingNode kernel wires Redis or no backing for cache/message bus.
PostgreSQL classes elsewhere are not a drop-in configured backend on this path.
Streaming writes Feather files, separately from the historical Parquet catalog.
Component load/save, cache restoration, stream replay and durable event-store
capture differ in coverage and failure semantics.

Rust event-store documentation does not establish a configured journal in our
legacy node. Assess capture, durability, retention, failure signals and restore
before choosing journal implementation. PostgreSQL and DuckDB remain deferred
options; neither is the project-wide authority by decision at this stage.

## Required receipts and policies

- Data receipts identify source bytes, provider/instrument, coverage, timestamp
  convention/calendar, adjustments, transformation version and quality outcome.
- Run receipts preserve native IDs plus mode, inputs, effective configuration,
  code revision/dirty-file hashes, dependencies, status and artifact references.
- Audit extensions preserve native identities/correlation, distinguish intent from
  observed acknowledgment, and document gaps/ordering. Define extensions only after
  understanding native capture coverage.
- Comparisons flag differing dates, capital, cost/cash-flow policy, leverage and
  evidence quality; return on posted margin is not portfolio return.

These are later implementation requirements. The matrix distinguishes source
presence, imports and behavior proof. Existing historical evidence stays intact.

## Modes, controls and deployment

Project modes distinguish offline replay/simulation, paper observation, paper
execution and eventual live operation. Bind account/feed policy explicitly.
Native startup reconciliation defaults on; this does not verify connectivity or
establish that all continuous polling is configured.

Native HALTED/REDUCING controls are candidates to configure and verify. Pause new
submissions, cancel orders and close positions have separate effects. Stopping a
process is not cancellation. Query/reconcile unknown external outcomes before
retrying. Operational failure policies must be tested.

Use one concurrent node per process; parallel comparison workers use separate
processes. Keep current Python/Cython interfaces until a separate compatibility
decision justifies migration; Rust/PyO3 examples do not automatically apply.

## Repository structure

The scoped offline research controller is separate from native execution state:

```mermaid
flowchart LR
    A[Agent verifies plan, evidence and global budget] --> B[Research controller: reserve decision]
    B --> C[Bounded saved-SPY runner]
    C --> D[Existing ledger plus guarded Decimal replay]
    D --> E[Immutable results and independent metric review]
    E --> F[Scoring and temporal reports]
    F --> G[Research journal: outcome and branch decision]
    G --> A
```

`research/control/research_controller.py` owns hash-chained decision events, idempotent
operations, logical/resource reservations and branch state. Its journal is local
research history, not broker truth or proof of native node recovery.
`research/studies/spy/bounded_study.py` owns strict saved-SPY plans, per-plan case limits,
finite/coverage guards, output hashes and verified cache reuse. The coordinator
currently enforces the aggregate financial ceiling and deadline outside that runner.
`research/control/scoring.py` owns score consistency and ordering; [scoring](research-scoring.md)
owns meanings. `reporting/temporal.py` owns descriptive path calculations.
The research ledger remains the existing Python simulator; neither this slice nor
its tests establish Nautilus execution parity or new instrument support.

### Offline RSI foundation

The [foundation checklist](tasks/2026-10-27-rsi-foundation-implementation.md)
tracks the newer bounded engineering slice. Its
[operating SOP](operations/recursive-research.md) owns handoffs; GRS remains the
research/adoption rule owner. It wraps the existing controller without rewriting
frozen financial runners, NautilusTrader or MLflow.

```mermaid
flowchart LR
    C[Cycle contract and pinned prior lesson] --> P[Immutable program spec]
    P --> X[RSIProgram: single writer and aggregate bounds]
    X --> J[ResearchController: logical journal]
    X --> L[Execution log: actual allowed launches and recovery]
    L --> A[Synthetic or read-only adapter output]
    A --> V[Artifact/context verification]
    V --> R[Version registry: explicit scoped disposition]
```

`research/control/rsi_contracts.py` owns RSI-CYCLE-1 validation and the narrow saved-C001
lesson check. `research/control/rsi_coordinator.py` owns fixed registered commands,
launch reservations, output preservation and safe stopped recovery under the
controller's writer lock. `research/control/rsi_adoption.py` owns frozen evaluation
context, numerical gate consistency and append-only version/rollback records.
`scripts/current/rsi_foundation.py` joins these for the scoped demonstration and known
synthetic process comparison. Module existence is distinguished from its actual
test/demo evidence in the checklist.

Only synthetic and read-only process adapters exist. An output hash or declared
check does not authenticate evaluator provenance or establish financial truth.
Financial registry passes remain provisional; synthetic engineering adoption
does not change a financial incumbent. Persistent source hashes detect changed
inputs; local journals are not an OS sandbox or tamper-proof signed archive.

```text
README.md                     current capabilities and entrypoints
AGENTS.md                     instructions and conditional pointers
.agents/skills/               repeatable project workflows
docs/                         matrix, architecture, roadmap, SOPs and decisions
paper_trading/                paper adapters, observation tools and fixtures
research/                     research rules, data checks, plans and bounded control
reporting/                    shared metrics, saved-result adapters and renderers
scripts/                      entrypoints, local checks, offline audit
tests/                        offline project behavior checks
reports/                      dated historical evidence
vendor/nautilus_trader/        ignored pinned upstream source
```

The supporting [foundation proposal](tasks/2026-10-27-project-foundation-proposal.md)
describes the content/report structure and forward-only package grouping. No code
move is adopted by that proposal; this document remains the module/state owner.

Add modules with their first concrete use. Keep native interfaces visible and
introduce adapters where behavior varies, such as fake versus IB communication.
No speculative database/migration package is needed for the native baseline.


### Research package layout and frozen compatibility

The proposed grouping is now implemented for the published research code:

```text
research/
├── features/          causal feature transforms
├── policies/          signals, allocation overlays and risk-gate rules
├── evaluation/        financing ledger, reconciliation and input/temporal audits
├── control/           catalogue access, scoring and research journal/controller
├── studies/spy/       bounded runner, engine fixture, reports and historical adapters
├── plans/             preserved study definitions; new gate plans use current/
├── compatibility.json immutable old-file hashes and canonical module mapping
└── *.py               frozen legacy implementations, retained for reproduction
scripts/current/       current command entrypoints
scripts/*.py           preserved legacy commands and unaffected operational tools
tests/current/         behavioral suite for current implementations
tests/test_*.py        preserved legacy coverage plus migration checks
```

New development imports the concrete implementations in these packages, rather
than forwarding to flat modules. The machine-readable
[compatibility manifest](../research/compatibility.json) owns the exact old-to-new
mapping and baseline hashes. The legacy copies are intentional immutable source
inputs, not second development owners. Never synchronize current edits back into
them. Existing commands/imports therefore retain their original behavior and byte
identity. Original test files remain unchanged; their migrated counterparts test
the current graph. `tests/test_package_compatibility.py` checks frozen bytes,
imports, source identity separation, CLI discovery and synthetic output parity.

`make strategy-suite` and `make leverage-comparison` select current commands.
For a new bounded plan use `scripts/current/bounded_study.py`; old
`scripts/bounded_study.py` and flat imports remain the historical route. Current
runners hash their new source paths; a legacy plan is rejected there rather than
silently acquiring a different implementation. Existing hash/data failures in
old plans remain failures. This migration never renews financial budgets.

Historical gate adapters in the current namespace require separately prepared
`research/plans/current/` plans, use `.local/current-risk-gate/` state and
`reports/current-risk-gate/` outputs. Those plans are not generated or executed
by this infrastructure change. Synthetic ETF probes likewise isolate state under
`.local/current-etf-readiness/`. Historical comparisons still read their original
report references. No historical report, plan or journal is renamed or rewritten.

Shared metrics, saved-result adapters and renderers remain in `reporting/`, broker
observation in `paper_trading/`. Ignored `data/` and `.local/` retain their roles.
`research/README.md` remains the frozen SPY methodology. The primary checkout's
unpublished later research is outside this published-main migration; move it only
with its own source-identity review. No NautilusTrader or MLflow source changes,
dependency upgrades or new financial results are part of this change.

[Content/report conventions](README.md#content-structure) own document structure;
[foundation adoption](tasks/2026-10-27-project-foundation-adoption.md) records this
slice and remaining gaps without changing M1–M5 priority or runtime readiness.

### Enforced Python dependency boundaries

The executable layer policy lives in [`scripts/check_boundaries.py`](../scripts/check_boundaries.py).
`make boundaries-check` runs it without importing application code; `make check`
and the existing PR/push CI workflow include that gate. The
[implementation review](tasks/2026-10-27-dependency-boundaries.md) records acceptance
and the structural score; these are infrastructure findings, not strategy results.

```mermaid
flowchart TD
    CMD[Current commands] --> STUDY[Studies]
    STUDY --> POL[Policies]
    STUDY --> EVAL[Evaluation and independent audits]
    STUDY --> CTRL[Research control]
    POL --> FEAT[Features]
    EVAL --> REPORT[Shared reporting and metrics]
    CMD --> PAPER[Paper observation tools]
    CI[CI boundary gate] -.-> CMD
    CI -.-> STUDY
    LEGACY[Frozen legacy implementations: preserved, exempt from layering]
```

Reusable research/reporting/broker packages cannot import commands or tests.
Features remain independent of higher layers; policies can use features, evaluation
can use policies/features/reporting, and control remains separate from execution.
Studies compose those pieces. Reporting and broker observation stay independent of
research orchestration. The code policy owns the exact allowlist; all current
project Python modules in these roots are checked, including future modules.
Unknown flat research modules fail instead of inheriting a permissive exemption.
Static dependency cycles also fail.

[`research/evaluation/saved_review.py`](../research/evaluation/saved_review.py)
owns the four unchanged independent saved-ledger review functions. Current callers
import that library. Its metrics remain separate from the primary ledger and
reporting calculations so extraction does not collapse independent checking.
The current reviewer CLI records its own and the helper's hashes. Current study
code lists and derived-review provenance reference the helper's new path.

The compatibility manifest retains exactly the original protected-file hash map;
its owner mapping additionally points the frozen reviewer to the new library and
current command. Frozen legacy research/scripts/tests keep their original imports
and bytes; current implementations cannot import them. Shared reporting and broker
modules may be both hash-protected and current: they are checked for layering,
not misclassified as obsolete just because their bytes are preserved.

The checker resolves ordinary, relative, member, function-local and type-checking
imports, recognizable literal dynamic imports and aliases. Nonliteral dynamic
imports and recognized opaque Python loaders fail the checked contract. Tests
exercise rejected imports/cycles, frozen tampering and the actual Make target's
nonzero exit. This is static architecture enforcement, not a security sandbox,
complete runtime dependency graph, third-party side-effect audit or validation of
subprocess command targets. Arbitrary reflection and monkey-patching are outside
its guarantee. Tests may deliberately use both graphs for compatibility checks.

### Research evidence index

The [generated evidence index](research-evidence-index.md) and
[machine-readable view](research-evidence-index.json) provide navigation across
published study definitions, receipts, result reports, failure narratives and
lessons. They do not own result truth or supersede [GRS](research-standard.md).
The [registry](../research/evidence-registry.json) owns curated study membership,
plan ownership and explicit evidence references; source records retain all claims.
The [generator](../research/control/evidence_index.py) owns deterministic rendering
and validation. These are separate responsibilities, not duplicate result stores.

```text
Curated registry + original plans/tasks/receipts/reports
                         ↓ validate and hash referenced files
                  JSON + Markdown index
                         ↓ compare committed generated bytes
                    PR/push CI gate
```

Every indexed study has plans/results/failures/lessons slots. A published reference
has a kind (plan, receipt, report, narrative or artifact), path, optional verified
Markdown heading, note and derived SHA-256. Missing/unpublished/not-applicable
slots require reasons and never receive clickable nonexistent artifact paths.
A published receipt is not evidence that all of its underlying raw files are
published. Failure references can be counterevidence or narrative context; notes
must distinguish them from actual failed execution artifacts. Unknown failures
are not zero failures, and a plan is not execution authorization.

All JSON plans under `research/plans/`, including future nested plans, require
exactly one study owner. Other task/receipt files are listed separately as unassigned
supporting records, without inferring a research study from a filename. Initial
coverage is the published plans, named legacy studies/diagnostics and the existing
local-only C001 pointer; unpublished later research is not silently imported.
This is not an exhaustive historical attempt reconstruction.

`make research-index` regenerates only the two derived views. `make evidence-index-check`
validates registry fields, plan coverage, reference existence/allowed local paths,
Markdown heading anchors and committed output equality without writing. It is part
of `make check`, already used by PR/push CI. Referenced source changes refresh hashes
and make the view stale until regenerated. No network, broker, database, MLflow or
financial execution is involved. Ordinary tests use disposable fixtures.

Generation has no runtime timestamp or machine-local paths, and never inspects
unpublished local artifacts. It validates all inputs before output writes; each
output is atomically replaced. The two files are not a transactional database;
CI detects partial/stale output if interrupted. Reference checking proves navigation
and recorded bytes, not financial accuracy, source authenticity, schema validation
of arbitrary receipts, complete claim-to-source alignment or backup/restore.

### Closed evidence recovery

[`research/control/evidence_recovery.py`](../research/control/evidence_recovery.py)
owns manifest-qualified closed file-bundle copy/restore. The
[recovery SOP](operations/evidence-recovery.md) owns operation and limitations.
The current CLI records a separately pinned inventory hash; full inventories
remain private. Source and restored bundles keep their original manifest bytes,
terminal status and failures. Existing destinations are never merged/overwritten.
No financial execution is imported or invoked. The [scoped drill](tasks/2026-10-27-evidence-recovery.md)
is same-machine file recovery, not proof of complete project/store/disaster recovery.


## Offline RSI foundation

```mermaid
flowchart LR
    C[Cycle contract] --> P[Immutable bounded program]
    P --> X[RSI coordinator]
    X --> J[Existing current ResearchController journal]
    X --> A[Fixed synthetic or saved-evidence checker]
    A --> V[Artifact/context verification]
    V --> R[Synthetic adoption or provisional financial disposition]
```

`research/control/rsi_contracts.py` owns RSI-CYCLE-1, contained artifact reads and
the pinned saved-C001 lesson. The byte-matched installed
`research/control/legacy_control_contract.py` verifies its narrow diagnostic
transition; historical source bytes are checked but never executed.
`research/control/rsi_coordinator.py` owns fixed commands, aggregate launch/time
bounds, retained output and stopped ambiguous recovery under the existing current
controller's single-writer lock. `research/control/rsi_adoption.py` owns exact
context, numerical gates and append-only disposition/rollback records.
`scripts/current/rsi_foundation.py` owns operator arguments and the bounded demo.
[The SOP](operations/recursive-research.md) owns handoffs and command semantics;
[the integration task](tasks/2026-10-27-rsi-integration.md) owns observed validation.

No current module imports a frozen implementation or loads a historical runner.
The fixed saved-preflight adapter requires authenticated inputs within its checkout
before reservation; the standalone read-only CLI can check an explicit external
history root without importing code from it. Missing private evidence is unavailable,
not a synthetic pass. Financial execution is disabled. No NautilusTrader/MLflow
source, dependency, broker state or financial incumbent changes.

### Checkpoint integration reuse seams

The2026-10-31checkpoint preserves frozen local implementations and ports current
commands to canonical study/control packages. `research/compatibility.json` owns
byte identities and exact paper/research reuse seams: credential parsing, native
SPY strategy/configuration, pure T11 indicators and the risk policy. This is not
permission for paper code to import arbitrary studies or descendant modules.

The existing read-only T11 preview has one reviewed whole-file-SHA-bound opaque
loader exception. Its private source must match `POLICY_HASH` before loading.
Only `runpy.run_path` in that exact file/version is exempted from the static rule;
changed bytes, other files and other loaders remain rejected. Static checking is
not a sandbox or proof of policy purity, runtime readiness or order authorization.
