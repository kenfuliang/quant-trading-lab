---
status: active
updated: 2026-11-19
owner: project-maintainers
---

# Candidate confirmation (Plan 8, roadmap step 10) implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A command that takes a stored screening run, re-runs the same frozen candidate through the NautilusTrader engine, proves the two agree, and writes the NautilusTrader run output and a passing parity-style receipt. These are the refs Plan 6's rule 3 requires before a `keep` record can be logged.

**Architecture:**
- **Core:** a pure function in `research/evaluation/confirm.py` takes the stored screening run, reloaded data, a target function and callables for the two engines, and returns the NautilusTrader tables and a receipt dict.
- **Command:** `scripts/confirm.py` resolves the roots, the dataset, the membership mask and the quality gate, calls the core, and writes the run output and the receipt.
- **Receipt:** it reuses `parity-receipt/v1`, because rule 3 already reads exactly that shape.

**Tech Stack:** Python 3.12, pandas, NautilusTrader 1.231 (existing engine only), `unittest`. No new dependencies.

**Spec:**
- [design](2026-11-17-offline-research-infra-design.md), the "Three rules" section;
- [Plan 6 record](2026-11-18-enforced-rules.md) and [workflow](../workflow.md), rule 3;
- [roadmap](../roadmap.md), step 10.

## Global Constraints

- **Frozen candidate:** the candidate is exactly what the screening run's manifest records: strategy spec, market config, instruments, dataset (with its manifest SHA-256), and the membership and identity ids if the run was masked. Nothing is taken from the command line except where to find roots.
- **No tuning, no new data:** confirmation never changes a parameter, an instrument or a dataset. A candidate that disagrees between engines is a finding: the receipt records it, the command exits 1, and nothing is adjusted.
- **Owner-only acceptance stays owner-only:** a confirmation of a `use: financial` run re-verifies the quality gate from the data root. It never writes an acceptance.
- **Layers:**
  - `evaluation` may import data, features, policies, evaluation and reporting, and may not import `control`.
  - Commands may import everything.
  - No pinned-file edits, no new dependencies, tests offline and each under 30 s.
- **Outputs:**
  - Exclusive create, never overwritten.
  - The NautilusTrader run goes to the runs root as `run-output/v1`.
  - The receipt goes to `<parity root>/<parity_id>/receipt.json`.
- **Docs:** follow `docs/README.md`.

## Decisions (controller rulings from the code survey, binding)

- **Rebuilding the candidate:**
  - **Strategy:** `build_target_fn(manifest.config.strategy)`.
  - **Market config:** `MarketConfig(**manifest.config.market)`.
  - **Instruments:** `manifest.config.instruments`, in order.
  - **Masking:** when `config.universe` exists, rebuild `members_only` from its `membership_id` and `identity_id`.
  - **Dataset:** `load_dataset(manifest.datasets.dataset_id, instruments)`. Its `manifest_sha256` must equal the screening manifest's. A synthetic-fixture run (no dataset hash) is confirmable for engineering use only and is marked `bindable: false`.
- **Which screening run:** only a manifest with `engine: "screen"` that carries `config.strategy`, `config.market` and `config.instruments`. A run from `engine_parity` (a fixed `sma_trend_targets` strategy name) or a combiner run is refused with a clear message.
- **Proving the stored run is the candidate:** the core re-runs `run_screen` in-process on the reloaded data with the rebuilt target function, then requires its four tables to equal the stored run's tables exactly. If they differ, confirmation refuses (the stored run is not reproducible, for example because the engine code changed). This is the check that ties the stored run id to the candidate.
- **Comparing engines:** `parity.compare(screen_rerun, native)` with the default tolerances. `cash` is not stored in run outputs, so it comes from the in-process re-run, not from the stored tables.
- **The NautilusTrader run output:**
  - `engine: "nautilus"` and `parent_run` set to the screening run id.
  - `config` equals the screening config with only `engine` changed (and `ladder` dropped), so the bound keys (`strategy`, `market`, `instruments`) are equal.
  - `datasets` is copied from the screening manifest.
  - `use`, `acceptance_sha256`, `labels` and `universe_kind` are copied when present.
