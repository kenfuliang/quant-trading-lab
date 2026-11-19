---
status: active
updated: 2026-11-18
owner: project-maintainers
---

# S&P 500 stock layer (Plan 5, phase P3) implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing 500-stock archive usable for honest offline research. It needs:
- corporate actions;
- a quality-checked dataset;
- point-in-time S&P 500 membership;
- instrument identity across ticker changes;
- coverage per date;
- a survivor-bias label on every stock result;
- a liquidity-scaled cost model in both engines;
- a measured 500-name runtime.

**Architecture:**
- **Raw snapshots:** two new receipted snapshots go to the data root, one from Yahoo (stocks) and one from GitHub (membership sources). Both reuse the Plan 3 receipt and manifest pattern.
- **Data-layer builders** turn them into an actions file (etf-normalise format), a `membership/v1` table and an `instrument-identity/v1` table.
- **The stock dataset** is a normalised manifest over the archive's per-symbol bar files, with the full-window names only. The loader caches the normalised result. It gets a quality report like the ETF set.
- **Point-in-time membership** applies as a strategy-level mask, because `MarketData` keeps one shared session list.
- **Costs:** the cost model becomes per instrument and per session in the shared contract, so both engines stay in parity.

**Tech Stack:** Python 3.12 stdlib (`urllib`, `csv`, `decimal`), pandas, numpy, `unittest`, NautilusTrader 1.231. No new dependencies.

**Spec:**
- [offline research infrastructure design](2026-11-17-offline-research-infra-design.md): section 1 "Point-in-time membership", P3 row, reuse table;
- [goals](../goals.md), the survivor-bias rule at lines 66–78;
- the approved master plan (Plan 5 block);
- the owner ruling of 2026-11-18 authorising the Yahoo stock fetch.

## Global Constraints

- **Network:**
  - Only through `scripts/data.py` fetch commands, each with a receipt.
  - Authorised sources: the Yahoo chart endpoint for the archive's stock symbols, 2016–2025 (owner ruling 2026-11-18, private offline research only, not redistributed); and GitHub (`api.github.com` and `raw.githubusercontent.com`) for `fja05680/sp500`, `hanshof/sp500_constituents`, and an `index-constitution` repository if one can be found.
  - Never retry in a loop. A refused source is recorded as blocked.
- **Data handling:**
  - Raw prices only; adjusted series are for analysis only.
  - Nothing is overwritten or deleted, and writers use exclusive create.
  - New data goes to new folders under the data root (`research/data/root.py`).
- **Layers:** data → data; evaluation → data, features, policies, evaluation, reporting; control → control; commands → everything. No edits to files pinned in `research/compatibility.json` (for example `research/us_stock_library.py`, `research/us_etf_calendar.py`, `reporting/*`); importing them from current code is forbidden by the boundary checker.
- **Survivor bias:** "Until point-in-time S&P 500 membership is qualified from free data (D3), stock-selection results are labeled survivor-biased and discovery-only and cannot clear G2" ([goals](../goals.md)). Every stock analysis and receipt carries `labels: ["survivor-biased", "discovery-only"]`, whatever coverage says, because former members' prices are out of scope.
- **Tests and docs:** tests are offline, using committed fixtures under `tests/fixtures/`, and each test stays under 30 s. Docs follow `docs/README.md`. Schema ids must be catalogued.

## Decisions (controller rulings from the code survey, binding)

- **Stock universe for runs:**
  - The 459 symbols whose coverage status is `structural_full_window` in `<data root>/normalized/spy-equities-2016-2025-v1-coverage.csv`.
  - `MarketData` needs one shared session list, so the 41 partial-window and 3 unavailable symbols are excluded and listed in the dataset manifest notes and the coverage report.
  - The dataset id is `spy-equities-2016-2025-n1`, with `universe_kind: "current-holdings-proxy"`.
- **Corporate actions from Yahoo chart events:**
  - **Splits:** each event's `numerator`/`denominator`. An integer forward ratio ≥ 2 becomes a split record. A symbol with any other split (reverse, or a non-integer like 3:2) is **excluded** from the dataset with that reason.
  - **Dividends:** Yahoo's dividend amounts are adjusted for later splits. Un-adjust each one by multiplying by the product of the ratios of that symbol's splits dated after the ex-date. A test pins a constructed 4:1 case.
  - **Pay date:** Yahoo gives no pay date, so `pay_date = ex_date`, labelled `pay_date_unknown_credited_on_ex_date`. It is an exception in the quality report.
  - **Output:** `<data root>/normalized/spy-equities-2016-2025-actions-yahoo-<snapshot>.json`, in the etf-normalise actions format (`cash_and_in_kind`, `splits`).
