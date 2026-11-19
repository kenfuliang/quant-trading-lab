---
status: active
updated: 2026-11-18
owner: project-maintainers
---

# ETF data layer (Plan 3, phase P1a) implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a frozen, receipted and quality-checked ETF dataset that loads into `MarketData`, so real-data engine parity runs, and give every worktree one shared data root.

**Architecture:**
- New modules go under `research/data/`, with one command, `scripts/data.py`.
- Raw inputs are never edited. A normalised dataset is a manifest naming its inputs
  (with SHA-256) and a versioned recipe. It is applied on load, so no derived price file
  is written.
- Quality reports and Yahoo snapshots live under the shared data root.
- Pinned legacy modules are reused read-only.

**Tech Stack:** Python 3.12 standard library (`urllib`, `decimal`, `socket`), pandas, `unittest`. No new dependencies.

**Spec:**
- [offline research infrastructure design](2026-11-17-offline-research-infra-design.md), sections "1. Data layer" and the P1a phasing row;
- the approved master plan of 2026-11-18 (Plan 3 block, summarised in Decisions).

## Global Constraints

- **Data handling:**
  - Raw prices only; adjusted series are for analysis and cross-checks.
  - Signals at close *t*, fills at open *t*+1. Cash dividends are credited on the pay date,
    splits are applied to held quantity, and shares are whole.
  - Nothing is overwritten or deleted. Writers use exclusive create (`open("x")`,
    `mkdir(exist_ok=False)`).
- **Scope:**
  - Do not edit files pinned in `research/compatibility.json`. That includes
    `research/us_etf_calendar.py`, `research/us_stock_library.py` and
    `research/sector_etf_acquisition.py`; they may be imported.
  - Tests are offline and use committed fixtures under `tests/fixtures/data/`.
  - Network is used only by `scripts/data.py fetch-yahoo`, and every request is receipted.
  - No broker operations or orders.
- **Yahoo rights block (exact):** `{"source": "yahoo", "use": "private offline research only", "redistribution": "not permitted", "ruling": "owner 2026-11-17"}`.
- **Schema ids:** `dataset-manifest/v1`, `quality-report/v1`. Recipe ids: `etf-normalise/v1`, `adjust/v1`. Each `SCHEMA` constant must be catalogued in `research/registry/artifacts.json`, or `make check` fails.
- **Data root:** `QTL_DATA_ROOT` if set; otherwise `<main checkout>/data`, where the main checkout is the parent of `git rev-parse --git-common-dir`.
- **Data absent:** a real-data command whose inputs are missing prints `blocked: data absent: <path>` and exits 2.
- **Docs:** follow `docs/README.md`.

## Decisions (approved master plan, binding)

- **Sub-cent prices:**
  - OHLC are rounded half-even to the cent with `decimal`.
  - Every changed value is counted per instrument and field. Volume is unchanged.
  - A price that rounds to ≤ 0 is an error.
- **XLF in-kind distribution 2016-09-19:**
  - It becomes a cash-equivalent dividend: `per_share = round(ratio × child close on ex_date, 6)`, paid on its `pay_date`, labelled `in_kind_cash_equivalent`.
  - For XLF this is 0.139146 × 32.24 (XLRE close on 2016-09-19) = **4.486067**.
  - A child with no bar on the ex-date is an error.
- **Window rule:** a cash event whose `ex_date` or `pay_date` is not a bar session is excluded and listed (known case: SPY ex 2025-12-19, pay 2026-01-30).
- **Quality statuses:**
  - Each check is `pass`, `fail`, `exception` or `blocked`.
  - The report is `fail` if any check fails, else `pass-with-exceptions` if any check is `exception` or `blocked`, else `pass`.
  - `acceptance: {"accepted_by": null, "accepted_utc": null}` is left for the owner.
- **Cross-source:**
  - Yahoo `close` is split-adjusted. Un-adjust it by multiplying by the product of the ratios of our splits whose effective date is after the day.
  - Tolerance is `max(0.01, 5 bp × alpaca close)`.
  - Breaches are an `exception` with count, max and p99. A missing Yahoo snapshot makes the check `blocked`.
- **Gaps:** a close-to-close move over 25 % with no action that day is an `exception`.
- **Continuous run:** the owner authorised a continuous multi-plan run on 2026-11-18. `docs/workflow.md` records that the per-plan checkpoint becomes a per-plan report while such an authorisation stands.

## Review Focus

