---
status: active
updated: 2026-11-18
owner: project-maintainers
---

# Enforced research rules (Plan 6, phase P4) implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make three research rules tool-enforced, each with a failing-then-passing test: financial use needs an accepted quality report, a completed financial record needs a run output, and a promoting record needs a NautilusTrader run, a passing parity receipt and an independent validation receipt.

**Architecture:**
- **Quality acceptance** is a new artifact written only by an explicit owner command.
- **Financial runs** are flagged `use: financial`, and the run command checks that flag.
- **Registry rules:**
  - Shape rules live in `validate()` and apply to new records only.
  - File checks live in a control-layer module and run at log time.
  - The tracked validation receipt is re-checked by `make check`.
- **Control layer:** `research/control` cannot import evaluation or data, so its readers take plain paths and use `json` and `hashlib`.

**Tech Stack:** Python 3.12 standard library, pandas (existing code only), `unittest`. No new dependencies.

**Spec:**
- [offline research infrastructure design](2026-11-17-offline-research-infra-design.md), the "Three rules" section (~lines 225–250) and the P4 row;
- [goals](../goals.md);
- [research standard](../research-standard.md), "Incremental improvement and disposition";
- the approved master plan (Plan 6 block).

## Global Constraints

- **Existing records are untouched:**
  - The registry is hash-chained and append-only.
  - All 110 current records are `development` class, 109 are `imported: true` and one is a `blocked` record.
  - No new rule may change how they validate. New rules apply only to records with `imported: false`.
- **Local data:**
  - Run outputs, parity receipts and quality reports are local and absent in CI.
  - `make check` must therefore never require those files.
  - File reads happen at log time and in explicit commands.
  - `make check` verifies only tracked material, such as registry refs and validation receipts, and it needs no local files.
- **Layers:**
  - `research/control` may import only `research/control`.
  - `research/evaluation` may import data, features, policies, evaluation and reporting.
  - Commands (`scripts/`) may import everything.
  - No edits to pinned files (`research/compatibility.json`); no new dependencies; tests offline, each under 30 s.
- **The owner accepts exceptions, the agent does not.** No code path or command run by this plan may record an acceptance on the owner's behalf. The acceptance command exists, is tested on temporary data only, and is never run against the real data root during this plan.
- **Honest limits:**
  - Skill names in a validation receipt are self-reported, and the tool cannot prove which model or session produced them.
  - The tool enforces separation of recorded roles, not independence.
  - The docs say this.
- **Docs:** follow `docs/README.md`. Schema ids must be catalogued.

## Decisions (controller rulings from the code survey, binding)

- **"Financial use":**
  - A run is financial when its spec or command says `use: financial`. Everything else is `engineering`, which is the default and what parity and screening runs are.
  - `analysis.json` and every run manifest from a financial run record `use: "financial"`.
  - Engineering manifests gain no new keys, so existing hashes and goldens stay identical.
- **Quality acceptance `quality-acceptance/v1`:**
  - It is stored as `<data root>/quality/<dataset_id>/<report stamp>/acceptance.json`, with exclusive create.
  - Fields: `schema`, `dataset_id`, `report_stamp`, `report_sha256`, `accepted_by` (non-empty text), `accepted_utc`, `accepts` (check names, or `["all"]`), `note`.
  - It is valid only for the exact report it names, by SHA-256.
  - A financial run on a `pass-with-exceptions` report needs an acceptance whose `accepts` covers every check that is not `pass`. A `pass` report needs none. A `fail` report is never loadable.
  - A changed report or dataset invalidates the acceptance.
- **Which registry disposition promotes:** `keep` (the registry has no `adopt`). Retiring, controlling and inconclusive records do not promote.
- **Rule 2 (completed financial record needs a run output):**
  - A new record (`imported` not true) with a non-`blocked` disposition and `attempt` ≠ `failed`/`abandoned` must carry `refs.run_id` and `refs.run_manifest_sha256` (64 hex characters).
  - `attempt` is a new optional field in `completed` (default), `failed` or `abandoned`.
  - At log time the run manifest is read from the runs root and its SHA-256 must match. It must show `use: "financial"`, and its `datasets.quality_status` must be `pass`, or `pass-with-exceptions` with an `acceptance` recorded.
