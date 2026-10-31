# Local trading platform

Updated 2026-10-30 (America/Los_Angeles). This file owns current capability status
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

- [Six-ETF T11 selector comparison](docs/tasks/2026-10-30-t11-universe-comparison.md) — four provisional result rows; selector trails fresh gated T11, bounded budget closed, missing audits and comparisons preserved

- [T11 on SOXL or cash: eight cloud tests](docs/tasks/2026-10-30-t11-soxl-cloud-results.md) — provisional native summaries favor full gated T11 at both costs; analysis UI available, official exports and daily audits remain incomplete

- [Calmar epoch3 negative-results report](docs/tasks/2026-10-30-calmar-epoch3-experience-report.md) — twelve audited cases across correlation-aware selection and sector-breadth market conditions; both rejected, incumbent unchanged

- [Skills and SOP repair checklist](docs/tasks/2026-10-30-skills-sop-repair.md) — recovered management/stage skills, new receipt validation and separate research/paper readiness reviews; offline evidence only

- [T11 official export validation](docs/tasks/2026-10-29-t11-export-validation.md) — both result downloads verified; candidate closing paths match prior summaries, while decision/input/native-execution gates remain blocked

- [Generated research evidence index](docs/research-evidence-index.md) — plans, results, failures, lessons and explicit publication gaps