1. Re-running `fetch-yahoo`, `normalise` or `quality` must never overwrite an existing snapshot, manifest or report. A new run writes a new folder or fails.
2. An input file whose SHA-256 no longer matches its manifest must be refused at load, naming the file.
3. A Yahoo HTTP error, or a response with `chart.error`, must leave a `failed` receipt row and no file that looks like a good snapshot.
4. Rounding must never turn a positive price into 0 or break OHLC consistency. If it would, the normaliser raises.
5. The network guard blocks non-loopback connections but lets loopback servers (dashboard and preview tests) work.

---

### Task 1: Shared data root and the continuous-run workflow note

**Files:**
- Create: `research/data/__init__.py`, `research/data/root.py`
- Modify: `scripts/current/engine_parity.py` (`--out` and `--runs` default to `parity_root()` and `runs_root()`), `Makefile` (`parity-local` drops the hard-coded `.local` paths), `docs/workflow.md` (continuous-run authorisation rule)
- Test: `tests/current/test_data_root.py`, `tests/current/test_engine_parity_cli.py` (one new test)

**Interfaces:**
- Produces:
  - `data_root(cwd: Path | None = None) -> Path`
  - `runs_root(cwd=None) -> Path` (`<root>/runs`)
  - `parity_root(cwd=None) -> Path` (`<root>/parity`)
  - `class DataAbsent(RuntimeError)`
  - `require(path: Path) -> Path`, which raises `DataAbsent(f"blocked: data absent: {path}")`

- [ ] **Step 1: Write the failing tests:**
  - `test_env_var_wins`;
  - `test_worktree_resolves_main_checkout_data`, using `git init` plus `git worktree add` in a temporary directory;
  - `test_main_checkout_resolves_its_own_data`;
  - `test_require_raises_blocked_message`;
  - `test_engine_parity_defaults_to_data_root`, with `QTL_DATA_ROOT` set to a temp dir and the injected loader;
  - `test_missing_inputs_exit_2_with_blocked_message`.
- [ ] **Step 2: Run them.** `<python> -m unittest tests.current.test_data_root -v`. Expected: FAIL (module not found).
- [ ] **Step 3: Implement.**
  - Resolve the main checkout with `git rev-parse --git-common-dir`, run from `cwd`, made absolute.
  - Outside git, fall back to `<repo root>/data`.
  - In `engine_parity`, inputs that do not exist print the blocked message and return 2.
  - Add to `docs/workflow.md`: "The owner may authorise a continuous multi-plan run; while it stands, the per-plan checkpoint is replaced by a per-plan report (PR link, rulings, deferred minors, score changes). Stops for destructive actions, credentials, new dependencies and refused external sources still apply."
- [ ] **Step 4: Run** the tests, then `make check`. Expected: pass.
- [ ] **Step 5: Commit:** "Shared data root and continuous-run rule".

### Task 2: No-network guard in the test runner

**Files:**
- Modify: `scripts/run_tests.py`
- Test: `tests/current/test_run_tests.py`

**Interfaces:**
- Produces:
  - `install_network_guard() -> None`, called by `main` before discovery. It wraps `socket.socket.connect` and `connect_ex`.
  - An `AF_INET`/`AF_INET6` address outside `127.0.0.0/8` and `::1` raises `NetworkBlocked(OSError)` with `"network access blocked in tests: <host>:<port>"`.
  - `AF_UNIX` and loopback addresses pass.

- [ ] **Step 1: Write the failing tests** (each runs the runner as a subprocess on a temporary test module):
  - `test_non_loopback_connection_fails_naming_test`: the module calls `socket.create_connection(("192.0.2.1", 80), timeout=0.5)`. Expected: exit 1, the output names the test and contains `network access blocked`.
  - `test_loopback_server_allowed`: the module serves `http.server` on 127.0.0.1:0 and fetches it. Expected: exit 0.
- [ ] **Step 2: Run them.** Expected: the first FAILs (a timeout error, not the guard message).
- [ ] **Step 3: Implement** the guard.
- [ ] **Step 4: Run** the tests, then `make check`. The whole suite must stay green; any test that needed the network is a finding to report, not something to skip.
- [ ] **Step 5: Commit:** "Block non-loopback network in tests".

### Task 3: Dataset manifest and Yahoo raw snapshot collector

**Files:**
- Create: `research/data/manifest.py`, `research/data/yahoo_snapshot.py`, `scripts/data.py`, `tests/fixtures/data/yahoo-chart-XLB.json` (a small hand-made chart response: 5 sessions, one dividend, one 2:1 split)
- Modify: `research/registry/artifacts.json` (`dataset-manifest/v1` → implemented, with the real producer and consumers; re-render `docs/artifacts.md`)
- Test: `tests/current/test_data_manifest.py`, `tests/current/test_yahoo_snapshot.py`

