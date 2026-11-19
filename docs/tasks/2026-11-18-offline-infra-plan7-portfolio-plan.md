---
status: active
updated: 2026-11-18
owner: project-maintainers
---

# Portfolio construction (Plan 7, phase P5) implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Combine several run outputs into one portfolio run output, with equal-weight or inverse-volatility sleeves on one long-only cash account with no leverage. The combination must reproduce from its component run ids, reconcile to them, and count as a trial.

**Architecture:**
- **Combiner:** a pure function in `research/evaluation/portfolio.py` reads component run outputs and writes a standard `run-output/v1` with `engine: "combiner"`.
- **Command:** `scripts/portfolio.py` loads components by id, records the trial, writes the run, and produces a diversification report.
- **No engine change:** the combiner works on sleeve net returns, not shares.

**Tech Stack:** Python 3.12, pandas, numpy, `unittest`. No new dependencies.

**Spec:**
- [offline research infrastructure design](2026-11-17-offline-research-infra-design.md), the P5 phasing row;
- [goals](../goals.md), row "Research baseline and selection": stock members of a combination inherit the survivor-bias label, a combination needs its own frozen plan and forward window, and the number of combinations tried counts as trials;
- [conventions](../conventions.md);
- the approved master plan (Plan 7 block).

## Global Constraints

- **Account rules:** long-only; weights are ≥ 0 and sum to at most `gross` (default and maximum 1.0), so there is no leverage. Cash is whatever is not allocated, and it earns zero (disclosed, as everywhere).
- **Sleeve model:** a sleeve contributes its own run's `net_return` series, which is already net of its trading costs. The combiner is a sleeve-level model, not a share-level portfolio: positions in the output are sleeves, and `quantity` is `0` by definition.
- **Layers:** the combiner lives in `research/evaluation` (imports `run_output`, `metrics`); registry and ledger access happens in `scripts/portfolio.py`. No pinned-file edits, no new dependencies, tests offline and under 30 s each.
- **Outputs:**
  - Exclusive create, never overwritten.
  - A combined run is a `run-output/v1` in the runs root, with an optional `combination` manifest key. A report goes under `<data root>/portfolio/<id>/report.json` (`portfolio-report/v1`, catalogued).
- **Labels:**
  - If any component carries `labels` or `universe_kind`, the combination inherits the union (stock members inherit the survivor-bias label).
  - `use` is `financial` only if every component is `financial`; otherwise the combination is `engineering`.
- **Trials:** each combination run counts as a trial. `scripts/portfolio.py combine` requires `--cycle-id` (records one ledger trial through `research.control.trial_ledger`) or `--exploratory` (records none, and the manifest says `exploratory: true`). Tests use a temporary ledger directory. The plan's real-data demonstration uses `--exploratory`, so no trial is written to the tracked ledger.
- **Docs:** follow `docs/README.md`.

## Decisions (controller rulings, binding)

- **Alignment:** all components must have identical date sets. A mismatch is an error naming the first differing dates. There is no silent intersection.
- **Weights:**
  - `equal`: `w_i = gross / n`.
  - `inverse_vol`: `w_i ∝ 1 / σ_i`, where `σ_i` is the sample standard deviation (ddof 1) of component `i`'s `net_return` over the trailing `vol_window` sessions (default 60) **ending the session before** the rebalance (causal). Before `vol_window` sessions exist, the weights are equal. A zero or non-finite σ is an error naming the component. The weights are normalised to sum to `gross`.