- [Documentation map and conventions](docs/README.md)
- [Project foundation and report formats](docs/tasks/2026-10-27-project-foundation-adoption.md)
- [Golden research standard and cycle register](docs/research-standard.md)
- [Teams, skills, routing and readiness](docs/skills.md)
- [Canonical research leaderboard](docs/leaderboard.md) — saved results grouped by comparable context, with risk and temporal metrics
- [Parallel RSI diagnosis and readiness](docs/tasks/2026-10-28-rsi-readiness-wave.md) — saved SPY attribution, blocked selector reconstruction and isolated synthetic execution-record audit; zero new financial runs
- [Sector issuer reconciliation](docs/tasks/2026-10-28-sector-issuer-qualification.md) — payment dates and omissions resolved; scoped accounting and eight-case replay audits passed
- [Sector comparison results](docs/tasks/2026-10-28-sector-selection-experience-report.md) — eight audited cases; Calmar improves about18%, but the strict joint drawdown screen fails at10bp; no adoption
- [Sector risk-gate results](docs/tasks/2026-10-28-sector-gate-experience-report.md) — six audited cases; Calmar roughly doubles and drawdown falls to12.5%, but growth and recovery worsen; no adoption
- [Blocked T11 reproduction goal](docs/tasks/2026-10-28-t11-reproduction-rsi-goal.md) — private synthetic policy conformance verified; original daily references and qualified input/engine/accounting route are missing; zero of six financial attempts used
- [Goals and investment mandate](docs/goals.md)
- [External research intake and source registry](docs/research-intake.md)
- [QuantConnect research objective checklist](docs/tasks/2026-10-26-quantconnect-research-master-plan.md) — O00–O02 discovery/indexing complete; O03 licensed-method review available; full contracts blocked, O04 rights triage started
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
| Research management and stage workflows | Recovered `/ask-pm`, `trade-research-management` and `trade-stage-development` instructions with provenance; [catalog](docs/skills.md) owns discovery. Offline receipt validation and descriptive readiness summaries added; [repair evidence](docs/tasks/2026-10-30-skills-sop-repair.md). No scheduler, generic runner enforcement or order authorization |
| Bounded research skills | Available workflows are listed in the [catalog](docs/skills.md#available-research-workflows); [procedure](docs/research-development.md), [evaluation receipt](docs/tasks/2026-10-25-research-skills.md). Instructions support scoped offline work; no unattended optimizer or broker promotion implemented |
| Stage development workflow | Shared [skill/catalog](docs/skills.md), [stage procedure](docs/research-development.md#individual-stage-development) and RSI handoffs; [one unchanged risk/sizing exercise](docs/tasks/2026-10-27-stage-development-skill.md) with synthetic integration checks. No generic stage runner or financial improvement established |
| Offline RSI foundation | Strict cycle contracts, aggregate fixed-adapter coordinator and synthetic adoption/rollback under `research/control/`; [SOP](docs/operations/recursive-research.md), [integration evidence](docs/tasks/2026-10-27-rsi-integration.md). Saved C001 preflight requires private qualified history and reports unavailable when absent; financial adapters and automatic improvement remain unsupported |
| Research scoring and decision control | Versioned evidence gates, raw-unit Pareto comparisons, bounded action priority and hash-chained reserve/record journal implemented; three pilot decisions, eight audited new cases and fresh adversarial review. [Review package](docs/tasks/2026-10-25-recursive-research-review.md); caller evidence verification and coordinator-enforced aggregate financial limits remain necessary |
| RSI foundation | Strict cycle contracts, saved C001 lesson preflight, offline execution coordinator and version/evidence registry; [implementation checklist and actual verification](docs/tasks/2026-10-27-rsi-foundation-implementation.md), [skills/SOP handoffs](docs/operations/recursive-research.md). Default execution adapters remain synthetic/read-only. A fixed C02 local adapter (`.local/rsi-calmar-20261028/docs/tasks/2026-10-28-ceiling-capture-study.md`; private/local artifact, not published) in the isolated checkout verified six captured financial cases; its candidate was rejected and budget closed. Generic financial adapters and autonomous scientific improvement remain unavailable |
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

A subsequent [nine-path execution robustness challenge](docs/tasks/2026-10-25-rsi-gate-robustness-review.md)
retained the frozen EMA/volatility-only gate versus EMA at5/25bp and an additional
session of signal delay. Accounting, annual metrics and temporal audits passed;
buy-and-hold still grew faster and some periods favored EMA. This is viewed-history
evidence with zero remaining epoch budget, not independent alpha or a new strategy.

The [SPY/IEF/GLD readiness audit](docs/tasks/2026-10-25-rsi-etf-readiness.md) is
complete with a **not-ready** result. Three frozen inputs passed basic structural
checks; two native synthetic probes verified shared cash, fee-aware whole shares
and rejection. Dividend payment data, adjustment/calendar/rights qualification,
native corporate actions and the monthly allocator remain open. The fixed six-case
portfolio design remains non-executable with zero financial budget. The
[decision-layer research map](docs/tasks/2026-10-25-research-decision-layers.md)
screens industry/asset selection, exposure, risk and strategy allocation methods.

The [multi-asset enablement goal](docs/tasks/2026-10-25-multi-asset-unlock-review.md)
adds tested causal monthly trend/relative-strength builders, a whole-share shared-cash
order planner and a native synthetic allocation seam proof. Full historical
comparison with SPY/the gate remains **blocked** by qualified action/payment/calendar/
rights inputs, corporate-action handling and a continuous-NAV historical runner.
No multi-asset historical returns were generated; the ten-case design is non-executable.

The [blocked qualification goal](docs/tasks/2026-10-25-multi-asset-qualification-v2-checkpoint.md)
has since acquired issuer ex/pay-date histories, verified calendar alignment and
implemented a native historical research account/coordinator with exact synthetic
cash/NAV audits. Historical launch is still gated on permission-qualified price
inputs and a reviewed frozen bundle. No comparison result or native operational
readiness is inferred from these engineering checks.

The [QuantConnect Cloud comparison](docs/tasks/2026-10-25-quantconnect-spy-comparison.md)
now has three completed hosted SPY cases and 21 annual comparisons. Hold/EMA/gate
returned 9.174%/7.776%/6.917% CAGR with 51.8%/28.6%/19.6% native drawdown.
EMA remains conditional with three buying-power rejections; the failed initial
zero-trade hold is preserved and excluded. These are development diagnostics,
not independent alpha or exact Nautilus/accounting parity. See the linked receipt
for observed hosted capabilities, source identities and remaining audit limits.

The [bounded hosted sector comparison](docs/tasks/2026-10-25-sector-momentum-comparison.md)
is complete for2017–2025 with four matched selected runs and36annual metric rows.
Momentum/hold/equal-sector/original-gate CAGR was13.63%/13.95%/11.57%/9.60%;
longest underwater runs were195/488/313/593sessions. All selected runs passed
closing cash/exposure guards with zero rejected orders after a preserved technical
execution repair. The [browser report](http://127.0.0.1:8765/sector-momentum-v1/index.html)
contains annual drawdown, Sharpe, Calmar and carried-peak underwater measures.
Summary consistency is audited; independent daily accounting, source calendar and
unseen alpha remain unverified. This is a hosted diagnostic, not local multi-asset
input qualification or operational promotion.

The [copied-source #504 evaluation](docs/tasks/2026-10-26-qc504-evaluation.md)
completed within five attempts. Recent source-default and25bp slippage cases have
complete custom summaries; the longer case has native-only evidence and an
observed rejected order. The [browser report](http://127.0.0.1:8765/qc504-v1/index.html)
marks missing evidence. High modeled growth came with65–70% drawdown; financing,
capacity, independent accounting and unseen performance remain unqualified.

The [full-budget #504 sleeve ablation](docs/tasks/2026-10-26-qc504-sleeve-ablation.md)
now has five matched2020–2025 cases and30 annual rows at25bp slippage. The ensemble
leads CAGR/Sharpe/underwater duration; T11 leads Calmar/drawdown depth. All four
standalone paths contain rejected orders and remain conditional; no candidate is
promoted. The [ablation browser](http://127.0.0.1:8765/qc504-ablation-v1/index.html)
preserves these limits and temporal comparisons. Seven attempts closed, including
two reporting-only retries; no strategy tuning or broker operation.

The [staged execution/funding follow-up](docs/tasks/2026-10-26-qc504-funded-execution.md)
completed five fresh matched cases with zero observed rejected orders, explicit6%
ACT/360 debit financing and30 annual rows. T11 leads the new full-period measures;
all cases still exceed the approximate30% drawdown reference. The
[old/new policy dashboard](http://127.0.0.1:8765/qc504-funded-v1/index.html) exposes
staging delays, cash clipping, financing and boundary pending orders. This is a
combined-policy development diagnostic, not future execution or alpha proof.

The [bounded T11 gate transfer](docs/tasks/2026-10-26-qc504-t11-gate.md)
completed three fresh matched runs: the retained EMA/volatility traffic light
reduced T11 closing drawdown from51.26% to36.90%, while CAGR fell from119.67%
to92.03% and longest underwater grew from146 to199sessions. The30% reference
was not reached. Controls reproduced exactly; zero rejected orders. The
[gate comparison browser](http://127.0.0.1:8765/qc504-t11-gate-v1/index.html)
includes annual metrics and temporal tradeoffs. Development evidence only;
no OOS alpha or promotion established.

## Local checks

The [bounded Alpaca paper integration](docs/operations/alpaca-paper.md) now uses
native live-client/strategy/risk interfaces with the existing SPY EMA50/200 signal.
Offline synthetic and saved-SPY signal tests passed through a fake broker;
authenticated Alpaca paper preflight passed and the closed-market gate sent zero
orders. Results are logged separately in local MLflow. **Actual paper fills,
partial-fill recovery, general reconciliation and unattended operation remain
unverified or unsupported**; see the [receipt](docs/tasks/2026-10-25-alpaca-paper-integration.md).

The [independent-provider review](docs/tasks/2026-10-25-independent-data-review.md)
compares free stocks/ETF/FX coverage, futures gaps and six pinned collector
repositories. The [Alpaca Basic price pilot](docs/tasks/2026-10-25-alpaca-us-stock-pilot.md)
subsequently acquired 164 raw daily bars across AAPL/JPM/MSFT and SPY for January
2016 and December 2025. Structural validation, native catalog round-trip and
identical-import behavior passed; synthetic restore was verified separately.
The isolated local catalog is **conditional price data**; actions, full source-use
qualification and financial comparison eligibility remain blocked. See the
[local data-library contract](docs/data-library.md).
The [current SPY equity-holdings acquisition](docs/tasks/2026-10-25-sp500-stock-library.md)
processed 503 share-class symbols: 500 returned 1,212,539 raw daily bars for
2016–2025. Of these, 459 have full-window coverage and 41 shorter coverage; three
returned no bars. All saved bars passed final native catalog read-back. This is
a current-member, survivor-selected pool with unqualified corporate actions,
not an unbiased historical S&P 500 universe or a promoted financial dataset.
The initial library scope is now free daily US stocks, with SPY retained as a
benchmark. Broader ETF, FX, futures and options acquisition is deferred; see the
[library plan](docs/data-library.md) for the revised phases.

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
paper_trading/       paper adapters, observation tools and offline fixtures
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

The [first-three QuantConnect selection study](docs/tasks/2026-10-26-qc-selection-comparison.md)
verified free hosted equity/fundamental access and completed five matched cases,
including SPY and unchanged funded T11. The [comparison browser](http://127.0.0.1:8765/qc-breadth-v1/index.html)
contains30annual rows and temporal diagnostics. Source-informed adaptations and
feature-readiness cash periods remain explicit; two technical failures are preserved.
Stock momentum is a further-validation candidate, not a promoted strategy.

The [completed selection follow-up](docs/tasks/2026-10-26-selection-completion.md)
diagnoses early-close/short-listing readiness, tests nine fresh cases against
matched equal-weight controls and cached T11, and records three decision cards.
The [new browser comparison](http://127.0.0.1:8765/selection-completion-v1/index.html)
contains60annual rows and separate cost/delay stress. Stock momentum remains a
research candidate; this low-volatility variant stops. Exposure/capital confounds
and unseen performance remain unqualified. Hosted research does not qualify the
local500-stock catalog or establish paper/live readiness.

The [stock-momentum risk-overlay comparison](docs/tasks/2026-10-26-stock-risk-ablation.md)
adds original/gate/sector/both/SPY cases,72monthly selections per case and complete
security PnL in the [browser](http://127.0.0.1:8765/stock-risk-v1/index.html).
The overlays reduce drawdown while giving up growth; sector treatments also exclude
missing classifications. These remain USD10000 viewed-history research fixtures.

The [sector classification and matched-exposure follow-up](docs/tasks/2026-10-26-sector-matched.md)
covers all 27 missing selections with dated public-filing research inferences;
exact historical vendor classifications remain unavailable. Its [three-case review](http://127.0.0.1:8765/sector-matched-v1/index.html)
finds sector CAGR24.52%/DD25.48% versus target-matched24.27%/27.03%, with only
one session less in the longest underwater period. This is conditional development
evidence, with a closed budget and no promotion.

The [QuantConnect catalog inventory](docs/tasks/2026-10-26-quantconnect-inventory.md)
reconciles 540 community IDs across three listing orders plus 82 tutorial-index
entries (81 reachable articles and one soft404). The [browser inventory](http://127.0.0.1:8765/qc-inventory-v1/index.html)
provides provisional family filters, provenance and a 19-group existing-research
index. This is metadata coverage, not 622 reproduced strategies. Rights, source
packages, detailed contracts/data readiness and code equivalence remain open;
no new simulations were launched.

The [licensed-source and rights review](docs/tasks/2026-10-26-quantconnect-source-rights.md)
adds static inspections for 82 tutorial methods, eight manual detail cards and
three reviewed code-fragment similarities. [Browse the review](http://127.0.0.1:8765/qc-detail-rights-v1/index.html).
All 622 records have separate rights dispositions; no complete source packages or
free-data entitlements are verified. O03 remains partial; the subsequent source follow-up below records limited O05 exports.

The [82-tutorial source follow-up](docs/tasks/2026-10-26-quantconnect-tutorial-packages.md)
exports four licensed source/example bundles, including clearly labeled alternatives,
with dependency/data findings and preserved source hashes. [Browse/download](http://127.0.0.1:8765/qc-tutorial-packages-v1/index.html).
The other 78 tutorial records lack qualified bundles in this search; exact hosted
source identity and runtime/free-data readiness remain unverified. No new financial
experiment or Nautilus port was performed.

The [CAPM framework alternative follow-up](docs/tasks/2026-10-26-capm-spy-comparison.md)
passed a free hosted dependency/data checkpoint probe for all29 fixed tickers.
Its [2016–2025 annual comparison](http://127.0.0.1:8765/capm-spy-v1/index.html)
includes return, drawdown, Sharpe, Calmar and time underwater. SPY passed the
aggregate/native-accounting checks, and the authorized CAPM accounting retest
reproduced its original performance exactly. Under the fixed25bp slippage model,
CAPM CAGR−51.08%/DD99.92% versus SPY14.82%/33.57%; this alternative failed as an
improvement. Both bounded budgets are closed, and failed attempts remain preserved.
No independent alpha or deployment readiness is established.

The [CAPM cost/stop ablation](docs/tasks/2026-10-26-capm-cost-stop-ablation.md)
completes nine fresh cases: three explicit-cost levels, stock stop on/off and
matching SPY controls. [Browse all 90 annual rows and factor contrasts](http://127.0.0.1:8765/capm-ablation-v1/index.html).
Both prior controls exactly reproduce and native accounting/selection checks pass.
With commissions only, stop-on CAGR6.03%/DD37.17% compares with stop-off10.66%/42.13%
and SPY14.82%/33.53%; the stop extends longest underwater716→945sessions.
Every tested CAPM variant underperforms matching SPY on CAGR, Sharpe and Calmar.
The separate budget is closed at ten attempts with one preserved technical failure;
this is negative development evidence, with independent replay and unseen advantage unverified.


The [next licensed-candidate comparison](docs/tasks/2026-10-26-dual-thrust-spy-comparison.md)
preserves CAPM unchanged as a negative baseline. G-Score stopped after one
order-free data probe: current quarterly ROA is retired, and the legacy feed has
known look-ahead dates. The feasible fallback is an explicitly causal SPY
adaptation of licensed Dual Thrust, repairing its same-day range dependency.
[Browse the three-case comparison and 30 annual rows](http://127.0.0.1:8765/dual-thrust-spy-v1/index.html).
Under fixed native IB fees plus 5bp/fill, Dual Thrust CAGR−3.80%/DD34.06% versus
SPY14.65%/33.16%; longest underwater2,493 versus488sessions. Native accounting,
source/calendar/range checks, minute-risk diagnostics and browser checks pass,
but the candidate fails the frozen improvement screen. Five of six aggregate
attempts were used, including the blocked probe and one preserved observation
failure; the budget is closed. No unseen alpha, historical shortability or
independent cash/action replay is established.


The [licensed stock-pairs study](docs/tasks/2026-10-26-stock-pairs-spy-comparison.md)
passes an order-free raw/action/known-information data gate and completes three
qualified2016–2025cases. [Browse annual and temporal results](http://127.0.0.1:8765/stock-pairs-spy-v1/index.html).
The declared causal NVDA/AMD adaptation loses2.18%CAGRwith25.62%DDand2,341underwater
sessions versus SPY13.64%/31.26%and488, failing both frozen screens. Flat-year
ratios remain undefined. The stock-hold control grows64.66%but has65.70%DD and
hindsight selection. Budget closed at5/6attempts, including one preserved failed
probe;372offline checks pass. Known implementation leaks are repaired, but
independent alpha, historical borrow and prospective stock selection remain
unverified. CAPM and Dual Thrust evidence is preserved unchanged.

The [golden research standard GRS-1.0](docs/research-standard.md) now owns the
minimal pipeline, incremental-stage adoption, mandatory per-cycle evidence and
paper-style experience-report criteria. The [cycle register](docs/research-cycles.md)
links authoritative records. This is a documented workflow with scoped runners,
not an unattended optimizer or a newly validated combined trading system.

The [C03 position-proposal study](docs/tasks/2026-10-28-proposal-c03.md) completed six locally captured/audited cases. Faster EMA200 and simpler SMA200 price proposals trail the unchanged discrete-gate incumbent; the bounded cycle is closed. Source remains in the isolated research checkout, with no broker or generic financial adapter enabled.

The [C04 no-veto eligibility study](docs/tasks/2026-10-28-no-veto-c04.md) completed six fixed saved-SPY cases with captured UTC lifecycle and independent audits. Union eligibility failed the incumbent improvement target; gate-only increased growth with deeper/longer losses. The isolated research cycle is closed; incumbent and generic financial/broker availability remain unchanged.

[RSI epoch2](docs/tasks/2026-10-28-rsi-epoch2.md) completed two cycles and twelve audited cases without meeting the material Calmar/growth/recovery target. Incumbent unchanged; all slots consumed. C06 postseal receipt export failed and was recovered read-only; its frozen driver is not advertised as repaired. Final closure verified:624offline tests passed,all549financial artifacts preserved,no qualifying improvement and no remaining slots.


T11 + risk gate paper preparation now has a separate offline multi-ETF proposal
and restart-journal seam. Its full signal producer and native execution bridge
remain blocked; **T11 is not launched and no paper orders were sent**. See the
[paper SOP](docs/operations/alpaca-paper.md#t11--traffic-light-pilot-preparation)
and [implementation receipt](docs/tasks/2026-10-28-t11-paper-runner.md).


The [October29 T11 rehearsal](docs/tasks/2026-10-29-t11-paper-rehearsal.md) verified
read-only account preflight and a fresh24-instrument,414-session data snapshot.
A prototype now produces daily features/gate/policy previews; no T11 order was
submitted. Qualified operational features and native multi-ETF execution remain
incomplete; no trader or scheduler was deployed.