- **Membership (`membership/v1`):**
  - Source: the fja05680 historical-components CSV (date plus a comma-separated ticker list per row).
  - Stored as per-symbol intervals `[{symbol, start, end | null}]`, where `end` is the last date the symbol is in the list. The file lives in the data root (`location: local`) and has a manifest that records the MIT licence text's hash.
  - Cross-checks: hanshof and index-constitution membership on the first trading day of each year from 2016 to 2025. Each disagreement is listed. A source that cannot be found or fetched makes its cross-check `blocked`.
  - Spot checks, each expected value stated in the test-like check (a mismatch is a finding, not tuned): TSLA in from 2020-12-21; FB present before 2022-06-09 and META from 2022-06-09, with one identity; AAPL present throughout 2016–2025.
- **Identity (`instrument-identity/v1`):**
  - `instrument_id` is the issuer identifier from the holdings workbook (in the archive manifest `universe.equities`) for current members.
  - Historical-only symbols get `sym:<SYMBOL>`.
  - Ticker changes come from a committed, sourced, curated file `research/registry/ticker-changes.json` (`[{old, new, date, source_url}]`). It starts with FB→META 2022-06-09, and others found in the membership data are added only with a cited source.
  - The identity table maps every symbol to one id with dated symbol intervals.
- **Membership in runs:** `members_only(target_fn, intervals_by_symbol)` (evaluation) sets the targets of non-members to 0 on each decision date, and records how many names it masked as a signal stage `universe`. The intervals are passed in as plain data by the command.
- **Cost model:**
  - `MarketConfig` gains `cost_model: "flat" | "adv" = "flat"` and `adv_tiers: tuple[tuple[float, float], ...] = ((1e9, 2.0), (1e8, 5.0), (2e7, 10.0), (0.0, 25.0))`, read as (minimum average daily dollar volume, bp).
  - ADV is the median of close × volume over the 20 sessions **before** the decision session; with fewer than 20, the 25 bp tier applies.
  - The shared function `cost_bps(data, instrument, i, config) -> float` lives in `market_model`. Both engines use it for the fill at session i+1 based on data up to i.
  - `flat` keeps today's behaviour exactly, so the existing parity tests, goldens and receipts are unchanged.

## Review Focus

1. A split delivered in Yahoo's split-adjusted units must not corrupt raw-price backtests. The dividend un-adjustment and the reverse/non-integer exclusion are tested, and the stock quality report's `gaps` check shows no unexplained jumps on split dates.
2. Point-in-time masking must be causal: membership on the decision date only, never a later date.
3. The ADV cost tier must use only sessions before the decision date. A lookahead check with `cost_model="adv"` passes.
4. Every stock analysis must show the survivor-bias label on its output, its report and the dashboard. A stock result without it is a defect.
5. Re-running any fetch or build never overwrites data. A partially failed fetch is visible in its manifest and receipt.

---

### Task 1: Stock corporate actions from Yahoo

**Files:**
- Create: `research/data/stock_actions.py`, `tests/fixtures/data/yahoo-chart-SPLITCO.json` (dividends before and after a 4:1 split, plus a reverse-split symbol fixture)
- Modify: `scripts/data.py` (`fetch-yahoo` accepts `--symbols-file`; new `stock-actions` subcommand), `research/data/yahoo_snapshot.py` only if a symbols-file helper belongs there
- Test: `tests/current/test_stock_actions.py`

**Interfaces:**
- Consumes: `research/data/yahoo_snapshot.py` (`fetch_snapshot`, `parse_chart`), `research/data/manifest.py` (`write_manifest`, `read_manifest`), `research/data/root.py`.
- Produces:
  - `build_stock_actions(snapshot_manifest: dict, root: Path) -> tuple[dict, list[dict]]` returns (an actions document in etf-normalise format, a list of excluded symbols with reasons).
  - `scripts/data.py stock-actions --snapshot <id> --out <relative path>` writes the actions file with exclusive create and prints counts.

- [ ] **Step 1: Write the failing tests:**
  - `test_dividends_are_unadjusted_for_later_splits` (Review Focus 1);
  - `test_reverse_and_fractional_splits_exclude_symbol`;
  - `test_pay_date_equals_ex_date_with_label`;
  - `test_output_loads_with_etf_normalise` (the fixture bars plus the generated actions pass `normalise`).
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the tests and `make check`. Then run the live fetch:
  `scripts/data.py fetch-yahoo --symbols-file <data root>/normalized/spy-equities-2016-2025-v1-coverage.csv --start 2016-01-01 --end 2025-12-31 --snapshot-id yahoo-spy-equities-2016-2025-20261118`.
  - It uses the symbol column, all 503 symbols, and the owner-ruling rights block.
  - Some symbols may fail; record which. No retry loop.

  Then run `stock-actions`. Report the counts of splits, dividends and excluded symbols.