- **Rebalancing:** on the first session, and then on the first session of each calendar month (`rebalance: "monthly"`) or every session (`"daily"`). Between rebalances sleeve weights drift with their returns: `w_i ← w_i (1 + r_i) / (1 + r_p)` for the sleeve weights, with cash staying a fixed fraction of the starting equity within drift, treated as an additional zero-return asset.
- **Costs:** a rebalance on session `t` costs `rebalance_cost_bps × Σ|w_target − w_drifted| / 10_000` (fraction of equity), charged on that session, and is added to `cost`. Default `rebalance_cost_bps = 5.0` (the conventions' base level). The first session's allocation is charged the same way from an all-cash start.
- **Returns:** `gross_return_t = Σ_i w_{t−1,i} r_{i,t}` (drifted weights at the start of session `t`, after any rebalance at the close of `t−1`, which is the convention below). `net_return_t = gross_return_t − cost_t`. `equity_t = equity_{t−1} (1 + net_return_t)`, starting from `initial_cash` (default 100,000, the same as the engines).
- **Timing convention:** weights chosen from information up to the close of `t−1` apply to the return of session `t`. A rebalance "on session `t`" means the new weights are computed from data up to `t−1` and apply from `t`. This is stated in the docstring and tested against a hand computation.
- **Output tables:**
  - `returns`: the above.
  - `positions`: one row per sleeve per session: `instrument` is the component's `run_id`, `quantity` is 0, `weight` is the drifted weight at the close.
  - `signals`: `stage` `target_weight` (on rebalance sessions) and `sleeve_vol` (the trailing σ used, inverse-vol only).
  - `fills`: empty (rebalancing is modelled as a cost on returns).
- **Manifest:** `engine: "combiner"`, `engine_version: "combiner/v1"`. `config` is `{method, vol_window, rebalance, gross, rebalance_cost_bps, initial_cash, components: [{run_id, manifest_sha256}]}`, so `config_hash` identifies the combination. `parent_run` is null. `combination` is `{method, components, weights_first_rebalance, exploratory | trial: {cycle_id, trial_number}}`. `datasets` lists each component's `datasets` under its run id, and `labels` and `universe_kind` follow the label rule.
- **Reproducibility:** re-running the combiner on the same component run ids and parameters gives identical tables, so the same `config_hash`. A test asserts this and checks the tables bit for bit.

## Review Focus

1. A combination can never take leverage: with weights summing to at most 1, a sleeve cannot get more than its weight, and cash never goes negative, even when a sleeve's `net_return` is −100% or worse.
2. Inverse-volatility weights must be causal: changing a sleeve's return on session `t` must not change weights chosen for `t` or earlier.
3. A stock sleeve's survivor-bias label must reach the combination's manifest, its report and any listing, and a combination of an engineering run with a financial one is `engineering`.
4. Components with different date sets, a missing run, or a manifest whose hash differs from the one given must be rejected, naming the component.
5. A combination must never be written without either a recorded trial or an explicit `exploratory` flag.

---

### Task 1: Combiner core

**Files:**
- Create: `research/evaluation/portfolio.py`
- Test: `tests/current/test_portfolio.py`

**Interfaces:**
- Consumes: `research/evaluation/run_output.py` (`read_run`, `write_run`, `config_hash`, `new_run_id`, `COLUMNS`) and `research/evaluation/metrics.py`.
- Produces:
  - `METHODS = ("equal", "inverse_vol")`, `REBALANCE = ("monthly", "daily")`, `class PortfolioError(ValueError)`.
  - `@dataclass(frozen=True) class Sleeve: run_id: str; manifest: dict; returns: pd.DataFrame` (the `returns` table).
  - `combine(sleeves: list[Sleeve], method: str, *, gross: float = 1.0, vol_window: int = 60, rebalance: str = "monthly", rebalance_cost_bps: float = 5.0, initial_cash: float = 100_000.0) -> dict[str, pd.DataFrame]`. It returns the four tables, and raises `PortfolioError` for misaligned dates, an unknown method, `gross` outside (0, 1], fewer than two sleeves, or a bad volatility.
  - `build_manifest(sleeves, method, params, tables, now, code_commit, trial=None, exploratory=False) -> dict` returns a manifest that passes `write_run` (`MANIFEST_KEYS` plus `combination` and the optional label keys).
  - `reconcile(tables, sleeves, ...) -> dict`: recomputes the portfolio return from the position weights and the sleeve returns, and returns `{max_abs_return_error, weights_sum_max, cash_min, cost_total}`.

- [ ] **Step 1: Write the failing tests:**
  - `test_equal_weight_hand_computed` (3 sessions, 2 sleeves, known returns, daily rebalance, 0 cost: every number checked);
  - `test_drift_between_monthly_rebalances` (weights drift, then reset on the first session of the next month);
  - `test_rebalance_cost_charged_on_turnover`;
  - `test_inverse_vol_hand_computed_and_equal_before_window`;
  - `test_inverse_vol_is_causal` (Review Focus 2: change session `t`'s return, and weights through `t` are unchanged);
  - `test_no_leverage_and_cash_never_negative` (Review Focus 1: a sleeve returning −100% and one returning +300%);
  - `test_misaligned_dates_rejected_naming_first_difference` (Review Focus 4);
  - `test_gross_validation_and_fewer_than_two_sleeves`;
  - `test_zero_volatility_sleeve_named_in_error`;
  - `test_combination_is_reproducible_bit_for_bit`;
  - `test_output_tables_pass_write_run_and_read_run` (a temp runs root);
  - `test_reconcile_matches_returns`.
- [ ] **Step 2: Run them.** `<python> -m unittest tests.current.test_portfolio -v`. Expected: FAIL (module not found).
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the tests and `make check`.
- [ ] **Step 5: Commit:** "Portfolio combiner core".

### Task 2: Command, trials, labels and report

**Files:**
- Create: `scripts/portfolio.py` (`combine` and `report`), `research/registry/artifacts.json` entry `portfolio-report/v1` (implemented; also update the `combination` note on `run-output/v1` if the catalog mentions it; re-render)
- Test: `tests/current/test_portfolio_cli.py`

**Interfaces:**
- Consumes: Task 1; `research/control/trial_ledger.py` (`TrialLedger(dir).trial(cycle_id, description)`; read it for the exact API and error behaviour); `research/data/root.py` (`runs_root`, `data_root`).
- Produces:
  - `scripts/portfolio.py combine --run-id ID ... --method equal|inverse_vol [--gross --vol-window --rebalance --rebalance-cost-bps --initial-cash] (--cycle-id ID | --exploratory) [--runs-root --ledger-dir --root]`:
    - Each component is loaded with `read_run`, which verifies every hash.
    - Component `manifest_sha256` values are computed from the files and recorded.
    - Exactly one of `--cycle-id` and `--exploratory` is required.
    - It records a ledger trial before writing the run, and the trial number goes in the manifest.
    - Labels and `use` follow the rule above.
    - It prints the new run id.
  - `scripts/portfolio.py report --run-id ID [--root]` writes `<root>/portfolio/<run id>/report.json` (`portfolio-report/v1`) with exclusive create. It holds:
    - per-sleeve and combined metrics (`summarize`);
    - the correlation matrix of sleeve `net_return`;
    - diversification ratio and the share of risk (variance contribution) per sleeve;
    - the reconciliation from Task 1;
    - labels, `use`, the trial info, and a plain-language limitations note ("sleeve-level model; cash earns zero; costs are rebalance turnover only; sleeve returns already include their own costs").

- [ ] **Step 1: Write the failing tests** (temp roots; fixture component runs written with `write_run` from `synthetic_fixture` screening results or small hand-built returns):
  - `test_combine_writes_run_with_combination_manifest`;
  - `test_requires_cycle_id_or_exploratory` (Review Focus 5, both missing and both given);
  - `test_trial_recorded_in_ledger_and_manifest` (a temp ledger directory; the trial count increases by exactly 1);
  - `test_exploratory_records_no_trial_and_says_so`;
  - `test_stock_label_inherited` and `test_engineering_plus_financial_is_engineering` (Review Focus 3);
  - `test_missing_run_and_tampered_manifest_rejected_naming_component` (Review Focus 4);
  - `test_report_has_metrics_correlation_diversification_and_reconciliation`;
  - `test_report_is_exclusive`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the tests and `make check`. Do not write to the tracked trial ledger in tests (a temp `--ledger-dir`) and never use `--cycle-id` against the real ledger.
- [ ] **Step 5: Commit:** "Portfolio command, trial counting, labels and report".

### Task 3: Real-data demonstration and records

**Files:**
- Create: `docs/tasks/2026-11-18-portfolio.md` (task record), `docs/tasks/evidence/2026-11-18-portfolio.json`, analysis specs `research/registry/analysis-specs/portfolio-sleeve-etf-trend.json` and `portfolio-sleeve-stock-trend.json`
- Modify: `docs/data-library.md` only if a portfolio folder is added to the layout, the design P5 row, `docs/roadmap.md` step 9, `docs/conventions.md` (the combination conventions: sleeve model, trial rule), `docs/workflow.md` (a short pointer), `research/registry/readiness.json` (P2 portfolio construction, and any other aspect this plan completes; each at most +1, cited; then re-render), `scripts/current/research_index.py --write`
- Test: `make check`

- [ ] **Step 1: Make the sleeves.** All use the real data root and write run outputs only:
  - `incumbent`: the costs-rung run of the existing clean incumbent analysis (cite its id from `docs/tasks/evidence/2026-11-18-incumbent-rebuild.json`), if its date set is identical to the others, otherwise re-run it through the sector-ETF dataset spec;
  - an ETF sleeve: `sma_trend` on the sector-ETF dataset (SPY and the ten sector ETFs);
  - a stock sleeve: `sma_trend` on `spy-equities-2016-2025-n2` (screening, engineering use, with the survivor-bias labels).

  Write the two sleeve specs by copying the structure of `research/registry/analysis-specs/fixture-ladder.json`, and run them with `scripts/analysis.py run --spec ... ` (engineering). If the date sets differ between datasets, report it and stop at the alignment error rather than loosening the rule.
- [ ] **Step 2: Combine** with `scripts/portfolio.py combine --exploratory` twice: `equal` and `inverse_vol`, then `report` for each. Re-run the equal one with the same components and parameters in a temporary runs root to prove bit-for-bit reproducibility (compare table hashes and `config_hash`).
- [ ] **Step 3: Write the records:**
  - the task record, with per-sleeve and combined metrics, the correlation matrix, the diversification figures, the reconciliation error, the labels (stock sleeve → survivor-biased, discovery-only), `use: engineering`, and `exploratory`;
  - say explicitly that the numbers are a demonstration of the mechanism, not a research finding, and that no trial was recorded in the tracked ledger;
  - the evidence JSON (no prices);
  - the design P5 row, roadmap, conventions, workflow pointer and readiness.
- [ ] **Step 4: Run** `scripts/current/research_index.py --write` and `make check`.
- [ ] **Step 5: Commit:** "Portfolio demonstration and records".