**Interfaces:**
- Produces:
  - In `manifest.py`:
    - `SCHEMA = "dataset-manifest/v1"`, `class ManifestError(ValueError)`.
    - `KINDS = ("raw-snapshot", "normalised")`.
    - Manifest keys `{schema, dataset_id, kind, created_utc, source, inputs: [{path, sha256}], recipe, rights, files: [{path, sha256}], notes}`. `recipe` is null for raw snapshots, and paths are relative to the data root.
    - `write_manifest(root: Path, manifest: dict) -> Path` writes `<root>/manifests/<dataset_id>.json` with exclusive create.
    - `read_manifest(root: Path, dataset_id: str, verify: bool = True) -> dict`. It validates keys and kind. With `verify`, it recomputes every `inputs` and `files` SHA-256 and raises `ManifestError("<path>: sha256 mismatch")` or `("<path>: missing")`.
  - In `yahoo_snapshot.py`:
    - `chart_url(symbol: str, start: str, end: str) -> str`: `https://query1.finance.yahoo.com/v8/finance/chart/<SYM>?period1=<utc epoch of start>&period2=<utc epoch of end + 1 day>&interval=1d&events=div%2Csplits`.
    - `parse_chart(raw: bytes, symbol: str) -> tuple[pd.DataFrame, list[dict], list[dict]]`. The frame is OHLCV indexed by New York date, plus `dividends` and `splits` lists. It raises `ValueError` on `chart.error`, a symbol mismatch, or duplicate dates.
    - `fetch_snapshot(symbols, start, end, snapshot_id, root, opener=urllib.request.urlopen, now=None) -> Path`:
      - it writes `<root>/raw/yahoo/<snapshot_id>/` holding `response-<SYM>.json` and `requests.json`;
      - each receipt row is `{attempt, symbol, url, utc, status: reserved→received|failed, http_status, bytes, sha256, error}`;
      - it writes the manifest with the exact Yahoo rights block, and `files` lists only received responses;
      - a failed symbol is recorded, not retried, and the command exits 1 after writing the manifest;
      - the request header is a generic `User-Agent: research-snapshot/1` and carries no personal details.
  - `scripts/data.py fetch-yahoo --symbols SPY,XLB,... --start 2016-01-01 --end 2025-12-31 --snapshot-id yahoo-sector-etfs-2016-2025-<YYYYMMDD> [--root]`.

- [ ] **Step 1: Write the failing tests:**
  - `test_manifest_round_trip_and_exclusive_write`;
  - `test_sha256_mismatch_and_missing_file_are_refused` (Review Focus 2);
  - `test_chart_url_epochs`;
  - `test_parse_fixture_dates_dividend_split`;
  - `test_fetch_with_fake_opener_writes_receipt_responses_and_manifest`;
  - `test_http_error_and_chart_error_leave_failed_rows_and_no_response_file` (Review Focus 3);
  - `test_existing_snapshot_id_is_refused` (Review Focus 1).
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Reuse the parsing rules of `research/spy_backtest.py:load_data` (New York date conversion, OHLC checks) without importing that module's backtest code.
- [ ] **Step 4: Run** the tests and `make check`. Then run the live fetch once, outside the tests:
  `<python> scripts/data.py fetch-yahoo --symbols SPY,XLB,XLE,XLF,XLI,XLK,XLP,XLRE,XLU,XLV,XLY --start 2016-01-01 --end 2025-12-31 --snapshot-id yahoo-sector-etfs-2016-2025-20261118`.
  Expected: 11 received rows. If Yahoo refuses (an HTTP 4xx or 5xx on every symbol), keep the failed receipt and report BLOCKED with the receipt path. Do not retry in a loop.
- [ ] **Step 5: Commit:** "Dataset manifest and Yahoo snapshot collector" (code, fixture and catalog only; data files are outside the repo).

### Task 4: Normalisation recipe and own adjustment

**Files:**
- Create: `research/data/etf_normalise.py`, `tests/fixtures/data/etf-bars.json`, `tests/fixtures/data/etf-actions.json`
- Modify: `scripts/data.py` (`normalise` subcommand)
- Test: `tests/current/test_etf_normalise.py`