- [ ] **Step 5: Commit:** "Stock corporate actions from Yahoo snapshots".

### Task 2: Stock dataset, cached loading and quality report

**Files:**
- Modify:
  - `scripts/data.py`: `normalise` accepts `--bars-dir` with `--symbols-from <coverage csv> --status structural_full_window`, plus `--universe-kind`;
  - `research/evaluation/datasets.py`: load multi-file inputs; a verified normalised cache under `<root>/cache/<manifest_sha>/` (Parquet), rebuilt when missing and never trusted without a hash check;
  - `research/evaluation/data_quality.py`, only for a `universe` check that lists excluded symbols, as an `exception`.
- Test: `tests/current/test_stock_dataset.py`

**Interfaces:**
- Consumes: Task 1's actions file; `etf_normalise.normalise`; `data_quality.build_report`; `manifest`.
- Produces:
  - The manifest `spy-equities-2016-2025-n1`: inputs are every included symbol's bar file plus the actions file; `recipe: etf-normalise/v1`; `universe_kind`; the excluded symbols in `notes`.
  - `load_dataset` provenance gains `universe_kind`.

- [ ] **Step 1: Write the failing tests:**
  - `test_multi_file_manifest_round_trip` (fixture: 3 per-symbol files);
  - `test_cache_is_used_and_verified` (a tampered cache file is rebuilt, not trusted);
  - `test_universe_kind_in_provenance`;
  - `test_excluded_symbols_listed_in_report`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the tests and `make check`. Then build the real dataset and its quality report against the Yahoo stock snapshot. Report:
  - the status and every check's count;
  - cross-source breaches per symbol (top 10);
  - `gaps` items on split dates (they should be 0; otherwise investigate before going on);
  - the time of a cold load and a cached load.
- [ ] **Step 5: Commit:** "Stock dataset with cached loading and quality report".

### Task 3: Membership snapshot and table

**Files:**
- Create: `research/data/github_snapshot.py` (receipted GETs of named URLs, the same receipt and manifest pattern as `yahoo_snapshot`), `research/data/membership.py`, `tests/fixtures/data/sp500-components-sample.csv`
- Modify: `scripts/data.py` (`fetch-github`, `membership`), `research/registry/artifacts.json` (`membership/v1` implemented, `location: local`, real producer and consumers; re-render)
- Test: `tests/current/test_membership.py`, `tests/current/test_github_snapshot.py`

**Interfaces:**
- Produces:
  - `fetch_urls(urls: dict[str, str], snapshot_id, root, opener=urllib.request.urlopen, now=None) -> Path` (name → URL; GitHub hosts only).
  - `SCHEMA = "membership/v1"`.
  - `parse_components(csv_text) -> dict[str, list[dict]]` (symbol → intervals).
  - `membership_on(intervals, day) -> set[str]`.
  - `cross_check(intervals, other_by_date: dict[str, set[str]]) -> dict`.
  - `write_membership(root, doc) -> Path`.

- [ ] **Step 1: Write the failing tests:**
  - `test_intervals_from_sample_csv` (add, remove, re-add);
  - `test_membership_on_is_point_in_time` (Review Focus 2);
  - `test_cross_check_lists_disagreements`;
  - `test_github_fetch_receipts_and_host_allowlist` (a non-GitHub URL is refused before any request).
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Find the fja05680 CSV file name through the GitHub contents API, then fetch the CSV and the `LICENSE` (one request each).
  - **hanshof:** find and fetch the constituent file the same way.
  - **index-constitution:** search once via `api.github.com/search/repositories?q=index-constitution`. Use a match only if it holds S&P 500 constituents; otherwise mark the cross-check blocked.
- [ ] **Step 4: Run** the tests and `make check`. Then fetch, build the membership table, and run the cross-checks and spot checks. Report:
  - the interval count;
  - members on 2016-01-04 and on 2025-12-31 (expected about 500–505 each);
  - the cross-check disagreements;
  - the spot-check results.
- [ ] **Step 5: Commit:** "Point-in-time S&P 500 membership".

### Task 4: Instrument identity, coverage, masking and survivor labels

**Files:**
- Create: `research/data/identity.py`, `research/registry/ticker-changes.json`, `research/evaluation/universe.py`
- Modify:
  - `scripts/data.py`: `identity` and `coverage` subcommands;
  - `research/evaluation/analysis_output.py` and `scripts/analysis.py`: a `labels` field set from the provenance's `universe_kind`; a spec may name `membership` for masking;
  - `research/control/analysis_view.py`: shows labels;
  - `research/registry/artifacts.json`: `instrument-identity/v1` implemented; re-render.
- Test: `tests/current/test_identity.py`, `tests/current/test_universe.py`, additions to `tests/current/test_analysis_cli.py` and `test_analysis_view.py`