- **Rule 3 (a `keep` record):**
  - **Refs (all required):**
    - `refs.nautilus_run_id` plus `refs.nautilus_run_manifest_sha256`: the run's manifest must have `engine: "nautilus"`.
    - `refs.parity_receipt_id` plus `refs.parity_receipt_sha256`: the receipt must have `status: "passed"`, 0 mismatches, a `code_commit` without `+dirty`, and `runs.nautilus.run_id` equal to the record's `nautilus_run_id`.
    - `refs.validation_receipt` plus `refs.validation_receipt_sha256`.
  - **Engine code identity:** `git diff --quiet <receipt code_commit> <run code_commit> -- <ENGINE_FILES>`. The files are `research/evaluation/{engine_contract,screening_engine,native_engine,market_model,parity}.py`. The commit comparison runs at log time in `scripts/experiments.py`.
  - **Validation receipt (`validation-receipt/v1`):** tracked at `research/registry/validation-receipts/<receipt_id>.json`, with `result: "pass"`, a validator skill in the Validation allowlist that is not among the researcher skills, and the same run ids. `make check` re-verifies these tracked files.
- **Validation allowlist:** `trade-leakage-audit`, `trade-robust-evaluation`, `trade-promotion-review`. Research skills (`trade-research-design`, `trade-feature-engineering`, `trade-experiment`, `trade-performance-diagnosis`, `trade-candidate-evolution`) may not validate their own runs.
- **Parity receipt `run_id`:** the receipt gains a top-level `parity_id` (its folder name) and `run_id` (the nautilus run id, null unless both engines ran).

## Review Focus

1. A record that tries to skip any rule must be rejected, naming the missing item, in both `log` and the structural part of `check`.
2. The 110 existing records must still validate, byte-for-byte unchanged, and `make check` must pass with no local data.
3. An acceptance for a different report (changed SHA-256), or one that does not cover every exception, must not unlock a financial run.
4. A validation receipt whose validator is a Research skill, or whose run ids differ from the record's, must be rejected.
5. No code path writes an acceptance for the owner. Tests use temporary roots only.

---

### Task 1: Quality acceptance and the financial-use gate

**Files:**
- Create: `research/evaluation/acceptance.py`
- Modify:
  - `scripts/data.py` (`accept` subcommand);
  - `research/evaluation/datasets.py` (`load_dataset` returns the verified acceptance in provenance);
  - `scripts/analysis.py` (a spec or CLI `use`; the financial gate);
  - `research/evaluation/analysis_output.py` and `ladder.py` (`use` and `acceptance_sha256` recorded only when financial);
  - `research/registry/artifacts.json` (`quality-acceptance/v1`; re-render)
- Test: `tests/current/test_acceptance.py`, additions to `tests/current/test_analysis_cli.py`

**Interfaces:**
- Produces:
  - `SCHEMA = "quality-acceptance/v1"`, `class AcceptanceError(ValueError)`.
  - `write_acceptance(root: Path, dataset_id: str, report_stamp: str, accepted_by: str, accepts: list[str], note: str, now: datetime) -> Path`. It reads the report, writes `acceptance.json` with exclusive create, and refuses empty `accepted_by` or `accepts`.
  - `verify_for_financial_use(root: Path, report_folder: Path, report: dict) -> dict`. It returns `{"status": "pass"|"accepted", "acceptance_sha256": str|None}`, or raises `AcceptanceError` naming the uncovered checks.
  - `scripts/data.py accept --dataset-id X --report-stamp S --by NAME --accepts all|check1,check2 --note TEXT`.
  - `use` values `engineering` (default) and `financial`.

- [ ] **Step 1: Write the failing tests:**
  - `test_pass_report_needs_no_acceptance`;
  - `test_exceptions_without_acceptance_block_financial_use`;
  - `test_acceptance_covering_all_exceptions_unlocks` (Review Focus 3);
  - `test_partial_acceptance_names_uncovered_checks`;
  - `test_acceptance_for_changed_report_is_rejected` (a changed report SHA-256);
  - `test_fail_report_never_loadable`;
  - `test_write_is_exclusive_and_requires_name`;
  - `test_engineering_run_unchanged` (an analysis with default `use` has the same keys and hashes as before);
  - `test_financial_run_records_use_and_acceptance`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Financial `scripts/analysis.py run` calls `verify_for_financial_use` before any run is written.
