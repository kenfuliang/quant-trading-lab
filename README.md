# Local trading platform

Updated 2026-10-27 (America/Los_Angeles). This file owns current capability status
and project entrypoints. The active priority is infrastructure, using Python and
NautilusTrader locally without QuantConnect.

## Current package layout

Research implementations now live in `research/features/`, `policies/`,
`evaluation/`, `control/` and `studies/spy/`. Use `scripts/current/` for new research
commands; existing flat source paths remain frozen for saved experiments.
The [architecture and compatibility contract](docs/architecture.md#research-package-layout-and-frozen-compatibility)
explain the mapping, preserved entrypoints and separate source identities.
[Migration evidence](docs/tasks/2026-10-27-code-reorganization.md) records the offline
checks. Historical command examples below retain their original reproduction role.

Current dependency directions are enforced by `make boundaries-check` and CI;
see the [boundary contract](docs/architecture.md#enforced-python-dependency-boundaries).

Closed file-bundle recovery is tested for one completed and one failed historical
bundle; see the [SOP and limits](docs/operations/evidence-recovery.md). General
database, tracking-store and disaster recovery remain unverified.

## Start here

- [Generated research evidence index](docs/research-evidence-index.md) — plans, results, failures, lessons and explicit publication gaps

- [Documentation map and conventions](docs/README.md)
- [Project foundation and report formats](docs/tasks/2026-10-27-project-foundation-adoption.md)
- [Golden research standard and cycle register](docs/research-standard.md)
- [Teams, skills, routing and readiness](docs/skills.md)
- [Goals and investment mandate](docs/goals.md)
- [External research intake and source registry](docs/research-intake.md)
- [NautilusTrader capability matrix](docs/capabilities.md)
- [Architecture and state ownership](docs/architecture.md)
- [Development workflow](docs/workflow.md)
- [Infrastructure roadmap](docs/roadmap.md)
- [Local operations](docs/operations/local.md)
- [Local strategy performance browser](docs/operations/performance.md)
- [IBKR paper observation](docs/operations/paper-connection.md)

```text
Define outcome → implement one slice → verify offline → record evidence
                         ↓
               update capability status
```

## Current capabilities

| Capability | State and evidence |
| --- | --- |
| Development workflow and SOPs | Established in `docs/`; project skills in `.agents/skills/` |
| Research documentation foundation | [GRS-1.0](docs/research-standard.md), cycle/decision/paper templates and [folder/content conventions](docs/tasks/2026-10-27-project-foundation-adoption.md); documentation availability does not imply automatic enforcement |
| ML modeling and ML infrastructure advisers | Advisory availability is listed in the [catalog](docs/skills.md#available-advisory-skills); RSI handoff defined; [contracts](docs/advisory-team.md#ml-team-handoff-in-rsi). Consultation available; no generic training/orchestration or inference service implemented |
| Bounded research skills | Available workflows are listed in the [catalog](docs/skills.md#available-research-workflows); [procedure](docs/research-development.md), [evaluation receipt](docs/tasks/2026-10-25-research-skills.md). Instructions support scoped offline work; no unattended optimizer or broker promotion implemented |
| Research scoring and decision control | Versioned evidence gates, raw-unit Pareto comparisons, bounded action priority and hash-chained reserve/record journal implemented; three pilot decisions, eight audited new cases and fresh adversarial review. [Review package](docs/tasks/2026-10-25-recursive-research-review.md); caller evidence verification and coordinator-enforced aggregate financial limits remain necessary |
| Temporal performance diagnostics | Rolling observed-session returns/Sharpe, deepest versus longest drawdowns, recovery/censoring and historical daily ES95; [research review](docs/tasks/2026-10-25-recursive-research-review.md). Descriptive history, not current risk signals or loss bounds |
| Decision logs and outcome labels | Saved SPY gate inputs reconstructed separately from execution and matured5/21/63-session outcomes; protection, missed-rebound and already-cash warning analysis. [Contract](docs/research-development.md#decision-logs-and-outcome-labels), [review](http://127.0.0.1:8765/gate-decisions/20261025-v2/index.html). Prospective/live capture remains planned |
| Feature engineering | Project-local skill, versioned three-feature registry and causal saved-SPY diagnostic implemented; [contract](docs/feature-engineering.md), [first test](docs/tasks/2026-10-25-feature-engineering-skill.md). Descriptive associations only; no trained predictor or changed strategy |
| Local environment | Python 3.12 `.venv`; NautilusTrader 1.231.0 pinned in requirements.txt; exact packages in requirements.lock.txt |
| GitHub Actions CI | PR/push workflow runs `make check` on Ubuntu/Python 3.12; [contract](docs/workflow.md#continuous-integration). Hosted push/PR checks verify locked dependencies, documentation, dependency layers, frozen file hashes and the checked-out branch’s offline suite; no deployment or broker operation |
| Offline regression checks | `make check`; tests use fixtures and build observer configuration without connecting |
| IBKR observation tools | Implemented in `paper_trading/`; `scripts/paper.py` exposes doctor, probe, observe; no execution client |
| Broker verification | Blocked by paper-account access in the last observed session on 2026-10-24; no successful engine-to-broker connection recorded |
| Historical SPY fixture | Completed and independently reconciled; [report](reports/spy/20261024-235746-728801/report.md), [methodology](research/README.md) |
| Upstream capabilities | Native catalog, risk, reports, persistence and reconciliation assessed in the capability matrix; availability differs by runtime |
| Native reports and local MLflow | Saved SPY reports rendered via native precomputed-statistics interface; two audited portfolios imported for browser comparison, including overall/annual Calmar and Sharpe rankings, charts and CSV; see performance SOP |
| Strategy catalogue and exploratory suite | All 100 ideas catalogued; 22 local daily-SPY adaptations × four exposure targets, with independent ledger audits, annual/full-period rankings and explicit blockers for 78 unsupported entries; [protocol](research/strategy-suite.md) |
| Leveraged SPY research | Eight $300,000 daily-sizing base cases plus financing/margin stress paths; annual/full-period rankings, independent ledger reconciliation and separate MLflow experiment; [model](research/leverage-model.md) |
| Native catalog/execution persistence | Not configured or behavior-verified; see roadmap |
| Project comparison view | Saved SPY slice available through local MLflow; generic strategy import and operational health view remain planned |
| Additional SQL/analytical stores | Deferred pending evidence of a native gap; PostgreSQL/DuckDB are not selected prerequisites |
| Paper orders and real-money execution | Not implemented; no paper or real-money order submitted by this project |

The Gateway login attempt reported that paper access was not enabled. A support
inquiry was submitted by the user; its resolution has not been verified here.
Account provisioning is external to this project. The
[paper SOP](docs/operations/paper-connection.md) owns connection steps and source evidence.

The [capability-led decision](docs/decisions/0002-native-capabilities-first.md)
supersedes the initial PostgreSQL-first design. Native configuration/catalog proof remains planned. An explicitly requested
saved-result reporting slice is now available using MLflow-owned SQLite; this
does not select an execution-state database or migrate the engine runtime.

## View saved strategy performance

Run `make performance`, then open [performance home](http://127.0.0.1:8765/) or
[MLflow](http://127.0.0.1:5050/). Use `make performance-stop` to stop both servers.
Run `make leverage-comparison` for the separate leverage/financing research comparison.
Run `make strategy-suite` for the supported catalogue batch; this does not implement
all 100 candidates or obtain missing datasets.
The [performance SOP](docs/operations/performance.md) owns setup and limitations.

The [recursive research review](http://127.0.0.1:8765/recursive-research/20261025-review-v3/index.html)
adds inventory, goals, prior research, fixed-rule cost sensitivity and temporal paths.
The gate/entry-only infrastructure is implemented and behavior-tested. The bounded
improvement epoch used all16 attempts across two studies: the combined gate failed
the joint loss-depth/duration criterion; a predeclared four-case removal of price-peak
conditions passed against both bases at5/10bp. Two control-check failures remain
preserved with separately qualified account evidence. These are viewed-history
results, not independent alpha, trained RL or broker readiness. See the
[epoch record](docs/tasks/2026-10-25-rsi-risk-gate-epoch.md) and
[browser comparison](http://127.0.0.1:8765/risk-gate/20261025-epoch-v1/index.html).
Existing allocation rules31–34
remain saved development references. Frozen history ends2025-12-31 and does not
establish today's market state.

The [SPY/IEF/GLD readiness audit](docs/tasks/2026-10-25-rsi-etf-readiness.md) is
complete with a **not-ready** result. Three frozen inputs passed basic structural
checks; two native synthetic probes verified shared cash, fee-aware whole shares
and rejection. Dividend payment data, adjustment/calendar/rights qualification,
native corporate actions and the monthly allocator remain open. The fixed six-case
portfolio design remains non-executable with zero financial budget. The
[decision-layer research map](docs/tasks/2026-10-25-research-decision-layers.md)
screens industry/asset selection, exposure, risk and strategy allocation methods.

## Local checks

Run from this directory:

```sh
make check
make doctor
```

These targets operate locally without Gateway or broker access. See
[local operations](docs/operations/local.md) for environment reconstruction and
failure handling. Broker connection commands are intentionally separate.

## Repository navigation

```text
.agents/skills/       repeatable project-specific Codex workflows
AGENTS.md            agent entrypoint and conditional instructions
Makefile             local verification commands
scripts/             command entrypoints and offline capability audit
paper_trading/       broker observation and offline fixtures
research/            research rules, data checks, plans and bounded control
reporting/           shared metrics, saved-result adapters and renderers
tests/              offline behavior checks
docs/               design, roadmap, SOPs, decisions, templates, task evidence
reports/             dated historical evidence
```

[Architecture](docs/architecture.md#repository-structure) owns folder responsibilities;
[documentation conventions](docs/README.md#content-structure) own content and
report-template selection. Future package grouping is forward-only and requires
its own compatibility checks.

`data/`, `vendor/`, `.venv/`, and `.local/` are ignored local material. Preserve
source snapshots and prior reports. The retired LEAN setup is in `archive/lean/`.
The public project repository is [kenfuliang/quant-trading-lab](https://github.com/kenfuliang/quant-trading-lab).
Generated leverage runs, MLflow state, environments and vendor checkouts remain
local/ignored; the source SPY fixture and validation receipts are versioned.
Follow [local setup](docs/operations/local.md) and the performance SOP to recreate
the environment and browser reports from a fresh checkout.
