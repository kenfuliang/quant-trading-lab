---
status: proposed
updated: 2026-11-17
owner: project-maintainers
---

# Pipeline status and stage view: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reviewed stage-classification sidecar, an incumbents declaration, a generated `docs/pipeline-status.md`, and a "Pipeline" tab (stage view, compare, trust, cycle log) on the existing dashboard entry page.

**Architecture:** Pure functions in `research/control/` read the hash-chained registry plus two small JSON declarations and return a model; one renderer makes the status document and one makes the HTML page; `scripts/stages.py` is the only file-writing entry point and follows `scripts/experiments.py` (render + freshness check). Nothing writes the registry, receipts or gates.

**Tech Stack:** Python 3 standard library, `unittest` (project convention), static HTML like `scripts/dashboard.py`. No new dependency.

**Spec:** [2026-11-17-dashboard-redesign-design.md](2026-11-17-dashboard-redesign-design.md)

Run tests with `python3 -m unittest tests.<module> -v` from the repo root (this worktree has no `.venv`; the main checkout's `.venv/bin/python` works too).

## Global Constraints

- Views, not stores: write none of `research/registry/experiments.jsonl`, receipts, `gates.json`. Offline, loopback only, no broker or network.
- Metric units as stored (`net_cagr`, `max_drawdown` are fractions). Missing values render `n/a` and are `None` in data, never `0`.
- Effect = Pareto dominance on `net_cagr` (higher better) and `max_drawdown` (lower better); exact equality is `tie`, no tolerance. Sharpe, Calmar and underwater length are diagnostics and never decide an effect. No blended score and no per-cell roll-up label.
- Counting unit is the **record**. Trust is `unassessed` for every run; `evidence_status` is shown verbatim.
- Matched pair = a record tagged `challenger` plus the control the stage map names, in the same `context.code` and `context.period`; otherwise `ambiguous control` and no delta.
- Only a reviewed (`reviewed: true`) stage-map entry places a record in a stage cell; everything else is `unclassified`; `stage_under_test: "multiple"` is `unattributable`.
- Generated files are never hand-edited; `make check` fails when `docs/pipeline-status.md` is stale. Every maintained doc has `status`, `updated`, `owner` frontmatter.
- Every commit message ends with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

## Review Focus

1. Challenger whose named control is in another context (code or period) → `ambiguous control`, no delta. Pinned in Task 2.
2. A metric missing on either side → delta `None` and effect `unmeasured`, rendered `n/a`. Pinned in Tasks 2 and 5.
3. Empty registry, or a stage with records but no matched pair → renders "no evidence" / "no matched control", never crashes. Pinned in Tasks 2, 3 and 5.
4. Stage map or incumbents naming a `record_id` that does not exist → `check` fails loudly. Pinned in Tasks 1, 3 and 4.
5. Names, lessons and statuses containing `|`, `<`, `&` → escaped in the Markdown table and in HTML. Pinned in Tasks 3 and 5.

## File structure

```
research/control/registry_views.py   modify  expose dominates()
research/control/stage_map.py        create  STAGES, tag_stages, load_stage_map, draft_stage_map
research/control/stage_view.py       create  classify, effect, build_model
research/control/incumbents.py       create  load_incumbents, render_status
research/control/stage_page.py       create  render_page (HTML)
scripts/stages.py                    create  draft-map | render | check | build
scripts/dashboard.py                 modify  add the Pipeline tab
research/registry/stage-map.json     create  drafted, reviewed:false
research/registry/incumbents.json    create  authored from cycle-register prose
docs/pipeline-status.md              create  generated
Makefile, docs/README.md, docs/operations/daily-schedule.md   modify
tests/test_stage_map.py  test_stage_view.py  test_incumbents.py  test_stages_cli.py
tests/test_stage_page.py                                         create; tests/test_dashboard.py modify
```

### Task 1: Stage taxonomy and stage-map loader

**Files:**
- Modify: `research/control/registry_views.py` (`frontier_ids`, lines ~46-56)
- Create: `research/control/stage_map.py`
- Test: `tests/test_stage_map.py`

**Interfaces:**
- Produces:
  - `registry_views.dominates(a: dict, b: dict) -> bool`: `a`, `b` are metrics dicts holding non-None `net_cagr` and `max_drawdown`; true when `a` is at least as good on both and strictly better on one.
  - `stage_map.STAGES: tuple[str, ...]` = `("features", "market conditions", "position proposal", "target selection", "risk gate", "sizing", "execution")`
  - `class StageMapError(ValueError)`
  - `tag_stages(tags: list[str]) -> frozenset[str]`: maps `feature representation`→`features`, `selection`→`target selection`, `traffic gate`→`risk gate`, other stage tags to themselves; ignores non-stage tags.
  - `load_stage_map(path: Path, record_ids: set[str]) -> dict[str, dict]`: schema `stage-map/v1`, `{"schema": ..., "entries": [{"record_id", "stage_under_test", "control", "reviewed"}]}`; returns entries keyed by `record_id`.
  - `draft_stage_map(records: list[dict]) -> dict`: one entry per record, all `reviewed: False`. `stage_under_test` is the single normalised stage if the record has exactly one, `"multiple"` if it has more than one, else `None`. `control` is set only for `challenger`-tagged records and only when exactly one record in the same `(code, period)` has disposition `control`; otherwise `None`.

- [ ] **Step 1: Write failing tests** in `tests/test_stage_map.py` (helper `rec(rid, tags=(), disp="inconclusive", code="C1", period="2020–2025")` building a valid record like `tests/test_experiment_registry.py::rec`):
  - `test_tag_stages_normalises_spellings`: `tag_stages(["selection","traffic gate","CAPM"]) == frozenset({"target selection","risk gate"})`; `tag_stages(["feature representation"]) == frozenset({"features"})`.
  - `test_draft_marks_every_entry_unreviewed`: three records → `doc["schema"] == "stage-map/v1"`, `len(doc["entries"]) == 3`, every `reviewed is False`.
  - `test_draft_stage_under_test_rules`: tags `["sizing"]`→`"sizing"`; `["target selection","traffic gate"]`→`"multiple"`; `[]`→`None`.
  - `test_draft_control_only_when_context_has_exactly_one_control`: challenger with one `control` sibling → `control == sibling id`; with two → `None`; non-challenger → `None`.
  - `test_load_rejects_unknown_record_id`: entry for `"ghost"` with `record_ids={"a-1"}` raises `StageMapError` whose message contains `ghost`.
  - `test_load_rejects_bad_stage_and_bad_schema`: `stage_under_test="foo"` and `schema="x"` each raise `StageMapError`.
  - `test_load_returns_entries_by_record_id`.
  - `test_dominates_tie_is_false_both_ways`: equal metrics → `dominates(a,b)` and `dominates(b,a)` both `False`.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_stage_map -v`. Expected: ImportError/FAIL.
- [ ] **Step 3: Implement** the above. In `registry_views.py` move the nested `dominates` out of `frontier_ids` unchanged and call it from there. Allowed `stage_under_test` values on load: a member of `STAGES`, `"multiple"` or `None`; `control` is a `record_id` or `None` and, when set, must also be in `record_ids`.
- [ ] **Step 4: Run** `python3 -m unittest tests.test_stage_map tests.test_experiment_registry -v`. Expected: PASS (existing registry tests unchanged).
- [ ] **Step 5: Commit** `git add research/control/registry_views.py research/control/stage_map.py tests/test_stage_map.py && git commit -m "Add stage taxonomy and stage-map loader"` (plus the trailer).

### Task 2: Stage view model

**Files:**
- Create: `research/control/stage_view.py`
- Test: `tests/test_stage_view.py`

**Interfaces:**
- Consumes: Task 1 `STAGES`, `dominates`; entries as returned by `load_stage_map`.
- Produces:
  - `POLICY_METRICS = ("net_cagr", "max_drawdown")`; `DIAGNOSTIC_METRICS = ("calmar", "sharpe", "longest_underwater_sessions", "longest_underwater_days")`
  - `classify(record: dict, entry: dict | None) -> str`: a member of `STAGES`, `"unclassified"` or `"unattributable"`.
  - `effect(challenger: dict, control: dict) -> str`: arguments are metrics dicts; returns `improved` (challenger dominates), `worse` (control dominates), `tie` (equal on both), `tradeoff` (otherwise), `unmeasured` (either policy metric `None` on either side).
  - `build_model(records: list[dict], stage_map: dict[str, dict]) -> dict` with keys `stages`, `unclassified`, `unattributable`, `contexts`. `stages[name]` = `{"records": [record_id], "pairs": [pair], "effects": {effect: n}, "dispositions": {disposition: n}}` for **every** stage in `STAGES`. `pair` = `{"challenger": id, "control": id|None, "status": "matched"|"ambiguous control", "effect": str|None, "disposition": str, "delta": {metric: float|None}}`; `delta` covers `POLICY_METRICS + DIAGNOSTIC_METRICS` as challenger minus control, `{}` unless matched. `contexts` maps `"code · period"` → record ids in input order. `effects` and `dispositions` count pairs by the challenger's disposition.

- [ ] **Step 1: Write failing tests** (`rec` helper with `metrics`, `tags`, `context`):
  - `test_classify_rules`: `None` entry → `"unclassified"`; `reviewed False` → `"unclassified"`; reviewed `"multiple"` → `"unattributable"`; reviewed `"sizing"` → `"sizing"`.
  - `test_effect_cases`: challenger (cagr .30, dd .20) vs control (.25, .30) → `improved`; (.20,.30) vs (.25,.20) → `worse`; (.30,.30) vs (.25,.20) → `tradeoff`; identical → `tie`; `max_drawdown` missing → `unmeasured`.
  - `test_gated_t11_pair_is_a_tradeoff_with_both_deltas`: control (1.1967, .5126), challenger (.9203, .3690), challenger disposition `retire` → pair `effect == "tradeoff"`, `delta["net_cagr"]` ≈ -0.2764 and `delta["max_drawdown"]` ≈ -0.1436 (`assertAlmostEqual(..., places=4)`), model `effects == {"tradeoff": 1}` and `dispositions == {"retire": 1}` in that stage.
  - `test_control_in_other_period_is_ambiguous` (Review Focus 1): reviewed control with a different `period` → `status == "ambiguous control"`, `delta == {}`, `effect is None`.
  - `test_challenger_without_named_control_is_ambiguous`.
  - `test_missing_metric_gives_none_delta_not_zero` (Review Focus 2): control without `calmar` → `delta["calmar"] is None`.
  - `test_unattributable_and_unclassified_stay_out_of_stage_cells`.
  - `test_empty_registry_has_every_stage_with_zero_counts` (Review Focus 3): `build_model([], {})["stages"]` has all 7 keys, each with empty `records`/`pairs`.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_stage_view -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** Challengers are records with tag `challenger`; their stage is `classify(...)` of their own entry; a pair is matched only when the entry is reviewed, names a control that exists in the input, and that control shares `context.code` and `context.period`. Controls and every other record are counted in `records` of their classified stage but produce no pair.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit** `git add research/control/stage_view.py tests/test_stage_view.py && git commit -m "Add stage view model with matched-control effects"`.

### Task 3: Incumbents and the status document

**Files:**
- Create: `research/control/incumbents.py`
- Test: `tests/test_incumbents.py`

**Interfaces:**
- Consumes: `STAGES`; `build_model` output; `registry_views.updated_date(records)`.
- Produces:
  - `AVAILABILITY = ("implemented", "unverified", "blocked", "planned")`; `class IncumbentsError(ValueError)`
  - `load_incumbents(path: Path, record_ids: set[str]) -> dict[str, dict]`: schema `incumbents/v1`, `{"schema": ..., "incumbents": [{"stage","algorithm","identity","justified_by","availability","last_changed","scope"}]}`, keyed by `stage`. Errors: unknown stage, duplicate stage, availability not in `AVAILABILITY`, `justified_by` not in `record_ids` (allowed `None` only when `algorithm == "none"`), `last_changed` neither `None` nor `{"cycle_id": str, "date": str}`.
  - `render_status(records: list[dict], incumbents: dict[str, dict], model: dict) -> str`: Markdown with frontmatter (`status: active`, `updated: <updated_date(records)>`, `owner: project-maintainers`), title `# Pipeline status`, the line `<!-- Generated by scripts/stages.py render. Do not edit by hand. -->`, then a table `| Stage | Algorithm in use | Availability | Latest paired result | Records | Scope |` with one row per stage in `STAGES` order. Algorithm cell is `undeclared` when the stage has no entry. Latest paired result: for the stage's matched pair with the newest challenger `logged_at`: `f"{effect}, {disposition}: net CAGR {x:+.2f} pt, max DD {y:+.2f} pt"` (deltas ×100; `n/a` for `None`); `no matched control` if the stage has records but no matched pair; `no evidence` if it has none.

- [ ] **Step 1: Write failing tests**:
  - `test_load_rejects_missing_justification_and_bad_values` (Review Focus 4): `justified_by="ghost"`, availability `"live"`, duplicate stage, unknown stage each raise `IncumbentsError`.
  - `test_none_algorithm_may_have_no_justification`.
  - `test_render_has_one_row_per_stage_in_order`: data rows (lines starting `| ` minus header and separator) == 7, in `STAGES` order.
  - `test_undeclared_stage_reads_undeclared`.
  - `test_latest_paired_result_text`: gated-T11 pair → row contains `tradeoff, retire: net CAGR -27.64 pt, max DD -14.36 pt`.
  - `test_no_matched_control_and_no_evidence_texts` (Review Focus 3).
  - `test_pipes_and_markup_are_escaped_in_cells` (Review Focus 5): algorithm `"A|B"` renders with the pipe replaced as `registry_views._cell` does (`/`).
  - `test_render_is_deterministic_and_has_frontmatter`.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_incumbents -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** Reuse `registry_views._cell` for cell escaping and `registry_views.updated_date`.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit** `git add research/control/incumbents.py tests/test_incumbents.py && git commit -m "Add incumbents declaration and status renderer"`.

### Task 4: `scripts/stages.py`, seed data, freshness check

**Files:**
- Create: `scripts/stages.py`, `research/registry/stage-map.json`, `research/registry/incumbents.json`, `docs/pipeline-status.md` (generated)
- Modify: `Makefile` (add `stages-check`, append it to `check`'s prerequisites and `.PHONY`), `docs/README.md` (map row)
- Test: `tests/test_stages_cli.py`

**Interfaces:**
- Produces: `scripts/stages.py` `main(argv: list[str] | None = None) -> int` with global options `--registry`, `--stage-map`, `--incumbents`, `--status-doc` (defaults: the repo files above and `docs/pipeline-status.md`) and subcommands `draft-map [--out PATH]` (refuses to overwrite an existing file, exit 1), `render`, `check`, `build [--dir PATH]` (added in Task 5). Errors print `error: ...` to stderr and return 1, as `scripts/experiments.py` does. `check` fails with a message containing `stale` when `--status-doc` differs from a fresh render and with `missing` when any of the three files is absent.

- [ ] **Step 1: Write failing tests** (tmp dir, small fixture registry written with `research.control.experiment_registry.append`):
  - `test_draft_map_writes_unreviewed_entries_and_refuses_overwrite`
  - `test_render_then_check_passes`
  - `test_check_fails_when_status_doc_edited_by_hand`: stderr contains `stale`, return `1`.
  - `test_check_fails_when_stage_map_names_missing_record` (Review Focus 4)
  - `test_check_fails_when_incumbent_justified_by_missing_record`
  - `test_check_fails_when_a_file_is_missing`: stderr contains `missing`.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_stages_cli -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `scripts/stages.py` following `scripts/experiments.py` structure; `render` writes the status doc, `check` renders in memory and compares.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Create seed data.** Run `python3 scripts/stages.py draft-map` (writes `research/registry/stage-map.json`, 110 entries, all `reviewed: false`). Author `research/registry/incumbents.json` by reading `docs/research-cycles.md` and `docs/architecture.md`: add an entry for a stage **only** where the prose names its current incumbent; set `availability` to `unverified`, `justified_by` to a real `record_id`, and `last_changed` to `null` unless a cycle changed it. Do not infer. Leave other stages without an entry (they render `undeclared`) and list them in the commit message.
- [ ] **Step 6: Wire and render.** Add to `Makefile`: target `stages-check` running `$(PYTHON) scripts/stages.py check`, added after `experiments-check` in `check` and to `.PHONY`. Add a `docs/README.md` map row: question "Which algorithm is in use at each pipeline stage?" → a link to `docs/pipeline-status.md` (generated; declared in `research/registry/incumbents.json`). Run `python3 scripts/stages.py render`.
- [ ] **Step 7: Verify.** `python3 scripts/stages.py check` → exit 0; `python3 scripts/check_docs.py` → "Documentation check passed"; `python3 scripts/experiments.py check` → passed (registry untouched, `git diff --stat research/registry/experiments.jsonl` empty).
- [ ] **Step 8: Commit** `git add scripts/stages.py tests/test_stages_cli.py research/registry/stage-map.json research/registry/incumbents.json docs/pipeline-status.md docs/README.md Makefile && git commit -m "Add stage-map, incumbents and generated pipeline status"`.

### Task 5: Pipeline page and dashboard tab

**Files:**
- Create: `research/control/stage_page.py`
- Modify: `scripts/stages.py` (`build`), `scripts/dashboard.py` (`PAGES`), `Makefile` (`stages` target: `scripts/stages.py build && scripts/dashboard.py`)
- Test: `tests/test_stage_page.py`; modify `tests/test_dashboard.py`

**Interfaces:**
- Consumes: Tasks 1-3 outputs.
- Produces: `render_page(model: dict, records: list[dict], incumbents: dict[str, dict], built: str) -> str`: one self-contained HTML page (light and dark via `prefers-color-scheme`, as `scripts/dashboard.py`) with four sections in this order: **Stage view** (one card per stage: algorithm in use, record count, matched pair count, effect counts, disposition counts), **Compare** (one table per context with the six registry metrics, `n/a` for `None`, an incumbent selector limited to that context's controls defaulting to its first control), **Trust** (per record: verbatim `evidence_status`, `evidence_class`, receipt link text, eligibility), **Cycle log** (newest first: date, `record_id`, stage, disposition, outcome, lesson). Each effect badge carries `data-effect="<effect>"`; every eligibility cell carries `data-eligibility="unassessed"`. All text is HTML-escaped. `scripts/stages.py build` writes `<dir>/stages.html`; `scripts/dashboard.py` `PAGES` gains `("stages.html", "Pipeline")` after `progress.html`.

- [ ] **Step 1: Write failing tests**:
  - `test_every_stage_card_and_bucket_present`: all 7 stage names plus `unclassified` and `unattributable` counts appear.
  - `test_no_improved_badge_when_none_exist`: pairs only `tradeoff`/`worse` → `'data-effect="improved"' not in page` and `'data-effect="tradeoff"' in page`.
  - `test_every_record_is_unassessed`: `page.count('data-eligibility="unassessed"') == len(records)`.
  - `test_markup_is_escaped` (Review Focus 5): record name `<script>x</script> & |` → `&lt;script&gt;` in page and `<script>x` not in page.
  - `test_missing_metric_renders_n_a_not_zero` (Review Focus 2).
  - `test_empty_registry_renders_every_section` (Review Focus 3): four section headings present, no exception.
  - In `tests/test_dashboard.py`: `test_pipeline_tab_appears_only_when_page_exists` (tab text `Pipeline` present with `stages.html`, absent without).
- [ ] **Step 2: Run** `python3 -m unittest tests.test_stage_page tests.test_dashboard -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `render_page`, the `build` subcommand (reads registry, stage map, incumbents; `built` is a local timestamp string) and the `PAGES` entry.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Smoke check.** `python3 scripts/stages.py build --dir /tmp/stages-smoke && python3 scripts/dashboard.py --dir /tmp/stages-smoke`, then open `http://localhost:<port>` after `python3 -m http.server --directory /tmp/stages-smoke --bind 127.0.0.1 <port>`; confirm the Pipeline tab shows 7 stage cards, 44 `unclassified` records and no `improved` badge. Stop the server.
- [ ] **Step 6: Commit** `git add research/control/stage_page.py scripts/stages.py scripts/dashboard.py Makefile tests/test_stage_page.py tests/test_dashboard.py && git commit -m "Add Pipeline tab: stage view, compare, trust and cycle log"`.

### Task 6: Operations note and evidence index (revised during execution)

The original Task 6 also added a `render_latest` guard to `scripts/performance.py` so a stale
`leverage-latest.json` source would be skipped. It was **dropped**: `scripts/performance.py`,
`reporting/leverage.py` and `reporting/strategy_suite.py` are byte-pinned in
`research/compatibility.json` (`protected_files`), and editing any of them fails
`tests.test_package_compatibility` and `tests.test_dependency_boundaries`. The stale pointer is
untracked `.local/performance/leverage-latest.json` state; repointing its `source` and
`directory` to the current checkout is a data fix for the owner, not a code change.

**Files:**
- Modify: `docs/operations/daily-schedule.md` ("Single entry page"), `docs/research-evidence-index.json` and `.md` (regenerated with `scripts/current/research_index.py --write`, because two new files under `docs/tasks/` change the generated index)

- [x] **Step 1: Document** the Pipeline tab (`make stages`, inputs, `unassessed`, `unclassified`, the status document) and update `updated:` frontmatter.
- [x] **Step 2: Regenerate** the evidence index and confirm `scripts/current/research_index.py --check` passes.
- [x] **Step 3: Verify everything** with the project interpreter: `/path/to/.venv/bin/python -m unittest discover -s tests` (the worktree has no `.venv`; plain `python3` lacks pandas and NautilusTrader and reports unrelated import errors), then `scripts/check_docs.py`, `scripts/experiments.py check`, `scripts/stages.py check`.
- [x] **Step 4: Commit** `git add docs/operations/daily-schedule.md docs/research-evidence-index.json docs/research-evidence-index.md docs/tasks/2026-11-17-dashboard-redesign-design.md docs/tasks/2026-11-17-dashboard-redesign-plan.md && git commit -m "Document the Pipeline tab; regenerate evidence index"`.

## After the code lands (owner work, not a task)

Review `research/registry/stage-map.json`: for each record read its study document, set `stage_under_test` and, for challengers, the matched `control`, then set `reviewed: true`. Until then those records show as `unclassified`. Confirm or correct each entry in `research/registry/incumbents.json` and change `unverified` where the owner has verified it.