- [ ] **Step 4: Run** the tests and `make check`. Do not run `accept` against the real data root.
- [ ] **Step 5: Commit:** "Quality acceptance and the financial-use gate".

### Task 2: Parity receipt ids and the engine-code identity check

**Files:**
- Modify: `scripts/current/engine_parity.py` (`parity_id`, `run_id` in the receipt); create `research/evaluation/engine_identity.py` (the `ENGINE_FILES` constant and a pure helper `engine_files_changed(run_git, a, b)` taking an injected git runner)
- Test: `tests/current/test_engine_parity_cli.py` (additions), `tests/current/test_engine_identity.py`

**Interfaces:**
- Produces: the receipt keys `parity_id: str` and `run_id: str | None`; `ENGINE_FILES: tuple[str, ...]`; `engine_files_changed(git, a: str, b: str) -> list[str]` returns the changed engine files (empty means identical).

- [ ] **Step 1: Write the failing tests:**
  - `test_receipt_has_parity_id_and_nautilus_run_id`;
  - `test_rejected_or_timing_only_receipt_has_null_run_id`;
  - `test_engine_files_changed_with_fake_git`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the tests and `make check`. Existing receipts are unaffected, because only new receipts gain keys.
- [ ] **Step 5: Commit:** "Parity receipt ids and engine-code identity".

### Task 3: Registry rules 2 and 3

**Files:**
- Create: `research/control/run_refs.py` (control-layer readers: `read_run_manifest(runs_root, run_id, sha)`, `read_parity_receipt(parity_root, parity_id, sha)`; both use plain `json` and `hashlib`)
- Modify: `research/control/experiment_registry.py` (`validate`: the shape rules for new records, optional `attempt`), `scripts/experiments.py` (`log` flags `--run-id`, `--nautilus-run-id`, `--parity-receipt`, `--validation-receipt`, `--attempt`; log-time verification; `check` structural), `docs/templates/experiment-receipt.json` only if required
- Test: `tests/test_experiment_registry.py` (additions, following its helpers), `tests/current/test_run_refs.py`

**Interfaces:**
- Consumes: Task 1 (`use`, acceptance recorded in the manifest), Task 2 (`parity_id`, `run_id`, `engine_files_changed`).
- Produces:
  - `validate(record)` rejects, for new records (`imported` not true): a non-blocked, non-failed/abandoned record without `refs.run_id` and `refs.run_manifest_sha256`; and a `keep` record missing any rule-3 ref. The messages name each missing key.
  - `run_refs.read_run_manifest(...) -> dict` (raises `RegistryError` on a missing file or SHA-256 mismatch) and `read_parity_receipt(...) -> dict`.
  - `scripts/experiments.py log` verification at log time:
    - the run manifest has `use: "financial"` and a quality status of `pass`, or `pass-with-exceptions` with an `acceptance`;
    - for `keep`: the nautilus manifest has `engine: "nautilus"`, the parity receipt passes with a clean commit and the matching run id, and `engine_files_changed(git, receipt commit, run commit)` is empty.

- [ ] **Step 1: Write the failing tests:**
  - `test_new_completed_record_without_run_refs_is_rejected` (Review Focus 1);
  - `test_blocked_failed_and_abandoned_need_no_run_output`;
  - `test_imported_records_are_exempt` and `test_existing_registry_still_validates` (the real `research/registry/experiments.jsonl`, Review Focus 2);
  - `test_keep_without_each_rule3_ref_names_it` (subTests: nautilus run, parity receipt, validation receipt);
  - `test_log_rejects_hash_mismatch_missing_file_and_non_financial_run`;
  - `test_log_rejects_screen_engine_run_for_keep`;
  - `test_log_rejects_dirty_or_mismatched_parity_receipt`;
  - `test_log_rejects_when_engine_files_changed_between_commits` (fake git);
  - `test_full_valid_keep_record_logs`, using a temporary registry, runs root, parity root and tracked validation receipt;
  - `test_check_structure_passes_without_local_files` (Review Focus 2: `check` on a registry with such a record, with the runs and parity roots absent).
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Keep `validate()` pure.
- [ ] **Step 4: Run** the tests and `make check`.
- [ ] **Step 5: Commit:** "Registry rules: run output and promotion refs".

### Task 4: Validation receipts