Fixture: three symbols (`AAA`; `PAR`, which has an in-kind event with child `KID`; and `KID`) over 6 sessions. It includes:
- sub-cent values, including one exact half-cent tie;
- one cash dividend paid after the last session;
- one 2:1 split;
- a parent in-kind event with ratio `0.5` on session 3.

**Interfaces:**
- Consumes: Task 3 `write_manifest`, `read_manifest`. `research/evaluation/market_model.py`: `Dividend`, `Split`, `MarketData`, `MarketDataError`, `validate`, `BAR_COLUMNS`.
- Produces:
  - `RECIPE = "etf-normalise/v1"`, `ADJUST_RECIPE = "adjust/v1"`.
  - `@dataclass(frozen=True) class Normalised: data: MarketData; rounding: dict[str, dict[str, int]]; converted: tuple[dict, ...]; excluded: tuple[dict, ...]`.
  - `normalise(rows: list[dict], actions: dict, instruments: tuple[str, ...]) -> Normalised`:
    - the bar and session rules are those of `research/evaluation/sector_derivative.py` (duplicates, differing session lists, missing instruments);
    - the result passes `validate`.
  - `adjusted_close(data: MarketData) -> dict[str, pd.Series]` is backward-adjusted:
    - closes before a split's effective date are divided by the ratio;
    - closes before a dividend's ex-date are multiplied by `1 - per_share / close on the previous session`.
  - `scripts/data.py normalise --bars <path> --actions <path> --dataset-id <id> [--root]`:
    - it checks that the inputs exist (else the blocked message, exit 2);
    - it runs `normalise` on all symbols to prove the recipe applies;
    - it writes a `normalised` manifest with the input SHA-256s, `recipe: "etf-normalise/v1"` and the rights copied from the Alpaca source manifest (`redistribution: not_qualified`);
    - it prints the rounding, converted and excluded counts.

- [ ] **Step 1: Write the failing tests:**
  - `test_rounds_half_even_and_counts_changes` (the tie goes to the even cent);
  - `test_rounding_to_zero_raises` (Review Focus 4);
  - `test_in_kind_becomes_cash_equivalent_with_pinned_value` (PAR per share = 0.5 × KID close on the ex-date, label `in_kind_cash_equivalent`);
  - `test_missing_child_bar_raises`;
  - `test_event_paid_after_window_is_excluded_and_listed`;
  - `test_result_passes_market_model_validate`;
  - `test_adjusted_close_split_and_dividend_factors` (hand-computed values);
  - `test_normalise_command_writes_manifest_and_blocks_on_absent_input`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the tests and `make check`. Then build the real dataset:
  `<python> scripts/data.py normalise --bars <data_root>/normalized/alpaca-sector-etfs-2016-2025-v1.json --actions <data_root>/normalized/alpaca-sector-etfs-2016-2025-v1-issuer-actions-v2.json --dataset-id sector-etfs-2016-2025-n1`.
  Expected:
  - one converted event, XLF-2016-09-19, with per share 4.486067;
  - the excluded list includes SPY ex 2025-12-19;
  - rounding counts are reported.

  Record the printed counts in the report.
- [ ] **Step 5: Commit:** "ETF normalisation recipe and own adjustment".

### Task 5: Quality report

**Files:**
- Create: `research/data/quality.py`
- Modify: `scripts/data.py` (`quality` subcommand), `research/registry/artifacts.json` (`quality-report/v1` → implemented; re-render)
- Test: `tests/current/test_data_quality.py`

**Interfaces:**
- Consumes:
  - Task 4 `Normalised`, `normalise`;
  - Task 3 `read_manifest`, `parse_chart`;
  - `research/us_etf_calendar.py` `sessions(start, end)` and `clocks(day)` (read-only).
- Produces:
  - `SCHEMA = "quality-report/v1"`.
  - `CHECKS = ("sessions", "half_days", "duplicates", "non_finite", "non_positive", "ohlc", "gaps", "cent_rounding", "actions_converted", "actions_excluded", "cross_source")`.
  - `build_report(dataset_id: str, rows: list[dict], norm: Normalised, yahoo: dict[str, pd.DataFrame] | None, splits: tuple[Split, ...]) -> dict`:
    - the report is `{schema, dataset_id, recipe, created_utc (passed in), status, checks: [{name, status, count, detail, items (≤ 50)}], acceptance}`.
  - `render_report(report: dict) -> str` (Markdown).
  - `scripts/data.py quality --dataset-id <id> [--yahoo <snapshot_id>] [--root]` writes `<root>/quality/<id>/<YYYYMMDDTHHMMSSZ>/report.json` and `report.md` with exclusive create, and prints the status.
