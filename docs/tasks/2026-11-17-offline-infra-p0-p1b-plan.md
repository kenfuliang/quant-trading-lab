---
status: active
updated: 2026-11-17
owner: project-maintainers
---

# Run output, two engines and parity (P0 + P1b) implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A standard per-run output, a fast daily screening engine and a NautilusTrader confirmation engine that provably agree on a synthetic fixture inside `make check`, plus a local real-data parity run with a receipt.

**Architecture:** Both engines consume one `MarketData` value and call the *same* target function, so decision code is shared and only execution differs. Each engine returns an `EngineResult` in run-output columns; a comparator checks quantities, fills, cash and equity. New modules live in the `research/evaluation` layer; the command lives in `scripts/current/`.

**Tech Stack:** Python 3.12, pandas 3.1, pyarrow 26 (Parquet), NautilusTrader 1.231.0 (pinned), `unittest`.

**Spec:** [offline research infrastructure design](2026-11-17-offline-research-infra-design.md), sections 2 (run harness) and 3 (run output), phases P0 and P1b.

## Global Constraints

- Both engines trade raw unadjusted prices, credit cash dividends on the payment date and apply splits to held quantities on the effective date. Whole-share rounding is always on.
- Timing: signals use data up to the close of day *t*; orders fill at the open of *t*+1.
- Parity tolerances: identical share quantities and fill dates; cash and equity within $0.01 per session.
- In `make check` parity uses a committed synthetic fixture (a few instruments, about 250 sessions, one split, several dividends). The real-data run is a separate local make target with a receipt.
- A parity run is engineering evidence, not financial use.
- Run outputs live under `.local/runs/<run_id>/`, are never edited after write, and contain `manifest.json`, `returns.parquet`, `positions.parquet`, `signals.parquet`, `fills.parquet`.
- Do not edit files pinned in `research/compatibility.json` or import frozen legacy modules (for example `research/spy_backtest.py`) from new code; reimplement what is needed.
- Ordinary verification stays offline and order-free. No new dependencies (pandera is not adopted in this plan).

## Review Focus

1. A buy that would make cash negative must raise the same `EngineError` in both engines, never be silently skipped or partially filled.
2. An instrument missing a session, or a split falling between a dividend's ex and pay dates, must be rejected when `MarketData` is built, before any engine runs.
3. A split or dividend while the instrument is not held must change nothing in either engine.
4. A target for an unknown instrument or a negative share count must be rejected by both engines.
5. Writing into an existing run directory, or reading a run whose file hash no longer matches, must raise `RunOutputError`.

Each line has a named test in the owning task below.

---

### Task 1: Run output schema, writer and reader (P0)

**Files:**
- Create: `research/evaluation/run_output.py`
- Test: `tests/current/test_run_output.py`

**Interfaces:**
- Produces:
  - `SCHEMA = "run-output/v1"`
  - `COLUMNS: dict[str, tuple[str, ...]]` = `{"returns": ("date", "gross_return", "cost", "net_return", "equity"), "positions": ("date", "instrument", "quantity", "weight"), "signals": ("date", "instrument", "stage", "value"), "fills": ("date", "instrument", "side", "quantity", "price", "cost")}`
  - `MANIFEST_KEYS = ("schema", "run_id", "created_utc", "code_commit", "config", "config_hash", "engine", "engine_version", "datasets", "coverage", "parent_run")`; the writer adds `files: {name: sha256}`.
  - `class RunOutputError(ValueError)`
  - `config_hash(config: dict) -> str` — SHA-256 of `json.dumps(config, sort_keys=True, separators=(",", ":"))`.
  - `new_run_id(config: dict, now: datetime) -> str` — `f"{now:%Y%m%dT%H%M%SZ}-{config_hash(config)[:8]}"`, `now` in UTC.
  - `write_run(root: Path, manifest: dict, tables: dict[str, pd.DataFrame]) -> Path` — writes `root / manifest["run_id"]`.
  - `read_run(path: Path) -> tuple[dict, dict[str, pd.DataFrame]]` — verifies schema, columns and every file hash.

- [ ] **Step 1: Write the failing tests**