**Interfaces:**
- Produces:
  - `SCHEMA = "instrument-identity/v1"`.
  - `build_identity(archive_manifest, membership, ticker_changes) -> dict`, which maps `instrument_id` to symbol intervals.
  - `resolve(identity, symbol, day) -> str | None`.
  - `coverage(membership, identity, dataset_symbols, sessions) -> dict`: per date, `{in_index, with_data, share}`, plus a summary of minimum, median and the worst dates.
  - `members_only(target_fn, intervals) -> TargetFn`.
  - `LABELS = ("survivor-biased", "discovery-only")`.

- [ ] **Step 1: Write the failing tests:**
  - `test_fb_meta_one_identity`;
  - `test_resolve_by_date`;
  - `test_coverage_per_date`;
  - `test_members_only_masks_non_members_causally` (Review Focus 2);
  - `test_stock_analysis_carries_labels_in_json_report_and_page` (Review Focus 4);
  - `test_etf_analysis_has_no_stock_labels`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the tests and `make check`. Then build identity and coverage on the real data. Report the coverage summary: the share of index members with data, its minimum and median, and the worst date.
- [ ] **Step 5: Commit:** "Instrument identity, coverage, membership masking and survivor labels".

### Task 5: Liquidity-scaled cost model in both engines

**Files:**
- Modify: `research/evaluation/market_model.py` (`MarketConfig` fields; `cost_bps`), `research/evaluation/engine_contract.py` (`check_config` validates the tiers), `research/evaluation/screening_engine.py`, `research/evaluation/native_engine.py` (quotes per instrument and session from `cost_bps`), `research/evaluation/parity_fixture.py` only if the fixture needs varied volumes
- Test: `tests/current/test_cost_model.py`, additions to `tests/current/test_engine_parity.py`

**Interfaces:**
- Produces: `cost_bps(data: MarketData, instrument: str, i: int, config: MarketConfig) -> float`, computed causally from sessions i−20 … i−1 and applied to the fill at i+1.

- [ ] **Step 1: Write the failing tests:**
  - `test_flat_model_unchanged` (the existing parity results are identical);
  - `test_adv_tiers_and_short_history`;
  - `test_adv_uses_only_prior_sessions` (Review Focus 3: changing session i's volume does not change bps at i);
  - `test_engines_agree_with_adv_costs` (parity on the fixture with varied volumes crossing at least two tiers);
  - `test_lookahead_passes_with_adv_costs`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the tests and `make check`, including the golden and parity checks.
- [ ] **Step 5: Commit:** "Liquidity-scaled cost model in both engines".

### Task 6: 500-name performance, timing benchmark and records

**Files:**
- Modify: `research/evaluation/market_model.py` (`history_view` without per-session full DataFrame copies), engine hot loops as needed (`sessions.index` lookups, per-session scans of all actions), `scripts/current/engine_parity.py` (`--max-instruments`, and a `--timing-only` that records timing without a financial claim)
- Create: `docs/tasks/2026-11-18-stock-layer.md` (task record), `docs/tasks/evidence/2026-11-18-stock-layer.json`
- Modify: `docs/data-library.md`, the design P3 row, `docs/roadmap.md` step 5, `research/registry/readiness.json` (D3, D4, R2, N4; each at most +1, cited; re-render)
- Test: existing parity, lookahead and golden tests must pass unchanged. Add `test_history_view_matches_reference` (the new view equals the old construction on the fixture at every session).

- [ ] **Step 1: Write the failing test** `test_history_view_matches_reference` (against a reference copy of the current implementation in the test). Run it: it passes, as a guard. Then time `run_screen` on 459 names × 2,514 sessions with `sma_trend_targets` as the baseline. If it takes over 10 minutes, time 50 names and extrapolate, and say so.
- [ ] **Step 2: Optimise** `history_view` and the engine loops with no change in results. The parity, lookahead, golden and incumbent-rebuild summaries must be bit-identical; re-run the incumbent spec with `--root` in a temp dir to check. Target: screening on 459 names under 5 minutes.
- [ ] **Step 3: Benchmark** on the real stock dataset:
  - screening on 459 names with flat and `adv` costs, and with membership masking;
  - native on 20 names, extrapolated to 459;
  - real-data parity on 20 names with `adv` costs, receipt in the parity root.

  Record the timings and the parity status.
- [ ] **Step 4: Write the records:**
  - the task record: actions counts, the quality report, membership cross-checks and spot checks, identity, coverage, cost model, timings, parity, and the survivor-bias statement;
  - the evidence JSON (no prices);
  - data-library, design P3, roadmap step 5 and readiness.

  Run `research_index.py --write` and `make check`.
- [ ] **Step 5: Commit:** "Stock layer performance, timing benchmark and records".