- Check outcomes:

  | Check | Outcome |
  | --- | --- |
  | `sessions`: calendar sessions in the bar range against the bar sessions | missing or extra → `fail` |
  | `half_days` | listed, `pass` |
  | `duplicates`, `non_finite`, `non_positive`, `ohlc` (on the source rows) | any → `fail` |
  | `gaps` | `exception` |
  | `cent_rounding` | count > 0 → `exception` |
  | `actions_converted`, `actions_excluded` | non-empty → `exception` |
  | `cross_source` | breaches → `exception`; no snapshot → `blocked` |

- [ ] **Step 1: Write the failing tests:**
  - `test_clean_fixture_passes`;
  - `test_missing_session_fails`;
  - `test_rounding_conversion_and_exclusion_give_pass_with_exceptions`;
  - `test_cross_source_unadjusts_yahoo_splits_before_comparing`;
  - `test_cross_source_without_snapshot_is_blocked`;
  - `test_gap_without_action_is_exception`;
  - `test_report_folder_is_never_overwritten`;
  - `test_markdown_lists_every_exception`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the tests and `make check`. Then run it on the real data:
  `<python> scripts/data.py quality --dataset-id sector-etfs-2016-2025-n1 --yahoo yahoo-sector-etfs-2016-2025-20261118`.
  Expected: `pass-with-exceptions`, with the cross-source breach count, max and p99 recorded. If the Yahoo snapshot was blocked in Task 3, run without `--yahoo` and expect `cross_source: blocked`.
- [ ] **Step 5: Commit:** "Dataset quality report".

### Task 6: Dataset loader, real-data parity and records

**Files:**
- Create: `research/data/datasets.py`
- Modify:
  - `scripts/current/engine_parity.py`: `--dataset <id>`, mutually exclusive with `--bars`/`--actions`. The receipt's `inputs` gains the manifest SHA-256 and the quality report path and status. `calendar.half_days` comes from the quality report.
  - `Makefile`: `parity-local` uses `--dataset $(PARITY_DATASET)`, default `sector-etfs-2016-2025-n1`.
  - `docs/tasks/2026-11-17-engine-parity.md`: the new run and its receipt.
  - `docs/tasks/2026-11-17-offline-research-infra-design.md`: P1a status.
  - `docs/data-library.md`: the data root, raw Yahoo snapshot, normalised manifest and quality layout, and the Yahoo rights ruling.
  - `research/registry/readiness.json`: D1, D2, D5, N5, H6 and R1 critique, evidence and score, each raised by at most 1 with the completed work cited; re-render.
- Test: `tests/current/test_datasets.py`, `tests/current/test_engine_parity_cli.py`

**Interfaces:**
- Consumes: Tasks 1, 3, 4 and 5.
- Produces:
  - `class DatasetBlocked(RuntimeError)`.
  - `latest_report(root: Path, dataset_id: str) -> dict | None`.
  - `load_dataset(dataset_id: str, instruments: tuple[str, ...], root: Path | None = None) -> tuple[MarketData, dict]`:
    - it returns the data plus `{manifest_sha256, quality_status, quality_report}`;
    - it reads and verifies the manifest;
    - it raises `DatasetBlocked` when there is no report or the latest report is `fail`;
    - it re-applies `normalise`, then restricts to `instruments`. The restriction keeps a converted in-kind event whose child is not requested, because the value was computed from the full rows.

- [ ] **Step 1: Write the failing tests:**
  - `test_load_refuses_missing_or_failed_report`;
  - `test_load_refuses_changed_input` (Review Focus 2);
  - `test_load_returns_validated_market_data_and_provenance`;
  - `test_in_kind_value_survives_instrument_restriction`;
  - `test_engine_parity_dataset_mode_records_manifest_and_quality` (fixture dataset under a temp `QTL_DATA_ROOT`, injected engines not needed: run both real engines on the 6-session fixture).
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the tests and `make check`, then:
  - `make parity-local`. Expected: it loads; the receipt status is `passed`, or `mismatch` with mismatches listed. A mismatch is a finding, recorded, not tuned away.
  - Copy (`cp -R`, never move) the worktree's old `.local/parity/*` receipts into `<data_root>/parity/legacy-worktree/`.
  - Update the docs and readiness listed above.
  - `scripts/current/research_index.py --write`, then `make check`.
- [ ] **Step 5: Commit:** "Dataset loader, real-data parity and records".