**Files:**
- Create: `research/control/validation_receipts.py`, `scripts/validation.py` (`create` and `check`), `research/registry/validation-receipts/.gitkeep`
- Modify: `Makefile` (`validation-check` in `check`), `scripts/experiments.py` (`check` also verifies a `keep` record's tracked receipt: the file exists, its SHA-256 matches, the validator is allowed and separate, `result` is `pass`, and the run ids match), `research/registry/artifacts.json` (`validation-receipt/v1` implemented; re-render), `docs/skills.md`, `.agents/skills/trade-leakage-audit/SKILL.md`, `.agents/skills/trade-robust-evaluation/SKILL.md`, `.agents/skills/trade-promotion-review/SKILL.md` (a short "Validation receipt" section each), `docs/operations/recursive-research.md` (the Disposition step)
- Test: `tests/current/test_validation_receipts.py`, `tests/test_skill_catalog.py` (the catalog check must still pass)

**Interfaces:**
- Produces:
  - `SCHEMA = "validation-receipt/v1"`, `VALIDATION_SKILLS`, `RESEARCH_SKILLS`, `class ValidationReceiptError(ValueError)`.
  - A receipt: `{schema, receipt_id, created_utc, run_ids: [...], parity_receipt_id, validator: {skill}, researcher: {skills: [...]}, checks: [{name, status, detail}], result: "pass"|"fail", notes}`.
  - `load_receipt(path) -> dict`, which validates the shape and the allowlist.
  - `scripts/validation.py create --receipt-id --run-id ... --parity-receipt-id --validator-skill --researcher-skills ... --check name:status:detail ... --result` (exclusive create) and `check` (all tracked receipts).

- [ ] **Step 1: Write the failing tests:**
  - `test_research_skill_cannot_validate` (Review Focus 4);
  - `test_validator_must_not_be_among_researcher_skills`;
  - `test_unknown_skill_rejected`;
  - `test_receipt_must_list_the_records_run_ids`;
  - `test_failed_validation_cannot_back_a_keep`;
  - `test_create_is_exclusive`;
  - `test_check_command_passes_on_empty_directory`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Document the honest limit in `docs/skills.md`: roles are recorded, not proven.
- [ ] **Step 4: Run** the tests and `make check`, including the skill-catalog parity check.
- [ ] **Step 5: Commit:** "Validation receipts and the Validation role contract".

### Task 5: End-to-end rule demonstration, docs and records

**Files:**
- Create: `tests/current/test_enforced_rules.py` (one temporary-root scenario that walks all three rules: a financial run is blocked, accepted, run, logged and promoted, with each skipped step rejected in turn), `docs/tasks/2026-11-18-enforced-rules.md` (task record)
- Modify:
  - `docs/workflow.md` (the three rules in the development workflow, the definition of "financial use", and the owner-only acceptance rule);
  - `docs/research-standard.md` (a short note on which registry value promotes), only where the owner of that document allows an additive note;
  - `docs/conventions.md` (`use` values);
  - the design P4 row and the three-rules section (status: implemented, with the limits);
  - `docs/roadmap.md` step 6;
  - `research/registry/readiness.json`: H1, R11, R6 and any aspect whose next action this plan completed, each at most +1 and cited, then re-render;
  - `research/registry/gates.json` and `scripts/progress.py` expectations only if a gate item is directly satisfied (do not edit hand-maintained statuses without evidence).
- Test: the new test; `make check`.

- [ ] **Step 1: Write the failing scenario test** `test_end_to_end_rules` with a temporary registry, data root, a tiny fixture dataset whose quality report is `pass-with-exceptions`. Steps, each asserting the earlier rejection first:
  1. financial run → blocked (no acceptance);
  2. `write_acceptance` → run succeeds;
  3. `log` a completed record with no run refs → rejected, then accepted with them;
  4. `log` a `keep` record → rejected for each missing rule-3 ref in turn, then accepted once the nautilus run, a passing parity receipt and a validation receipt exist (build small fixture runs and receipts in the temp roots);
  5. a validation receipt from a Research skill → rejected.
- [ ] **Step 2: Run it.** Expected: FAIL.
- [ ] **Step 3: Implement** only what the scenario shows missing. Write the records and docs.
- [ ] **Step 4: Run** the test, `scripts/current/research_index.py --write` and `make check`.
- [ ] **Step 5: Commit:** "Enforced rules: end-to-end scenario, workflow and records".