- **Financial runs:** if the screening manifest says `use: "financial"`, the command re-verifies the quality gate (`acceptance.verify_for_financial_use` on the report named by `datasets.quality_report`, confined to the data root), requires the resulting `acceptance_sha256` to equal the manifest's, and refuses otherwise. An engineering screening run produces an engineering NautilusTrader run.
- **Receipt:** `parity-receipt/v1` with the standard fields and these additions: `kind: "candidate-confirmation"`, `candidate` (strategy, market, instruments, ladder id and rung, universe ids), `screen` and `nautilus` run ids with manifest SHA-256s under `runs`, `datasets` provenance, `use` and `acceptance_sha256` when financial, `stored_screen_identical: true`, `bindable`, `mismatches`, `timing`. `status` is `passed` or `mismatch`; `passed`, `mismatch_count` and `code_commit` follow the existing meaning.
- **Clean tree:** a dirty working tree is refused unless `--allow-dirty` is given. The receipt then records `+dirty`, and rule 3 will reject it (documented).
- **Rule 3 effect:** after a passing, clean, financial confirmation, the registry command can log a `keep` with `--run-id` (the screening run), `--nautilus-run-id`, `--parity-receipt` and a validation receipt. That is exercised end to end in Task 3 with temporary roots, and **no `keep` is logged to the real registry**.

## Review Focus

1. Confirmation must refuse (naming the reason) when the stored screening run no longer reproduces, when the dataset hash differs, when the run is not a `screen` run, or when a financial run's quality gate no longer verifies.
2. A mismatch between engines must leave a receipt with `status: "mismatch"` and the first mismatches, exit 1, and must not produce a receipt that satisfies rule 3.
3. The NautilusTrader manifest must satisfy Plan 6's `require_nautilus_run` binding: same `datasets.manifest_sha256` and equal `strategy`, `market` and `instruments`.
4. A masked candidate must be rebuilt with the same membership and identity (hashes verified), or refused.
5. Nothing is written to the registry, the trial ledger or any acceptance by this command.

---

### Task 1: Confirmation core

**Files:**
- Create: `research/evaluation/confirm.py`
- Test: `tests/current/test_confirm.py`

**Interfaces:**
- Consumes: `run_output` (`read_run`, `write_run`, `config_hash`, `new_run_id`, `COLUMNS`), `engine_contract.EngineResult`, `parity.compare`, `screening_engine.run_screen`, `native_engine.run_native`, `market_model` (`MarketConfig`, `MarketData`, `market_config_dict`).
- Produces:
  - `class ConfirmError(ValueError)`.
  - `CANDIDATE_KEYS = ("strategy", "market", "instruments")`.
  - `candidate_from_manifest(manifest: dict) -> dict` returns `{strategy, market: MarketConfig, instruments: tuple, universe: dict | None, datasets: dict}`. It raises `ConfirmError` for a non-`screen` run or missing keys.
  - `@dataclass(frozen=True) class Confirmation: screen: EngineResult; native: EngineResult; report: ParityReport; stored_identical: bool; screen_seconds: float; native_seconds: float`.
  - `confirm(data, target_fn, market, stored_tables: dict[str, pd.DataFrame], *, run_screen_fn=run_screen, run_native_fn=run_native) -> Confirmation`. It re-runs the screen engine, requires equality with the stored tables (raising `ConfirmError` naming the first differing table and date), runs the native engine, and compares.
  - `native_manifest(screen_manifest, native_result, *, code_commit, now, engine_version) -> dict` returns a manifest that passes `write_run`, per the Decisions (config with `engine` changed, `parent_run`, copied `datasets`, `use`, `acceptance_sha256`, `labels`, `universe_kind`).
  - `build_receipt(...) -> dict` returns the `parity-receipt/v1` document per the Decisions.

- [ ] **Step 1: Write the failing tests** (using `synthetic_fixture()` and a screening run written with `run_ladder` or `write_run`):
  - `test_candidate_from_manifest_rebuilds_inputs`;
  - `test_non_screen_or_incomplete_manifest_refused` (Review Focus 1);
  - `test_confirm_passes_on_fixture_and_returns_identical_flag`;
  - `test_changed_stored_run_is_refused_naming_table_and_date` (Review Focus 1);
  - `test_native_manifest_satisfies_rule3_binding` (equal bound keys, same dataset hash, parent run; Review Focus 3, checked against the keys `research/control/run_refs.py` reads, using plain dicts);
  - `test_native_manifest_copies_use_labels_and_acceptance`;
  - `test_mismatch_is_reported_not_raised` (a fake native runner that perturbs a fill; Review Focus 2).
