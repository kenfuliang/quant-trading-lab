# Local trading platform

Updated 2026-10-25 (America/Los_Angeles). This file owns current capability status
and project entrypoints. The active priority is infrastructure, using Python and
NautilusTrader locally without QuantConnect.

## Start here

- [Documentation map and conventions](docs/README.md)
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
| Local environment | Python 3.12 `.venv`; NautilusTrader 1.231.0 pinned in requirements.txt; exact packages in requirements.lock.txt |
| Offline regression checks | `make check`; tests use fixtures and build observer configuration without connecting |
| IBKR observation tools | Implemented in `paper_trading/`; `scripts/paper.py` exposes doctor, probe, observe; no execution client |
| Broker verification | Blocked by paper-account access in the last observed session on 2026-10-24; no successful engine-to-broker connection recorded |
| Historical SPY fixture | Completed and independently reconciled; [report](reports/spy/20261024-235746-728801/report.md), [methodology](research/README.md) |
| Upstream capabilities | Native catalog, risk, reports, persistence and reconciliation assessed in the capability matrix; availability differs by runtime |
| Native reports and local MLflow | Saved SPY reports rendered via native precomputed-statistics interface; two audited portfolios imported for browser comparison, including overall/annual Calmar and Sharpe rankings, charts and CSV; see performance SOP |
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
The [performance SOP](docs/operations/performance.md) owns setup and limitations.

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
paper_trading/       current IBKR observation implementation
research/            preserved historical fixture
tests/              offline behavior checks
docs/               design, roadmap, SOPs, decisions, templates, task evidence
reports/             dated historical evidence
```

`data/`, `vendor/`, `.venv/`, and `.local/` are ignored local material. Preserve
source snapshots and prior reports. The retired LEAN setup is in `archive/lean/`.
The private project repository is [kenfuliang/quant-trading-lab](https://github.com/kenfuliang/quant-trading-lab).
Generated leverage runs, MLflow state, environments and vendor checkouts remain
local/ignored; the source SPY fixture and validation receipts are versioned.
Follow [local setup](docs/operations/local.md) and the performance SOP to recreate
the environment and browser reports from a fresh checkout.