```python
def test_round_trip_preserves_tables_and_records_hashes(self):
    path = write_run(self.root, self.manifest, self.tables)
    manifest, tables = read_run(path)
    self.assertEqual(set(manifest["files"]), {"returns", "positions", "signals", "fills"})
    for name in COLUMNS:
        pd.testing.assert_frame_equal(tables[name], self.tables[name])

def test_refuses_existing_run_directory(self):            # Review Focus 5
    write_run(self.root, self.manifest, self.tables)
    with self.assertRaises(RunOutputError):
        write_run(self.root, self.manifest, self.tables)

def test_detects_tampered_file(self):                      # Review Focus 5
    path = write_run(self.root, self.manifest, self.tables)
    (path / "fills.parquet").write_bytes(b"x")
    with self.assertRaises(RunOutputError):
        read_run(path)

def test_rejects_missing_column_and_missing_manifest_key(self):
    bad = dict(self.tables, returns=self.tables["returns"].drop(columns="equity"))
    with self.assertRaises(RunOutputError):
        write_run(self.root, self.manifest, bad)
    with self.assertRaises(RunOutputError):
        write_run(self.root, {k: v for k, v in self.manifest.items() if k != "engine"}, self.tables)

def test_run_id_and_config_hash_are_deterministic(self):
    now = datetime(2026, 11, 17, 8, 30, tzinfo=timezone.utc)
    self.assertEqual(config_hash({"b": 1, "a": 2}), config_hash({"a": 2, "b": 1}))
    self.assertTrue(new_run_id({"a": 1}, now).startswith("20261117T083000Z-"))
```

`setUp` builds a temporary root, a manifest containing every `MANIFEST_KEYS` key, and one-row tables with exactly `COLUMNS`.

- [ ] **Step 2: Run** `.venv/bin/python -m unittest tests.current.test_run_output -v` — Expected: FAIL, `ModuleNotFoundError: research.evaluation.run_output`.
- [ ] **Step 3: Implement** the interfaces above. Write each table with `DataFrame.to_parquet(index=False)`, hash the written bytes, then write `manifest.json` last; create the run directory with `mkdir(exist_ok=False)`.
- [ ] **Step 4: Run** the same command — Expected: PASS. Then `make boundaries-check` — Expected: pass.
- [ ] **Step 5: Commit** `git add research/evaluation/run_output.py tests/current/test_run_output.py && git commit -m "Add run output schema, writer and reader"`

### Task 2: Market data model and synthetic fixture

**Files:**
- Create: `research/evaluation/market_model.py`, `research/evaluation/parity_fixture.py`
- Test: `tests/current/test_market_model.py`

**Interfaces:**
- Produces (in `market_model.py`):
  - `@dataclass(frozen=True) class Dividend: instrument: str; ex_date: str; pay_date: str; per_share: float`
  - `@dataclass(frozen=True) class Split: instrument: str; effective_date: str; ratio: int` (forward splits only; `ratio >= 2`)
  - `@dataclass(frozen=True) class MarketData: sessions: tuple[str, ...]; bars: dict[str, pd.DataFrame]; dividends: tuple[Dividend, ...]; splits: tuple[Split, ...]` — bars indexed by session date `YYYY-MM-DD`, columns `open, high, low, close, volume`, raw prices.
  - `class MarketDataError(ValueError)`; `validate(data: MarketData) -> None`
  - `@dataclass(frozen=True) class MarketConfig: initial_cash: float = 100_000.0; cost_bps: float = 5.0; commission_usd: float = 1.0`
  - `execution_price(open_px: float, side: str, cost_bps: float) -> float` — `round(open_px * (1 + sign * cost_bps / 10_000), 2)`, sign +1 for BUY, −1 for SELL.
  - `@dataclass(frozen=True) class Decision: targets: dict[str, int]; signals: dict[tuple[str, str], float]`
  - `TargetFn = Callable[[str, dict[str, pd.DataFrame], dict[str, int], float], Decision]` — arguments: session date *t*, bars up to and including *t*, current holdings, equity at close *t*.
  - `sma_trend_targets(window: int = 20, gross: float = 0.95) -> TargetFn` — equal weight across instruments whose close is above their `window`-session mean; shares `floor(gross / n * equity / close)`; signal `(instrument, "trend") = close / mean - 1`; zero targets before `window` sessions.
- Produces (in `parity_fixture.py`): `synthetic_fixture(seed: int = 7) -> MarketData` — instruments `AAA`, `BBB`, `CCC`; 250 business-day sessions from 2024-01-02; `BBB` 2:1 split at session 120 with the pre-split close an even number of cents; four `AAA` dividends of 0.40 and two `CCC` dividends of 0.25, each paid 5 sessions after its ex-date; a random walk from `numpy.random.default_rng(seed)` that keeps every price positive and OHLC consistent.