- [ ] **Step 2: Run them.** `<python> -m unittest tests.current.test_confirm -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the tests and `make check`.
- [ ] **Step 5: Commit:** "Candidate confirmation core".

### Task 2: Confirmation command

**Files:**
- Create: `scripts/confirm.py`
- Modify: `research/registry/artifacts.json` (`parity-receipt/v1` producer and consumers; re-render), `Makefile` (no new check target; optional `confirm-local` target documented in workflow only)
- Test: `tests/current/test_confirm_cli.py`

**Interfaces:**
- Consumes: Task 1; `scripts/analysis.py` helpers for the membership mask and the financial gate (extract shared helpers into `research/evaluation/` only if importing `analysis` from another script is awkward; analysis behaviour, goldens and its tests must not change); `research/data/root.py`; `research/evaluation/datasets.py`; `research/evaluation/acceptance.py`.
- Produces: `scripts/confirm.py --run-id ID [--root] [--runs-root] [--parity-root] [--allow-dirty]`, which:
  - reads the screening run, rebuilds the candidate, reloads and hash-checks the dataset (or the synthetic fixture), rebuilds the mask (hash-verifying membership and identity), and re-verifies the quality gate for financial runs;
  - calls `confirm`, writes the NautilusTrader run and the receipt, prints both ids and the receipt path;
  - exits 0 only for status `passed`; exits 1 for a mismatch or a refusal (`error: ...`), and 2 for absent data (`blocked: data absent: ...`);
  - never writes to the registry, the ledger or an acceptance.

- [ ] **Step 1: Write the failing tests** (temp roots; dataset-mode fixtures as in `tests/current/test_datasets.py` and the analysis tests; a loader injection):
  - `test_confirm_writes_native_run_and_passed_receipt`;
  - `test_refuses_when_dataset_hash_differs` and `test_refuses_non_screen_run` (Review Focus 1);
  - `test_financial_run_reverifies_gate_and_copies_acceptance` and `test_financial_run_refused_when_acceptance_removed`;
  - `test_masked_candidate_rebuilds_mask_and_verifies_hashes` (Review Focus 4);
  - `test_dirty_tree_refused_unless_allowed`, with an injected commit helper;
  - `test_mismatch_writes_mismatch_receipt_and_exits_1` (Review Focus 2);
  - `test_no_registry_ledger_or_acceptance_written` (Review Focus 5: those paths are untouched);
  - `test_missing_data_exits_2`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the tests and `make check`.
- [ ] **Step 5: Commit:** "Candidate confirmation command".

### Task 3: End-to-end `keep` path, docs and records

**Files:**
- Create: `tests/current/test_keep_path.py`, `docs/tasks/2026-11-19-candidate-confirmation.md` (task record)
- Modify: `docs/workflow.md` (rule 3: how to produce the refs; remove "no keep is possible yet" and say what is still needed: an accepted quality report, a validation receipt, a clean tree), `docs/roadmap.md` (step 10 implemented, with limits), the design doc's "Not yet" bullet, `docs/conventions.md` only if the receipt kind needs a line, `research/registry/readiness.json` (R1 and any aspect this plan truly completes; each at most +1 and cited; re-render), `scripts/current/research_index.py --write`
- Test: the new test; `make check`

- [ ] **Step 1: Write the failing test** `test_keep_path_end_to_end`, in temporary roots with a tiny dataset fixture and an accepted quality report. Steps, each rejection asserted before its success:
  1. a financial screening run via `run_spec`;
  2. `confirm` → NautilusTrader run and a passing receipt;
  3. `experiments log --dry-run` for `keep` with the screening run id, the NautilusTrader run id and the parity receipt but **no validation receipt** → rejected naming it;
  4. add a valid tracked validation receipt (a Validation skill, run ids covering both runs, the parity receipt id) in a temp receipts directory with a fake git → accepted;
  5. a `--allow-dirty` confirmation's receipt (`+dirty`) is rejected for `keep`.

  All with temporary registries. **Nothing is written to the real registry.**
- [ ] **Step 2: Run it.** Expected: FAIL until Tasks 1–2 land, then PASS.
- [ ] **Step 3: Write the records:**
  - the task record: what the command does, the two real-data confirmations below, the limits;
  - the workflow, roadmap, design and readiness updates.
- [ ] **Step 4: Real-data confirmation (engineering use, no acceptance involved):**
  - Run `scripts/confirm.py` on the ETF sleeve screening run from the portfolio demonstration (cite its run id from `docs/tasks/evidence/2026-11-18-portfolio.json`).
  - If feasible within a few minutes, also run it on a stock candidate limited by the run's own instruments (the stock sleeve takes about 7 minutes native; if the run is too slow, say so and use the ETF run only).
  - Record status, mismatches, timings, and that the receipts are engineering-use and **cannot back a `keep`** (the datasets are unaccepted).
  - From a clean tree: commit first, then run.
- [ ] **Step 5: Run** `scripts/current/research_index.py --write` and `make check`, then commit: "Candidate confirmation: keep path, docs and records".
