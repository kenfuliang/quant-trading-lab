---
status: active
updated: 2026-11-18
owner: project-maintainers
---

# Analysis layer (Plan 4, phase P2) implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn run outputs into analysis:
- a metrics summary;
- a stage waterfall from an ablation ladder;
- trust statistics (PSR, DSR, PBO);
- an automated lookahead check;
- a tearsheet.

It also rebuilds the incumbent SPY EMA/volatility gate through the harness, with a reconciliation report, and shows the results on the dashboard.

**Architecture:**
- **Computation** lives in `research/evaluation/` (`metrics`, `strategies`, `ladder`, `trust`, `lookahead`, `analysis_output`).
- **Tearsheet:** a new unpinned `reporting/run_tearsheet.py` wraps NautilusTrader's tearsheet with plain pandas inputs.
- **Commands:** `scripts/analysis.py` ties them together. It reads registry trial counts, because evaluation may not import control.
- **Outputs** are `analysis-output/v1` folders under `<data root>/analysis/`.
- **Views:** a control-layer reader renders them for the Pipeline page and a new Analysis tab.

**Tech Stack:** Python 3.12, pandas, numpy, stdlib `statistics.NormalDist`, `unittest`, NautilusTrader 1.231 (tearsheet only). No new dependencies.

**Spec:**
- [offline research infrastructure design](2026-11-17-offline-research-infra-design.md), section "4. Analysis" and the P2 phasing row;
- [conventions](../conventions.md);
- the approved master plan of 2026-11-18 (Plan 4 block).

## Global Constraints

- **Layers (`scripts/check_boundaries.py`):**
  - evaluation → data, features, policies, evaluation, reporting;
  - control → control only;
  - reporting → reporting only;
  - commands → everything.

  Current code may not import frozen legacy modules or edit pinned files (`research/compatibility.json`; for example `reporting/saved_runs.py`, `reporting/annual.py` and `reporting/temporal.py` are pinned and may not be changed).
- **Units:** fractions in data; 252 sessions a year; Sharpe at a zero risk-free rate, labelled. Metric keys and signs match the registry's `METRICS`:
  - `net_cagr`, `sharpe`, `calmar`, `turnover`;
  - `max_drawdown`: a **positive magnitude**, as the registry stores it (e.g. 0.177701);
  - `longest_underwater_sessions`, `longest_underwater_days`.

  Drawdown is measured from the running peak including the initial-capital baseline.
- **Trades:** signals at the close of *t*, fills at the open of *t*+1; raw prices; whole shares; long-only; cash earns zero.
- **Trial unit:** one frozen configuration. Ladder rungs, parity runs and lookahead re-runs are not trials. A PBO grid is labelled as an illustrative grid, not counted as registry trials.
- **Outputs:**
  - Exclusive create; nothing overwritten.
  - Analysis folders go under `<data root>/analysis/<analysis_id>/`, with `analysis.json` (schema `analysis-output/v1`), `tearsheet.html` and `report.md`.
  - The schema id must be catalogued (`research/registry/artifacts.json`).
- **Tests and docs:** tests are offline (the runner blocks network) and each test stays under 30 s. Docs follow `docs/README.md`.

## Decisions (controller rulings from the code survey, binding)

- **Incumbent target:**
  - The registry incumbent (`legacy-002`) is a gate over leveraged-ETF T11 weights, which the platform has no data for.
  - The rebuild therefore targets the SPY-only discrete EMA/volatility gate, compared with registry `legacy-030-discrete-ema-volatility-gate`: C01-5bp, 2005–2025, CAGR 0.087343, max DD 0.177701, Sharpe 0.7689, Calmar 0.491514, underwater 513 sessions / 746 days.
  - It also reports `legacy-058-gate-only-spy-control`.
- **Incumbent rules** (from `research/registry/incumbents.json`; price-peak component disabled):
  - Inputs: raw SPY closes; EMA 50 and 200 (`adjust=False`, `min_periods` equal to the span); 20-return sample volatility (ddof 1) × √252.
  - **Red:** volatility ≥ 0.40.
  - **Yellow:** trend non-positive (EMA50 ≤ EMA200) or volatility ≥ 0.25.
  - **Green:** otherwise.
  - **Recovery:** red → yellow only after 5 consecutive closes with volatility < 0.35; yellow → green only after 5 consecutive closes with a positive trend and volatility < 0.20.
  - **Caps:** green 1.0, yellow 0.5, red 0.0 of a 0.99 gross allocation.
  - **Warm-up:** until EMA200 exists, the state is red (no position).