- [ ] **Step 1: Write the failing tests**

```python
def test_fixture_is_valid_and_deterministic(self):
    a, b = synthetic_fixture(), synthetic_fixture()
    validate(a)
    self.assertEqual(len(a.sessions), 250)
    pd.testing.assert_frame_equal(a.bars["BBB"], b.bars["BBB"])
    self.assertEqual([s.ratio for s in a.splits], [2])
    self.assertEqual(len(a.dividends), 6)

def test_rejects_missing_session(self):                    # Review Focus 2
    data = synthetic_fixture()
    bars = dict(data.bars, AAA=data.bars["AAA"].drop(data.sessions[10]))
    with self.assertRaises(MarketDataError):
        validate(replace(data, bars=bars))

def test_rejects_split_between_ex_and_pay(self):            # Review Focus 2
    data = synthetic_fixture()
    split = data.splits[0]
    bad = Dividend("BBB", data.sessions[118], data.sessions[123], 0.1)
    with self.assertRaises(MarketDataError):
        validate(replace(data, dividends=data.dividends + (bad,)))

def test_execution_price_rounds_to_cents(self):
    self.assertEqual(execution_price(100.0, "BUY", 5.0), 100.05)
    self.assertEqual(execution_price(100.0, "SELL", 5.0), 99.95)
```

`validate` also rejects non-positive prices, inconsistent OHLC, unsorted or duplicate sessions, and actions naming unknown instruments or sessions.

- [ ] **Step 2: Run** `.venv/bin/python -m unittest tests.current.test_market_model -v` — Expected: FAIL, module not found.
- [ ] **Step 3: Implement** both modules.
- [ ] **Step 4: Run** — Expected: PASS; `make boundaries-check` passes.
- [ ] **Step 5: Commit** `git commit -m "Add market data model and synthetic parity fixture"` with the three files.

### Task 3: Screening engine

**Files:**
- Create: `research/evaluation/screening_engine.py`
- Test: `tests/current/test_screening_engine.py`

**Interfaces:**
- Consumes: Task 2's `MarketData`, `MarketConfig`, `TargetFn`, `Decision`, `execution_price`; Task 1's `COLUMNS`.
- Produces:
  - `class EngineError(RuntimeError)` (defined here; Task 4 imports it)
  - `@dataclass(frozen=True) class EngineResult: engine: str; returns: pd.DataFrame; positions: pd.DataFrame; signals: pd.DataFrame; fills: pd.DataFrame; cash: pd.Series` — tables in `COLUMNS` layout, `cash` indexed by session.
  - `run_screen(data: MarketData, target_fn: TargetFn, config: MarketConfig) -> EngineResult` with `engine="screen"`.

