---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Local performance browser SOP

This file owns starting, stopping and reconstructing the saved-result browser.
The [SPY methodology](../../research/README.md) owns the original fixture assumptions.
The [leverage research model](../../research/leverage-model.md) owns the separate
financing experiment. Root README owns current implementation status.

```text
Immutable saved SPY curves + audited summary
          ↓ validation and provenance hashes
Nautilus create_tearsheet_from_stats → HTML reports on 127.0.0.1:8765
          ↓ import via isolated MLflow client
MLflow local SQLite + artifacts     → comparison on 127.0.0.1:5050
```

## Start and view

From the repository root:

```sh
make performance
```

Open [performance home](http://127.0.0.1:8765/) for native report links, MLflow runs
and a two-run comparison. Reports show statistics, benchmark equity overlay,
drawdowns, monthly and yearly returns. MLflow stores the audited summary metrics,
daily equity/return/drawdown histories, parameters, source hashes and artifacts.
Metric names ending in `_pct` are percentage points, not decimal fractions.
`max_drawdown_pct` is the full-period minimum; `drawdown_pct` is a time series whose
latest value can differ. MLflow run duration is import time, not historical duration.

The imported experiment is **SPY saved historical comparisons**. In MLflow use the
Model training view, select the two runs and Compare. Click `equity_usd` or
`drawdown_pct` for historical curves; steps are the common ordered daily observations,
including one initial anchor. The experiment period is recorded separately.

## Compare calendar years

The performance home links **Rank strategies by Calmar and Sharpe · overall and annual**:
a ranked leaderboard with period and score selectors, annual performance/score tables,
four interactive bar charts, and downloadable CSVs. Full period displays all years;
selecting a year filters the annual table. Rankings sort descending, share exact ties,
and leave undefined scores unranked. Return and drawdown remain visible, since
negative-score rankings can favor a strategy with a larger dollar loss. Each MLflow run also contains `report/annual.csv`,
`report/annual-comparison.csv`, `report/score-ranking.csv` and
`report/annual-comparison.html` under Artifacts.
These are report artifacts; MLflow's built-in comparison summary still shows the
full-period metrics. The new `calmar_full_period` metric appears alongside the
existing `sharpe_zero_rf` in MLflow comparison. Use the local HTML link for annual
score selection and ranking; annual scores remain report artifacts, not extra
scalar columns in the MLflow summary.

Annual return is year-end equity divided by the previous year-end balance minus
one; the first year starts from initial cash. Annual maximum drawdown resets its
high-water mark at that same opening balance and measures the worst decline across
that year's daily closes, including the opening balance. This captures a first-day
loss but does not carry an earlier year's peak forward. Keep full-period drawdown
for losses spanning calendar boundaries. Returns include the existing fixture's
costs and cash dividends. The synthetic anchor does not count as a trading session
or create an extra year. CSV percentages use percentage points; the return-advantage
column is EMA annual return minus buy-and-hold annual return.

### Score definitions

- Full-period Calmar = saved CAGR / absolute saved full-period maximum daily-close
  drawdown. This uses the full 2005–2025 window, not a trailing 36-month convention.
- Annual Calmar = that calendar year's return / absolute within-year drawdown.
  The numerator is the calendar-year return, without extrapolating partial years.
- Sharpe = mean daily simple portfolio return / sample standard deviation (`ddof=1`)
  × sqrt(252), with a 0% risk-free rate. Annual Sharpe includes only that year's
  session returns; its first return uses prior year-end equity (initial cash for
  the first year). Exclude the synthetic zero-return anchor from return samples.
- No drawdown produces N/A Calmar. Fewer than two returns or zero variance (absolute
  tolerance 1e-15) produces N/A Sharpe. CSV uses blank numeric fields for N/A.
- Overall Sharpe retains the audited summary value; overall scores are not averages
  of annual scores. Rank uses unrounded finite values, competition ranking (1,1,3).
- `score-ranking.csv` is the long-form ranking export for overall and annual periods;
  `annual-comparison.csv` retains paired returns/drawdowns and adds scores/winners;
  per-run `annual.csv` includes both scores and ranks.

Formula references: [Calmar](https://fynance.readthedocs.io/en/stable/generated/fynance.metrics.calmar.html)
and [daily Sharpe and annualization](https://www.jeroenbouma.com/projects/financetoolkit/docs/performance/sharpe-ratio).
Project-specific windows, 0% rate and sample conventions above govern these reports.
Additive Calmar import checks an existing value before reuse; repeat starts do not
append another scalar or duplicate daily metric histories. Report rendering hashes
and score contract version are recorded in the import bundle.

The scoped fixture covers all evaluation years; a future truncated input would
require explicit partial-year labeling before broadening the importer. Annual
comparisons do not alter strategy parameters, original reports or existing run IDs.

The native equity chart is a growth multiple beginning at 1. The saved USD equity
and ending-balance statistics retain actual dollars. Charts include a zero-return
anchor one calendar day before the first session so initial losses count in drawdown.
The original audited statistics exclude that anchor and are displayed as precomputed
values; native analyzer calculations have not replaced the independent source audit.

The saved fixture used USD 100,000 over 2005–2025, cash dividends without automatic
reinvestment, illustrative costs, no borrowing, and no independent holdout claim.
It is not a USD 300,000 leveraged scenario or evidence of future return targets.
No strategy or broker connection is run by this command.

## Leveraged SPY research

Run `make leverage-comparison` to start the local browsers, create/reuse the defined
financing experiment and import its eight base cases into the separate MLflow
experiment **SPY leverage research · daily sizing**. Performance home links the
leverage dashboard. `make performance` refreshes the existing leverage link/view
without rerunning simulations; a new leverage experiment requires the explicit
leverage target. `make performance-stop` stops both browser services as before.

The dashboard compares both signals at 1x, 1.25x, 1.5x and 2x nominal targets,
with full-period and year-specific return/drawdown/Calmar/Sharpe ranks, financing,
checked exposure, margin buffer and liquidation status. Select a scenario, year,
metric and signal. The annual chart follows scenario/metric/signal but displays
all years; the equity plot is explicitly the base scenario. Annual tables have
168 rows per scenario (21 years × eight portfolios). Undefined metrics sort last.

Base financing is illustrative fixed 6%, and the two separate stress sets use 9%
financing or 50% maintenance. Definitions, limitations, event ordering and the
new daily-sizing baseline are owned by the model document above. This is an offline
portfolio-ledger simulation, not a native Nautilus execution/margin implementation
or broker readiness evidence. Original $100,000 fixtures and MLflow experiment 1
stay separate. Never compare their capital/sizing/dividend policies as identical.

Immutable research output lives in `reports/leverage/<input-code-config-hash>/`.
The manifest hashes every result artifact, source/signal inputs and implementation;
all 24 paths retain daily ledgers/trades/annual scores and independent Decimal
reconciliation. Complete matching runs are hash-verified before reuse; an incomplete
folder is retained and fails closed. Code/model changes generate a new identity.
Development receipts can remain as earlier identities; `.local/performance/leverage-latest.json`
identifies the current displayed result. Render-only changes do not alter financial
run identity. The current generated view includes a source manifest and model copy.
MLflow owns a separate imported copy of base daily curves/metrics/ledgers and all
comparison scores. Stress paths remain local research artifacts, not extra MLflow
base runs. A repeat successful import reuses finished runs and does not append daily
history again. Failed attempts remain FAILED for inspection. No concurrent import.

OHLC marks and fills use cent precision (half-even fill rounding); carried cash and
interest use full arithmetic precision. Tests cover weekend interest, dividends,
initial rejection, gap/low liquidation, halt and negative-equity liabilities.
Actual liquidation fills, time-varying borrowing rates, SMA/settlement and broker
house rules remain unverified/omitted as documented. No broker connection is made.

## Strategy catalogue suite

Run `make strategy-suite` for the explicitly requested exploratory research batch.
It starts/reuses the existing browser services, hash-verifies cached completed
results or executes supported cases with three worker processes, independently
audits ledgers, imports into a separate MLflow experiment and links the catalogue
dashboard from performance home. `make performance` only refreshes a previously
built suite view/link; it does not start a new strategy search.

The [suite protocol](../../research/strategy-suite.md) owns trial policy, frozen
rules, evidence levels and remaining prerequisites. The 100-entry catalogue is an
inventory: 22 supported local SPY adaptations produce 88 exposure cases. The other
78 remain unsupported (data/instrument gaps); their performance is unavailable. All runs are exploratory
on already-viewed 2005–2025 history, not independent out-of-sample proof. User data
budget is free/local only; no paid feed or new account is configured.

The dashboard filters full period/year, score and nominal leverage. Rankings show
top20 by default with an all-case toggle, and preserve all rows in CSV. Its annual
chart retrospectively selects five leaders from the selected ranking; that selection
is not a trading rule. Catalogue rows distinguish simulated adaptations from data, instrument or execution-model blockers. None is a paper/live readiness claim. CPPI and other overlays
can reduce actual exposure below the nominal cap, as the protocol explains.

Immutable output is ignored under `reports/strategy-suite/<hash>/`. Each manifest
records inputs, method/code identities, 88 audits and artifact hashes. Failed worker
folders and incomplete manifests remain for inspection and cannot be blindly reused.
Original research directories and experiments remain intact; earlier 15- and 21-rule
screens are separate evidence, not merged into the final22-rule ranking. Latest pointer
is `.local/performance/strategy-suite-latest.json`. Read its URL for the current
local dashboard rather than assuming a fixed financial-run hash. Repeat import
reuses FINISHED cases; FAILED cases remain visible and retries use new attempts.
Concurrent suite starts/imports are unsupported. Full backup/restore remains pending.

## Stop and storage

```sh
make performance-stop
```

Stops this project's supervisor and its two browser processes; preserves generated
reports, tracking metadata and artifacts. Services bind to loopback only. The static
server serves `.local/performance/`, not the repository root. No login or cloud service
is needed. The services are not configured to start at machine boot.

- `.local/performance/`: reports and import bundles, grouped by input/contract fingerprint.
- `.local/mlflow/tracking.db`: MLflow-owned SQLite metadata; not execution persistence.
- `.local/mlflow/artifacts/`: imported reports and provenance artifacts.
- `.local/performance-server.log`: service logs; inspect if ports are unavailable.
- `.local/performance-service.json`: owned supervisor identity used by stop.

Repeated starts reuse finished MLflow runs for the same input/contract fingerprint.
Report artifacts can be refreshed without duplicating metric histories. Changed
financial input bytes create a new identity. Failed imports stay FAILED and can be
inspected; retry creates a new attempt. Concurrent starts/imports are unsupported;
use one operator command at a time.

## Reconstruct dependencies

The existing `.venv` contains the engine and Plotly HTML renderer. MLflow is isolated
because the full frozen engine package set did not resolve with modern MLflow.
Static Kaleido export is not required or installed for this HTML-only path.

For a fresh environment, with Python 3.12 available:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m venv .local/venvs/mlflow
.local/venvs/mlflow/bin/python -m pip install -r requirements-mlflow.lock.txt
make performance
```

Preserve existing environments until replacements verify successfully. Direct
dependencies live in requirements.txt and requirements-mlflow.txt; each has a frozen
lock file. Reinstalling needs package-network access; normal operation reads saved
local inputs. Fresh-environment reconstruction of both locks is not established
solely by the successful installation and checks on this machine.

## Verification and limits

### Recursive research and temporal review

The scoped [review browser](http://127.0.0.1:8765/recursive-research/20261025-review-v3/index.html)
shows goals, inventory, primary-source reuse, eight new fixed-rule cases in separate
5bp/10bp contexts, existing risk references, annual observations and temporal paths.
Its [task review](../tasks/2026-10-25-recursive-research-review.md) owns evidence and
limits; [research development](../research-development.md#performance-diagnosis)
owns temporal definitions. No additional MLflow import was performed for this pilot.

Rebuild into a **new** ignored snapshot directory after checking referenced evidence:

```sh
.venv/bin/python scripts/build_recursive_review.py --output .local/performance/recursive-research/<new-review-id>
.venv/bin/python scripts/recursive_research_report.py --register-existing .local/performance/recursive-research/<new-review-id>
```

This reads saved receipts/ledgers and renders reports; it does not execute financial
simulations or start services. Open that directory's `index.html` under the existing
performance server. Preserve earlier snapshots and their manifests. The renderer's
registration checks artifact hashes and stores a pinned manifest pointer; normal
performance-home regeneration restores that verified link without new research.
The renderer's
unknown state is distinct from a failed check. No current market color is supplied:
the financial snapshot ends2025-12-31.

### Saved-run adapter and backup

The adapter validates snapshot SHA-256, audit status, date ordering/uniqueness,
positive finite equity, session counts, ending value, total return and maximum
drawdown against saved summaries before rendering. The source directory is read-only
to the adapter. The import is scoped to the existing two-portfolio SPY result format;
general strategy ingestion and cross-experiment compatibility checks remain planned.

For a recovery copy, stop the browsers, copy `.local/performance/` and
`.local/mlflow/` together with project code/locks and original reports. These local
files are ignored by Git and need a separate backup. An automated backup/restore
system and execution-state recovery are not supplied by MLflow.

## Saved gate decision and outcome review

The [gate decision review](http://127.0.0.1:8765/gate-decisions/20261025-v2/index.html)
adds eight saved gate/base comparisons, separate decision/execution/outcome CSVs,
5/21/63-session labels, episode/year filters and full-path warning counts. Existing
`make performance` serves the files when local services are needed; this diagnosis
used the already-running server and did not import MLflow or rerun strategies.

Default: ablated gate / EMA,5bp,21sessions, first actionable reduction. Select2020
and helped-during-base-loss to inspect protection;2022and missed-rebound to inspect
missed upside. The outcome-label filter applies to the selected anchor/year, not
all daily sessions. Select the anchor **Every warning already in cash** to inspect daily dates (first200
matching rows displayed), or download `decisions.csv`
and filter `warning_already_cash`; primary reduction anchors intentionally exclude
these unactionable warnings. Full-path count cards do not change with year/horizon.

[`scripts/gate_decision_review.py`](../../scripts/gate_decision_review.py) rebuilds
this saved-evidence view into a **new** output directory using `--output PATH`.
It hashes/checks all187parent artifacts and frozen source bytes, reads saved
account paths and writes derived reports; it neither reserves nor consumes a
financial trial. It refuses an existing output directory. Logs are reconstructed,
not contemporaneously recorded. [Lifecycle contract](../research-development.md#decision-logs-and-outcome-labels)
owns meaning and [task receipt](../tasks/2026-10-25-gate-decision-labels.md) owns
validation/results. Existing/public history and modeled dividend/execution
limitations remain unchanged.