- **Data:** the rebuild runs on the quality-checked `sector-etfs-2016-2025-n1` (SPY only, 2016–2025), because the platform has no checked SPY dataset back to 2005. The reconciliation report explains the period difference. It does not gate on it.
- **Ladder rungs** for the incumbent, each run on the screening engine and linked by `parent_run` to the previous rung:
  1. `hold`: buy-and-hold 0.99, zero cost.
  2. `trend`: EMA50/200 in or out, zero cost.
  3. `gate`: the traffic light, zero cost.
  4. `costs`: the traffic light at 5 bp plus $1.

  The waterfall is the metric change from each rung to the next.
- **Trial counts for DSR:**
  - `n_trials` is the number of registry records whose `context.code` equals the comparison record's code (C01-5bp).
  - The Sharpe variance is the sample variance of those records' Sharpe values, converted to per-period by dividing each Sharpe by √252.
  - With fewer than 2 records, DSR is `null` with the reason.
- **PBO:** CSCV with 16 partitions over a declared illustrative grid: EMA fast {20, 50}, slow {100, 200}, red volatility {0.35, 0.40}, which is 8 configurations, run on the screening engine at zero cost. It is labelled "illustrative grid; not registry trials".
- **Views:** analysis JSON is read by `research/control/analysis_view.py`. The Pipeline page's trust panel shows the latest analysis per spec, and a new `("analysis.html", "Analysis")` tab shows the waterfall, trust and lookahead results, with a link to the tearsheet.

## Review Focus

1. A strategy that peeks at the next session must fail the lookahead check. The incumbent and `sma_trend` must pass at every cutoff.
2. Max drawdown must include the initial-capital baseline: a run that starts by losing money has a non-zero drawdown on its first session.
3. DSR and PBO must return `null` with a reason, not NaN or a crash, on degenerate inputs: zero variance, fewer than 2 trials, or fewer sessions than partitions.
4. Re-running an analysis must write a new folder and never overwrite one. A golden summary that changes without `--update` must fail `make check`, naming the file.
5. Escaping: spec names and notes rendered on the dashboard must be HTML-escaped.

---

### Task 1: Metrics library

**Files:**
- Create: `research/evaluation/metrics.py`
- Test: `tests/current/test_metrics.py`

**Interfaces:**
- Produces:
  - `METRIC_KEYS = ("net_cagr", "max_drawdown", "sharpe", "calmar", "turnover", "longest_underwater_sessions", "longest_underwater_days")`
  - `summarize(returns: pd.DataFrame, fills: pd.DataFrame, initial_cash: float) -> dict[str, float | int | None]`. It takes `run-output/v1` tables and returns exactly `METRIC_KEYS`.
    - `net_cagr` = (final equity / initial cash) ^ (252 / sessions) − 1.
    - `max_drawdown` is the positive magnitude, with the baseline being the initial cash.
    - `sharpe` = mean / std (ddof 1) of `net_return` × √252, or `None` when std is 0.
    - `calmar` = CAGR / max drawdown, or `None` when max drawdown is 0.
    - `turnover` = Σ|fill quantity × price| / mean equity / years.
    - Underwater is the longest run of sessions below the prior peak, plus its calendar-day span.
  - `window(returns, start, end) -> pd.DataFrame`: a sub-period slice whose equity is rebased to the slice's first previous equity.

- [ ] **Step 1: Write the failing tests:**
  - `test_hand_computed_series` (5 sessions with known equity, every key checked);
  - `test_drawdown_includes_initial_baseline` (Review Focus 2);
  - `test_flat_series_gives_none_sharpe_and_calmar`;
  - `test_turnover_from_fills`;
  - `test_underwater_sessions_and_days`;
  - `test_window_rebases`;
  - `test_matches_registry_definitions_on_synthetic_fixture_run`: runs `run_screen` on `parity_fixture.synthetic_fixture()` with `sma_trend_targets()` and checks that the summary keys equal `METRIC_KEYS` and that the values are finite.