Per session *d*, in this exact order (Task 4 must reproduce it):
1. **Split** effective on *d*: held quantity × ratio; credit cash in lieu `q * prev_close - q * ratio * round(prev_close / ratio, 2)` (zero for the fixture); scale any pending target for that instrument by the ratio.
2. **Dividend** with `pay_date == d`: credit `per_share ×` shares held at the close of the session before `ex_date`.
3. **Orders** from the decision made at close *d*−1: sells first, then buys, each in instrument order; fill price `execution_price(open, side, cost_bps)`; commission per fill; fill `cost = commission + |price - open| * quantity`. A buy leaving cash below zero raises `EngineError`.
4. **Close mark:** equity = cash + Σ quantity × close; record returns (`net_return = equity / previous equity - 1`, `cost` = that session's fill costs / previous equity, `gross_return = net_return + cost`), positions (weight = value / equity) and cash.
5. **Decision** for *d*+1 (not on the last session): call `target_fn`; reject unknown instruments or negative shares with `EngineError`; record signals.

- [ ] **Step 1: Write the failing tests**

```python
def test_runs_fixture_and_conserves_cash(self):
    result = run_screen(synthetic_fixture(), sma_trend_targets(), MarketConfig())
    self.assertEqual(len(result.returns), 250)
    self.assertGreater(len(result.fills), 0)
    self.assertTrue((result.cash >= 0).all())

def test_split_doubles_holding_without_a_fill(self):
    result = run_screen(synthetic_fixture(), hold_targets({"BBB": 10}), MarketConfig())
    pos = result.positions.set_index(["date", "instrument"]).quantity
    data = synthetic_fixture(); day = data.splits[0].effective_date
    self.assertEqual(pos[(day, "BBB")], 20)
    self.assertFalse(((result.fills.date == day) & (result.fills.instrument == "BBB")).any())

def test_flat_through_split_and_dividend_changes_nothing(self):   # Review Focus 3
    result = run_screen(synthetic_fixture(), hold_targets({}), MarketConfig())
    self.assertTrue((result.cash == 100_000.0).all())

def test_overspend_raises(self):                                   # Review Focus 1
    with self.assertRaises(EngineError):
        run_screen(synthetic_fixture(), hold_targets({"AAA": 10_000_000}), MarketConfig())

def test_bad_targets_raise(self):                                  # Review Focus 4
    for targets in ({"ZZZ": 1}, {"AAA": -1}):
        with self.subTest(targets=targets), self.assertRaises(EngineError):
            run_screen(synthetic_fixture(), hold_targets(targets), MarketConfig())
```

`hold_targets(targets)` is a test helper returning a `TargetFn` that always returns `Decision(targets, {})`.

- [ ] **Step 2: Run** `.venv/bin/python -m unittest tests.current.test_screening_engine -v` — Expected: FAIL, module not found.
- [ ] **Step 3: Implement** `run_screen` as specified.
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Add daily screening engine"`.

### Task 4: NautilusTrader confirmation engine

**Files:**
- Create: `research/evaluation/native_engine.py`
- Test: `tests/current/test_native_engine.py`

**Interfaces:**
- Consumes: Task 2 types; Task 3's `EngineResult`, `EngineError`.
- Produces: `run_native(data: MarketData, target_fn: TargetFn, config: MarketConfig) -> EngineResult` with `engine="nautilus"`.

Approach (follows the pattern of the existing native SPY runner without importing it):
- One `Equity` per instrument on venue `SIM` (price precision 2, increment 0.01, size increment 1); cash account in USD with `config.initial_cash`; `FixedFeeModel(Money(config.commission_usd, USD))`; `bar_execution=False`.
- Per session: a quote tick at 09:30 New York with bid `execution_price(open, "SELL")` and ask `execution_price(open, "BUY")`; a daily bar at 16:00.
- The strategy calls `target_fn` once all instruments' 16:00 bars for *t* have arrived, using cash + Σ quantity × close as equity, and submits market orders on the 09:30 quote of *t*+1, sells before buys, in instrument order. A buy whose expected cost exceeds cash raises `EngineError` before submission.
- **Split:** on the effective date, before 09:30, a zero-spread quote at 09:28 priced at the previous close (sell the full holding) and one at 09:29 priced at `round(prev_close / ratio, 2)` (buy holding × ratio). Both orders carry the tag `split`, are excluded from `fills`, and their two commissions are refunded with `adjust_account`. Pending targets for that instrument are scaled by the ratio.
- **Dividend:** a `SimulationModule` records holdings at the first event of the ex-date and credits cash on the first event of the pay date with `adjust_account`.
- Build `EngineResult` from the strategy's recorded closes and the fills report (excluding `split` tags).

- [ ] **Step 1: Write the failing tests** — the same five scenarios as Task 3 against `run_native` (Review Focus 1, 3, 4 included), plus:

```python
def test_split_orders_are_not_reported_and_cost_nothing(self):
    result = run_native(synthetic_fixture(), hold_targets({"BBB": 10}), MarketConfig())
    day = synthetic_fixture().splits[0].effective_date
    before = result.cash[synthetic_fixture().sessions[synthetic_fixture().sessions.index(day) - 1]]
    self.assertAlmostEqual(result.cash[day], before, places=2)
```

- [ ] **Step 2: Run** `.venv/bin/python -m unittest tests.current.test_native_engine -v` — Expected: FAIL, module not found.
- [ ] **Step 3: Implement** `run_native`.
- [ ] **Step 4: Run** — Expected: PASS; the module's runtime on the fixture is under 30 seconds.
- [ ] **Step 5: Commit** `git commit -m "Add NautilusTrader confirmation engine"`.

### Task 5: Parity comparator and the CI check

**Files:**
- Create: `research/evaluation/parity.py`
- Test: `tests/current/test_engine_parity.py`

**Interfaces:**
- Consumes: `EngineResult` (Task 3).
- Produces: `@dataclass(frozen=True) class ParityReport: passed: bool; mismatches: tuple[str, ...]`; `compare(a: EngineResult, b: EngineResult, cash_tol_usd: float = 0.01) -> ParityReport` — checks identical position quantities per (date, instrument), identical fill (date, instrument, side, quantity, price) rows, and cash and equity within `cash_tol_usd` on every session. Each mismatch names the session, instrument and field.

- [ ] **Step 1: Write the failing tests**

```python
def test_engines_agree_on_synthetic_fixture(self):
    data, fn, cfg = synthetic_fixture(), sma_trend_targets(), MarketConfig()
    report = compare(run_screen(data, fn, cfg), run_native(data, fn, cfg))
    self.assertTrue(report.passed, report.mismatches)

def test_comparator_reports_a_real_difference(self):
    data, fn = synthetic_fixture(), sma_trend_targets()
    report = compare(run_screen(data, fn, MarketConfig()), run_native(data, fn, MarketConfig(cost_bps=6.0)))
    self.assertFalse(report.passed)
    self.assertTrue(any("price" in m for m in report.mismatches))
```

- [ ] **Step 2: Run** `.venv/bin/python -m unittest tests.current.test_engine_parity -v` — Expected: FAIL, module not found.
- [ ] **Step 3: Implement** `compare`.
- [ ] **Step 4: Run** — Expected: PASS. If the first test fails, fix the engine that departs from Task 3's per-session order; never widen the tolerance. Then run `make check` — Expected: pass (the parity test runs through `unittest discover`).
- [ ] **Step 5: Commit** `git commit -m "Add engine parity comparator and CI parity test"`.

### Task 6: Local real-data parity run, receipt and documentation

**Files:**
- Create: `research/evaluation/sector_derivative.py`, `scripts/current/engine_parity.py`, `docs/tasks/2026-11-17-engine-parity.md`, `docs/tasks/evidence/2026-11-17-engine-parity.json`
- Modify: `Makefile` (new `parity-local` target, not part of `check`), `README.md` (capability row), `docs/tasks/2026-11-17-offline-research-infra-design.md` (status of P0 and P1b)
- Test: `tests/current/test_sector_derivative.py`, `tests/current/test_engine_parity_cli.py`

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces:
  - `load_sector_derivative(bars_path: Path, actions_path: Path, instruments: tuple[str, ...]) -> MarketData`
  - `scripts/current/engine_parity.py run --bars PATH --actions PATH --instruments SPY,XLB,XLE,XLF --out DIR` — runs both engines with `sma_trend_targets()` over 2016–2025, writes two run outputs with Task 1 (the native run's `parent_run` is the screening run), writes `receipt.json` next to them with both run IDs, input file hashes and the `ParityReport`, and exits non-zero on a mismatch.

- [ ] **Step 1:** Read `docs/tasks/2026-10-28-sector-issuer-qualification.md` and its JSON receipt; record the derivative's bar and action file paths and column names in the execution ledger. If the derivative is not present locally, stop and report it as blocked.
- [ ] **Step 2: Write the failing tests** — `test_loader_maps_recorded_columns` on a three-session sample built from the recorded columns (one dividend with ex and pay dates); `test_cli_writes_two_runs_and_receipt` on the synthetic fixture through an injectable loader, asserting two readable run directories, a receipt with `passed: true`, and exit code 0.
- [ ] **Step 3: Run** both test modules — Expected: FAIL, modules not found.
- [ ] **Step 4: Implement** the loader, the command and `parity-local` (`$(PYTHON) scripts/current/engine_parity.py run ...` with the recorded paths and `--out .local/parity`).
- [ ] **Step 5: Run** the tests — Expected: PASS. Then `make parity-local` — Expected: exit 0 and `passed: true`. On a mismatch, record it as the actual result; do not change tolerances.
- [ ] **Step 6:** Write the task record and JSON receipt with the actual command, run IDs, hashes and outcome; add a README capability row ("Run output and engine parity: implemented on the synthetic CI fixture; local sector-ETF parity per receipt"); mark P0 and P1b in the design with links. Run `scripts/current/research_index.py --write`, then `make check` — Expected: pass.
- [ ] **Step 7: Commit** `git commit -m "Add local sector-ETF engine parity run and record its receipt"`.
