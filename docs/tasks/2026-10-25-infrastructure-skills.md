---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Infrastructure adviser scope and calling skills

Completed instruction/documentation change requested by the user. The
[team catalog](../skills.md#infrastructure-calling-map) owns routing and readiness;
[advisory remit](../advisory-team.md#ask-infra) owns business coverage;
[data library](../data-library.md#bounded-acquisition-procedure) owns acquisition.
No portfolio priorities or operational permissions changed.

## Change

Expanded ask-infra from component advice to activity-specific readiness across
source/universe, qualification/actions/timing, accounting interfaces, reproducible
runs/tracking/CI, runtime integration and operational stewardship. It selects a
minimum useful prerequisite chain and returns evidence and failure behavior.

Added trade-data-acquisition for the repeated, explicitly requested fixed-collector
workflow. It hands frozen outputs to data-audit for a separately requested study
fitness verdict. Existing capability-review, source intake, infra-change and
local-ops remain the execution routes; quant/risk/algo/ML-infra/director are scoped
consultations. Corrected provider routing in local-ops and infra-change so Alpaca
checks use their own SOP rather than the IBKR observation procedure.

## Scenario walkthroughs

These are same-agent instruction walkthroughs against saved project evidence,
not independent behavioral evaluation or new operational execution.

| Request | Selected route and observed contract result |
| --- | --- |
| What blocks a reliable comparison over the downloaded current SPY holdings? | ask-infra → data-audit/ask-quant: acquisition receipt shows 500 instruments, 459 full-window, 41 partial, three unavailable. Actions and historical membership remain unqualified; no backtest or new download implied |
| Download every US stock with the existing collector | data-acquisition inspects fixed current-SPY scope: unsupported universe, so route a scoped collector change or report blocker; no claim of generic collector/resume and no new requests |
| Check Alpaca paper connectivity | local-ops selects Alpaca preflight SOP and its requested read-only mode; no session/order invocation or IBKR command substitution |
| Make MLflow importer recover from interrupted imports | infra-change with ask-ml-infra lineage advice: require exact input/run identity and offline failure/idempotency acceptance; no server startup, training or broker operation merely for consultation |

## Validation and limits

- `make check`: exit 0; documentation/catalog parity, dependency consistency and
  **272 offline tests** passed.
- Skill Creator `quick_validate.py`: ask-infra and trade-data-acquisition passed
  using the existing isolated MLflow Python environment. The core environment
  lacks the validator's PyYAML dependency; no dependency was added or changed.
- Regenerated the catalog-driven team PNG and visually inspected it; adjusted
  project-workflow spacing for the additional entry and regenerated successfully.
- `git diff --check`: passed.

Existing collector evidence is linked from its acquisition procedure; this update
performs no acquisition, simulation, service startup or broker call. New instructions do not implement general ingestion,
corporate-action processing, historical-universe reconstruction or recovery.