- [ ] **Step 2: Run them.** `<python> -m unittest tests.current.test_metrics -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** them and `make check`. Expected: pass.
- [ ] **Step 5: Commit:** "Metrics library for run outputs".

### Task 2: Strategy specs, ablation ladder and waterfall

**Files:**
- Create: `research/evaluation/strategies.py`, `research/evaluation/ladder.py`
- Test: `tests/current/test_strategies.py`, `tests/current/test_ladder.py`

**Interfaces:**
- Consumes: Task 1 `summarize`. Also `market_model` (`TargetFn`, `Decision`, `history_view` semantics, `sma_trend_targets`, `MarketConfig`), `screening_engine.run_screen`, `run_output.write_run` / `new_run_id` / `config_hash`.
- Produces:
  - `build_target_fn(spec: dict) -> TargetFn`. `spec["name"]` is one of:
    - `"sma_trend"`, with `window` and `gross` (it delegates);
    - `"buy_hold"`, with `gross`;
    - `"ema_trend"`, with `fast`, `slow` and `gross`;
    - `"traffic_light"`, with `fast`, `slow`, `vol_window`, `red_vol`, `yellow_vol`, `recover_red_vol`, `recover_green_vol`, `recover_sessions`, `caps` (`{green, yellow, red}`) and `gross`.

    Any other name raises `ValueError`. Every function reads only `history`, which is causal, emits `Decision.signals` keyed `(instrument, stage)` (the stages are `trend`, `vol` and `state`), and sizes whole shares as floor(gross × cap × equity / close).
  - `INCUMBENT_SPEC`: the traffic-light dict with the Decisions values.
  - `@dataclass(frozen=True) class Rung: name: str; strategy: dict; market: MarketConfig`
  - `run_ladder(data: MarketData, rungs: list[Rung], runs_root: Path, base: dict, now: datetime) -> list[dict]`:
    - It runs each rung with `run_screen` and writes a `run-output/v1` run.
    - The config is `{strategy, market, instruments, engine, ladder: {id, rung, index}}`, and `parent_run` is the previous rung's run id (None for the first).
    - `base` carries `code_commit` and `datasets`.
    - It returns `[{rung, run_id, summary}]`.
  - `waterfall(steps: list[dict]) -> list[dict]` returns `[{from, to, delta: {metric: to − from}}]` for each consecutive pair. A `None` on either side gives a `None` delta.

- [ ] **Step 1: Write the failing tests:**
  - `test_traffic_light_states_on_constructed_series`: a hand-built close series drives green → yellow (trend), yellow → red (volatility ≥ 0.40), red → yellow only after 5 calm closes, then yellow → green after 5 good closes;
  - `test_warmup_is_red_until_slow_ema_exists`;
  - `test_unknown_strategy_raises`;
  - `test_ladder_links_parent_runs_and_writes_outputs` (the synthetic fixture, 3 rungs, in a temp runs root);
  - `test_waterfall_deltas_and_none_propagation`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** them and `make check`.
- [ ] **Step 5: Commit:** "Strategy specs, ablation ladder and waterfall".

### Task 3: Trust statistics

**Files:**
- Create: `research/evaluation/trust.py`
- Test: `tests/current/test_trust.py`

**Interfaces:**
- Produces:
  - `sharpe_per_period(returns: np.ndarray) -> float | None`
  - `psr(returns, sr_benchmark: float = 0.0) -> dict` gives `{value, sharpe, skew, kurtosis, n}`. The formula is Φ((SR̂ − SR*)·√(n−1) / √(1 − γ₃·SR̂ + (γ₄ − 1)/4·SR̂²)), where SR̂ is per period, γ₃ is skew and γ₄ is non-excess kurtosis. It returns `{value: None, reason}` when the input is degenerate.
  - `expected_max_sharpe(n_trials: int, sr_variance: float) -> float` = √V · ((1 − γ)·Φ⁻¹(1 − 1/N) + γ·Φ⁻¹(1 − 1/(N·e))), with γ = 0.5772156649.
  - `dsr(returns, n_trials, sr_variance) -> dict` gives the PSR at SR* = `expected_max_sharpe`. It returns `None` with a reason when n_trials < 2 or the variance is ≤ 0.
  - `pbo(perf: pd.DataFrame, n_partitions: int = 16) -> dict` gives `{value, logits, n_combinations, reason}`. `perf` has one row per period and one column per configuration of net returns. It uses CSCV with the Sharpe ratio as the performance metric, every combination of n/2 partitions, and PBO = the share of logits ≤ 0. It returns `None` with a reason when there are fewer rows than partitions or fewer than 2 columns.
  - All use `statistics.NormalDist`; no scipy.

- [ ] **Step 1: Write the failing tests:**
  - `test_psr_hand_value`: a fixed series, with the expected value computed in the test from the formula using `NormalDist`;
  - `test_psr_rises_with_sample_length`;
  - `test_expected_max_sharpe_increases_with_trials`;
  - `test_dsr_below_psr_when_many_trials`;
  - `test_pbo_near_zero_for_dominant_config_and_high_for_noise`: one column is strictly best in every partition, giving 0.0. For pure noise with a fixed seed and 8 configurations, the value is between 0.2 and 0.8;
  - `test_degenerate_inputs_return_none_with_reason` (Review Focus 3).
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** them and `make check`.
- [ ] **Step 5: Commit:** "Trust statistics: PSR, DSR and PBO".

### Task 4: Lookahead check

**Files:**
- Create: `research/evaluation/lookahead.py`
- Test: `tests/current/test_lookahead.py`

**Interfaces:**
- Consumes: `MarketData`, `run_screen`, Task 2 `build_target_fn`.
- Produces:
  - `truncate(data: MarketData, last: str) -> MarketData` keeps sessions ≤ `last`, bars, dividends with pay date ≤ `last`, and splits ≤ `last`.
  - `check_lookahead(data, target_fn_factory: Callable[[], TargetFn], market, cutoffs: int = 5) -> dict`:
    - The cutoffs are evenly spaced sessions, excluding the last.
    - For each cutoff it runs `run_screen` on the truncated and the full data, and compares the signals and positions for sessions ≤ cutoff − 1 (the last truncated session's orders cannot fill).
    - The result is `{status: "pass"|"fail", cutoffs: [...], differences: [{cutoff, table, first_date, count}]}`.

- [ ] **Step 1: Write the failing tests:**
  - `test_sma_trend_and_incumbent_pass_on_fixture`;
  - `test_planted_leak_fails` (Review Focus 1): a target function built by closure over the full `MarketData` that reads the next session's close;
  - `test_truncate_drops_future_actions`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** them and `make check`.
- [ ] **Step 5: Commit:** "Truncate-and-compare lookahead check".

### Task 5: Analysis output, tearsheet, command and golden summary

**Files:**
- Create:
  - `research/evaluation/analysis_output.py`, `reporting/run_tearsheet.py`, `scripts/analysis.py`
  - `research/registry/analysis-specs/fixture-ladder.json`
  - `tests/golden/fixture-ladder-summary.json`
- Modify: `research/registry/artifacts.json` (`analysis-output/v1` implemented; re-render), `Makefile` (`golden-check` in `check`), `scripts/check_docs.py` only if it requires registration of new top-level dirs
- Test: `tests/current/test_analysis_output.py`, `tests/current/test_analysis_cli.py`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces:
  - `SCHEMA = "analysis-output/v1"`.
  - Analysis spec keys: `{spec_id, title, dataset_id | fixture, instruments, rungs: [{name, strategy, market}], comparison: {record_ids: [...]} | null, pbo_grid: [strategy dicts] | null, cutoffs}`.
  - `build_analysis(spec, steps, trust, lookahead, comparison, provenance, created_utc) -> dict` returns `{schema, analysis_id, spec_id, created_utc, code_commit, datasets, runs: [{rung, run_id, summary}], waterfall, trust: {psr, dsr, pbo}, lookahead, comparison, notes}`.
  - `write_analysis(root: Path, doc: dict, tearsheet_html: str | None, report_md: str) -> Path` writes `<root>/analysis/<analysis_id>/` with exclusive create.
  - `render_report(doc) -> str` (Markdown).
  - `reporting/run_tearsheet.py`: `tearsheet_html(returns: pd.Series, stats: dict[str, float], title: str, benchmark: pd.Series | None = None) -> str`. It wraps `nautilus_trader.analysis.tearsheet.create_tearsheet_from_stats` the way `reporting/saved_runs.py` does, and imports nothing from `research`.
  - `scripts/analysis.py`:
    - `run --spec <path> [--root]` loads the dataset (`load_dataset`) or the synthetic fixture, runs the ladder, lookahead on the last rung, PSR on the last rung, DSR from registry trial counts, PBO over the grid when given, and comparison metrics read from the registry. It then writes the analysis and prints its path.
    - `golden [--update]` runs the fixture spec in a temp root and compares `{rung: summary}` (rounded to 10 decimal places) with `tests/golden/fixture-ladder-summary.json`. It fails naming the file, or rewrites it with `--update`.
  - The fixture spec has 3 rungs on `synthetic_fixture()`: `buy_hold`, `sma_trend` and `sma_trend` with costs.

- [ ] **Step 1: Write the failing tests:**
  - `test_analysis_doc_has_schema_and_keys`;
  - `test_write_is_exclusive` (Review Focus 4);
  - `test_report_markdown_lists_waterfall_and_trust`;
  - `test_tearsheet_html_contains_title` (a small series);
  - `test_cli_run_on_fixture_spec_writes_folder` (temp `QTL_DATA_ROOT`);
  - `test_dsr_counts_registry_records_by_context`, against a temp registry file;
  - `test_golden_detects_change`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Generate the golden file with `scripts/analysis.py golden --update`. Then add `golden-check` (`scripts/analysis.py golden`) to `make check`.
- [ ] **Step 4: Run** them and `make check`. All tests must stay under 30 s each.
- [ ] **Step 5: Commit:** "Analysis output, tearsheet, command and golden summary".

### Task 6: Views

**Files:**
- Create: `research/control/analysis_view.py`
- Modify: `research/control/stage_page.py` (the trust panel takes optional analyses), `scripts/stages.py` (`build` passes analyses read from `<data root>/analysis`), `scripts/analysis.py` (`build` writes `.local/progress/analysis.html`), `scripts/dashboard.py` (`("analysis.html", "Analysis")` after Readiness)
- Test: `tests/current/test_analysis_view.py`, `tests/test_dashboard.py` (one test)

**Interfaces:**
- Consumes: the analysis JSON written by Task 5. This module only reads files; it never imports evaluation.
- Produces:
  - `load_analyses(root: Path) -> list[dict]`: every `analysis/*/analysis.json` with the schema `analysis-output/v1`, invalid ones skipped with a warning list, newest per `spec_id`.
  - `render_analysis_page(analyses, built: str) -> str`.
  - `trust_rows(analyses) -> list[dict]` for the Pipeline trust panel.
  - Every value passes through `html.escape`.

- [ ] **Step 1: Write the failing tests:**
  - `test_loads_newest_per_spec_and_skips_invalid`;
  - `test_page_shows_waterfall_trust_lookahead_and_escapes` (Review Focus 5);
  - `test_stage_page_trust_panel_uses_analyses_when_present`;
  - `test_analysis_tab_appears_only_when_page_exists`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** them and `make check`.
- [ ] **Step 5: Commit:** "Analysis views: Pipeline trust panel and Analysis tab".

### Task 7: Incumbent rebuild, reconciliation and records

**Files:**
- Create: `research/registry/analysis-specs/incumbent-spy-gate.json`, `docs/tasks/2026-11-18-incumbent-rebuild.md` (a task record), `docs/tasks/evidence/2026-11-18-incumbent-rebuild.json` (a committed summary: run ids, summaries, waterfall, trust, lookahead, comparison; no prices)
- Modify:
  - `docs/tasks/2026-11-17-offline-research-infra-design.md` (P2 status) and `docs/roadmap.md` (step 4 status);
  - `research/registry/readiness.json`: R5, R6 and R8, and R7 if signal stages are covered. Each score may rise by at most 1, with the completed work cited. Re-render.
- Test: `tests/current/test_incumbent_spec.py` (the spec loads, matches `INCUMBENT_SPEC`, and has 4 rungs with the Decisions values)

**Interfaces:**
- Consumes: Tasks 2–6.

- [ ] **Step 1: Write the failing test** `test_incumbent_spec_matches_decisions`, then run it. Expected: FAIL.
- [ ] **Step 2: Write the spec:**
  - 4 rungs per Decisions on `sector-etfs-2016-2025-n1`, SPY;
  - comparison `["legacy-030-discrete-ema-volatility-gate", "legacy-058-gate-only-spy-control"]`;
  - `pbo_grid` per Decisions;
  - cutoffs 5.

  Run the test. Expected: PASS.
- [ ] **Step 3: Run** `<python> scripts/analysis.py run --spec research/registry/analysis-specs/incumbent-spy-gate.json`, then `scripts/analysis.py build` and `scripts/stages.py build`.

  Expected:
  - lookahead `pass`;
  - DSR computed from the C01-5bp registry records, or `null` with a reason;
  - PBO computed over the 8-configuration grid.

  If lookahead fails on the incumbent, stop and report. That is a finding, not something to tune.
- [ ] **Step 4: Write the reconciliation** in the task record. It covers:
  - per metric: rebuild against legacy-030 and legacy-058;
  - each difference with its explanation: period 2016–2025 against 2005–2025; dataset Alpaca raw against Yahoo; warm-up; price-peak disabled; integer shares; costs;
  - the waterfall table, trust values with their inputs (n_trials, variance), the lookahead result, and the analysis folder path relative to the data root.

  Write the evidence JSON. Update the design P2 row, the roadmap step 4 and readiness.
- [ ] **Step 5: Run** `scripts/current/research_index.py --write` and `make check`, check the Analysis tab in a browser if available, then commit: "Incumbent SPY gate rebuilt through the harness, with reconciliation".
