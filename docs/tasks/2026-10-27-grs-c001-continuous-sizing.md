---
status: active
updated: 2026-10-27
owner: research-maintainers
---

# GRS-C001: continuous sizing versus the discrete gate

Work status: closed, inconclusive; one control attempt, zero eligible comparisons.
Standard: [GRS-1.0](../research-standard.md). This is the first newly indexed cycle,
not the first historical project experiment. [Cycle register](../research-cycles.md).

## Question and scope

Improve the existing sizing stage, changing only its allocation policy. Does the
previously proposed continuous20%volatility cap produce a strictly shorter longest
observed peak-to-recovery/end interval and no deeper full-path drawdown than the
retained discrete EMA/volatility gate at both5and10bp per side? A one-session
strict duration reduction is the fixed integer path-screen threshold; drawdown
fraction tolerance1e-10. A path-screen pass is not sufficient to accept an
unspecified sacrifice in CAGR. Growth remains a separate unapproved tradeoff.

This executes the rules/criteria from the preserved
[2026-10-25 design](../../research/plans/spy-continuous-cap-development-v1.design.json)
under a new [executable plan](../../research/plans/grs-c001-continuous-sizing-v1.json).
The old design remains unchanged, including its original zero-attempt status.
The new request explicitly starts a finite cycle; it does not reopen any old
budget. Maximum8financial attempts,900seconds,oneworker,zero retries,zero new
market requests/packages/services/MLflow imports/agents/broker actions/publication.
Stop on first input, timing, account, parity or execution failure.

## Parent, data and controls

Incumbent: the frozen price-peak-removed EMA/volatility state recurrence in
[risk-gate ablation](../../research/risk_gate_ablation.py), retained in the
[robustness review](2026-10-25-rsi-gate-robustness-review.md). This cycle is a
model-specific diagnostic branch; it does not displace higher-return T11 or stock
momentum, nor choose an investment. Prior related gate, ablation, robustness,
label and feature studies have already viewed the history; all-project trial
counts have not been exhaustively reconstructed.

Saved SPY source hash992d9f62de93aa860ae00fc81d3810dbe0ac302a55102886fc5c50545130a8ba;
2004warmup;2005-01-03–2025-12-31;5,283evaluation sessions;USD300,000;
whole shares;target budget99%(1%sizing reserve);USD1/trade;5or10bp/fill;
fixed6%ACT360debit interest and zero cash credit. Dividends are modeled ex-date
cash credits, not verified payment-date cash. No native broker parity, full
retail-data/calendar/action/redistribution qualification or untouched holdout is
claimed. Numeric allocation=.99 is unchanged; the prior design's phrase99%reserve
was a wording error, retained in the original and corrected explicitly here.

Four policies per cost: plain EMA;half-sized EMA;frozen discrete gate;continuous
cap. All use the same EMA50/200 eligibility. Continuous cap uses20raw-close
returns' sample volatility×sqrt252, target=min(1,.20/sigma20)when positive, zero
when zero/unready. Decision uses only the prior completed close, shifted once.
No fitting or parameter choice occurs in this cycle. Replacing the discrete policy
also removes its confirmation memory; this does not isolate color discretization.

Fresh EMA/discrete controls must reproduce saved trades and all ledger fields
within the existing1e-7USDcontrol tolerance before accepting dependent results.
Independent Decimal account replay, independently recalculated full/annual ratios,
rolling/episode/tail metrics and input/artifact hashes are mandatory. If half EMA
is no worse on CAGR,drawdown and duration and better on at least one at both costs,
retire the continuous added-complexity claim. No scalar score rescues primary failure.

## Evidence and report readiness

Machine [receipt](evidence/2026-10-27-grs-c001.json), immutable raw/private outputs
in `.local/grs-c001/`, and cycle-specific plan/manifest retain every attempted case.
The runner is [incremental_sizing.py](../../research/incremental_sizing.py).
A first synthetic timing assertion compared date-only versus midnight timestamp
strings; its expected representation was corrected before plan freeze, with no
financial attempt. This engineering check is not a trading loss or a financial retry.

Report eligibility is assessed after audits and the frozen screen. Primary failure
requires a negative lesson and unchanged incumbent. A primary pass with unapproved
growth sacrifice remains a scoped tradeoff, not an unconditional performance win.
Any paper-style report must label development evidence and retain counterevidence.

## Completion

The first5bpEMAcontrol executed and stopped at the frozen whole-ledger parity gate.
Exactly one of eight attempts was consumed; seven were never launched. The budget
is closed with no retry or further financial simulation. Continuous sizing was
not evaluated, so this is neither evidence of its loss nor a rejected economic
hypothesis. The incumbent is unchanged.

Independent post-stop diagnosis on saved output found the trades identical and
all ledger fields except`effective_target_leverage` equal within1e-7USD. The old
field equals effective EMA eligibility0/1; the current field records nominal1
budget while flat too.1,019sessions differ in that diagnostic. The frozen strict
gate remains failed; this diagnosis does not retroactively relax it or relabel the
case completed. Decimal replay, full/annual calculations and temporal checks had
already completed before parity failed; raw outputs and traceback are preserved.

**Lesson:** qualify known diagnostic semantics on saved controls before launching
new financial attempts. The earlier historical receipt already disclosed this
representation issue; the new runner did not carry its compatibility contract
forward. Better evidence discipline catches an engineering issue without calling
it a strategy loss or quietly reusing unspent trials.

Next permissible question is a zero-financial read-only diagnostic adapter
verification; any resumed financial comparison needs a new explicit frozen budget,
retains this attempt in aggregate history, and must not tune the20%rule on observed
outcomes. No positive-performance paper is earned by this cycle.

### Read-only engineering follow-up

A narrow [legacy diagnostic contract](../../research/legacy_control_contract.py)
is now tested with two synthetic cases and the saved control output. It permits
only the recognized effective0/1-to-nominal1interpretation, checks all other ledger
fields and exact fills, and rejects financial or trade drift. It performs no
financial simulation and does not override the old frozen gate. The helper has
not been retrofitted into this closed runner; a new version must explicitly
adopt it before a separately bounded financial comparison.
