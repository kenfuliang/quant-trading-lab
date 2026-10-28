---
status: active
updated: 2026-10-27
owner: research-maintainers
---

# Stage-development skill and risk-gate exercise

Status: implementation and worked exercise prepared; offline implementation and one-stage exercise complete; exact-head hosted CI required before ready handoff.
Base `1c71c6267c78b130d932b191266c19820709aa28`. This is the user-requested
shared skill, RSI/catalog integration and one existing-stage test with zero
financial runs. It does not change policy rules or start a financial cycle.
The [catalog](../skills.md) owns discovery, [stage procedure](../research-development.md#individual-stage-development)
owns the component handoff, [RSI SOP](../operations/recursive-research.md) owns
execution handoffs and GRS remains the only research/adoption rule owner.
[Machine receipt](evidence/2026-10-27-stage-development-skill.json).

## Bounds and acceptance

One new project skill and one existing unchanged stage. One fixed 360-row synthetic
fixture, with healthy/shock, deliberately wrong consumer and invalid-input variants;
five component test methods. At most two full local check runs and focused checks
as needed; no financial launch, fitting, data download, service, broker activity or
RSI demo. Existing study budgets remain closed. Create a separate PR; no merge.

Acceptance: precise skill discovery; valid references/UI metadata; catalog/router/
SOP handoff; completed stage worksheet; positive checks and meaningful negative
integration controls; unchanged policy/evidence hashes; full offline checks and
exact-head hosted CI. Shape/wording checks alone do not prove the skill useful.

## Worked stage worksheet

| Field | Actual exercise |
| --- | --- |
| Identity and scope | Existing fixed traffic-light risk/sizing stage, `research/policies/risk_gate.py::frames` / `timeline` / `states`; parent is base commit above; source SHA in receipt. Characterization only, not the best-known portfolio or a new policy version. |
| One change and controls | Make its producer/consumer timing and actual-target semantics explicit in a worksheet and regression exercise. Policy source, thresholds, sizing, feature definitions and all financial assumptions unchanged. Hypothesis: contract checks reject double-lag and look-ahead consumers; falsifier: either wrong consumer is accepted. No new financial GRS cycle. |
| Inputs | Positive ordered unique daily OHLC in synthetic USD price units, fixture dates only (not a qualified trading calendar). Close-derived EMA/volatility/drawdown features use completed closes. Raw price fields retain their own timing; execution-day low/close are future accounting fields, never open-time decision inputs. |
| Outputs | `intended_target` is the actual long/cash portfolio fraction, gate values 0/0.5/1; `want_long` is Boolean eligibility; `base_target` is the underlying policy proposal. These decision fields are aligned to execution open already. EMA control `allocation_factor=1` is a nominal diagnostic even in cash; it is not actual exposure. |
| State and exceptional behavior | Full-history deterministic recomputation; warmup/unassessed targets become zero in this adapter. Missing/nonfinite or unordered/duplicate OHLC is rejected. Confirmation counters reset within recomputation; incremental streaming/restart is not implemented or inferred. |
| Verification | Synthetic price trend then 50% shock at completed close250. Exposure remains1 at open250 and becomes0 at open251. Future-close mutation leaves decisions through open250 unchanged. A second shift and a negative shift must each fail the same boundary check. Warmup, invalid inputs and nominal-versus-actual target checks are included. |
| Evidence | Five pure component checks in `tests/current/test_stage_development_risk_gate.py`; no ledger, account, order or financial runner is called. Actual exits/log hashes and source preservation are recorded in the receipt. |
| Disposition | Unchanged stage, characterized interface only. Financial comparison remains unassessed. The skill is instruction-available and exercised on one case, without a measured advantage versus working without it or coverage of all optional stages. |

```mermaid
flowchart LR
    P[Existing risk stage] --> C[Explicit field and timing contract]
    C --> T[Synthetic component exercise]
    T --> N[Double-shift and look-ahead controls rejected]
    N --> E[Evidence; policy unchanged]
```

## Skill application and lessons

Applied trade-stage-development by inspecting the current producer and consumer,
freezing unchanged characterization, filling the worksheet, selecting direct
component checks under the implementation workflow and recording the limited
engineering disposition. Advice, code implementation, financial evaluation and
adoption remain distinct handoffs. This is a self-authored worked exercise, not
blind evaluation or proof of generalized research-process improvement.

A mixed DataFrame is not uniformly available at one timestamp. Decision fields
are already lagged to the next open; current low/close belong to later accounting.
Also, nominal allocation diagnostics cannot replace the actual target. These
specific contracts change how a caller should integrate this existing component.

## Failures and remaining evidence

The initial focused run found a test-only date formatting mismatch: one timestamp
was date-only and the expected string included midnight. The fixture assertion now
compares parsed timestamps; no stage code changed. The skill validator required
PyYAML, absent from the core/bundled runtimes; an existing isolated MLflow Python
validated the skill without changing project dependencies. All attempted focused/
full checks and failures are retained in the receipt.
Synthetic success cannot validate data rights, economic value, learned market
regimes, target selection, a generic router or financial execution. Current RSI
adapters remain restricted; this skill does not register an additional adapter.
The incumbent, historical failures, frozen sources and original receipts stay
unchanged. Rollback removes the additive skill/template/tests and routing/view
changes, preserving all exercise logs and original evidence.


## Observed validation

All five component checks passed, including rejection of both deliberately wrong
shift consumers and nominal-versus-actual target composition. Both requirements
and standards reviewers independently ran the five focused checks and reported
zero remaining actionable findings. This remains one self-authored exercise with
review, not blind forward testing or a demonstrated research-process advantage.

The skill creator validator passed using an existing isolated Python environment
with PyYAML. `make check` passed **516 tests**, documentation checks for **102 files**,
boundary checks for **64 current modules**, dependency consistency and index coverage
for **14 entries / 12 published plans**. One of the two allowed full local checks
was used. All six scoped source/receipt hashes, 405 prior historical identities
and all 327 frozen files remain unchanged. The catalog PNG was regenerated with
the unchanged existing renderer and inspected for visibility and readiness labels.
No policy rules, financial portfolios, data, dependencies or closed budgets changed.
Exact published-head hosted CI is recorded separately on the PR.
