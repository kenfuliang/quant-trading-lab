---
status: proposed
updated: 2026-11-08
owner: project-maintainers
---

# Path to real money: gates, principles and improvement loop

This file owns the ordered readiness gates between today's research and a
real-money pilot, plus the principles for improving on live evidence. The
[mandate](goals.md) owns objectives and open risk choices, the
[roadmap](roadmap.md) owns infrastructure sequence, [GRS](research-standard.md)
owns research cycles, [scoring](research-scoring.md) owns metric meaning, and the
[incident SOP](operations/incidents.md) owns failure handling. Broker candidates:
[0004](decisions/0004-ibkr-candidate-broker.md).

**This plan authorizes nothing.** Orders, paper sessions and live access each need
their own scoped request. Passing a gate is evidence for a decision, not the
decision. Statuses below were taken from repository records on 2026-11-08;
`make check` was not rerun for this review.

```mermaid
flowchart LR
    G0[G0 Mandate and risk budget] --> G1[G1 Data parity]
    G1 --> G2[G2 Strategy evidence]
    G2 --> G3[G3 Execution parity]
    G3 --> G4[G4 Risk controls and kill switch]
    G4 --> G5[G5 Persistence and recovery]
    G5 --> G6[G6 Monitoring and alerts]
    G6 --> G7[G7 Paper operation]
    G7 --> G8[G8 Small live pilot]
    G8 --> G9[G9 Scale or retire]
    G2 -. holdout read once .-> G8
```

## Principles

1. **Capital follows evidence.** Order of exposure: offline research, paper, small
   live pilot, scaled. Moving up needs the previous gate's receipt, never a good
   backtest alone.
2. **Protect an untouched evaluation window.** All current results use viewed
   history. Reserve forward time or a sealed holdout that no cycle reads until
   the candidate is frozen, and read it once. Failure retires the candidate; it
   is not retuned on that window.
3. **The loop optimizes the frontier, not one ratio.** Improvement means a
   candidate dominates its incumbent on net CAGR versus drawdown, with recovery,
   cost and tail guards, as in [scoring](research-scoring.md). Calmar stays a
   diagnostic.
4. **Live parameters change only through a closed GRS cycle** plus a paper
   rehearsal. No process edits its own live strategy, limits or risk gates.
5. **Safety does not depend on the strategy process.** The kill switch, loss
   limits and account checks run outside the code they constrain and fail closed.
6. **Default deny.** Paper identity checks (DU accounts, fixed loopback port) stay.
   No live port, host or mode exists in code before G8 is authorized.
7. **Unknown is not zero.** An unreconciled order, stale feed or missing fill
   halts submissions and waits for a human, per the incident SOP.
8. **Record failures with the same discipline as wins**, as GRS already requires.

## Gates

| Gate | Deliverable | Acceptance evidence | Roadmap link | Status 2026-11-08 |
| --- | --- | --- | --- | --- |
| G0 Mandate | Numeric capital at risk, leverage and concentration limits, daily and weekly loss budgets, pilot size, start date, tax treatment, rule when growth conflicts with drawdown | User-confirmed values recorded in the mandate | Mandate | Partial: objective, USD 300k and ~30% reassessment tolerance set; the rest open |
| G1 Data parity | One qualified source for research and live decisions, with known adjustment, calendar and timing rules | Audit receipt showing research and live bars agree on a sample, including corporate actions | M1 | Partial: free daily data; SIP versus IEX difference recorded; native catalog proof planned |
| G2 Strategy evidence | One frozen candidate respecting the drawdown tolerance after modeled costs | Sealed-holdout or forward result read once, trial count disclosed, leakage audit passed | GRS | Tooling now offline-tested: hash-chained trial ledger with a sealed-holdout read gate and a leakage audit of receipts against it (`tests/test_trial_ledger.py`, `tests/test_leakage_audit.py`, `scripts/check_trial_ledger.py`). No holdout has been sealed and no candidate frozen. Not met: all evidence is viewed history; leading candidate's recorded max drawdown (36.9%) exceeds tolerance |
| G3 Execution parity | Strategy runs on the Nautilus live node through the IB client, with the same decision and fill timing as the backtest | Fault fixtures (reject, duplicate, partial fill, disconnect after submit, restart) pass offline; replay matches backtest orders | M5 | Not met: no IB execution client in use; multi-ETF bridge absent. Offline fault fixtures now cover reject, expire, timeout, poll failure, failed cancel and slow ack against a fake broker (`tests/test_native_failure_modes.py`) |
| G4 Risk controls | Native limits configured plus portfolio drawdown, leverage and daily-loss stops and an independent kill switch | Fixture shows each limit halts or reduces; kill switch tested to cancel and flatten | M5 | Partial offline: pre-submit `RiskGate` and file-sentinel kill switch with operator CLI, tested against the fake broker (`tests/test_pretrade_gate.py`, `tests/test_kill_switch.py`, `tests/test_native_halt.py`). Not met: flatten procedure, unrealized-loss stop, any broker-side verification |
| G5 Persistence and recovery | Chosen state backend, order journal and restart reconciliation | Disposable crash, restart and restore drill with no blind resubmission | M3 | Partial offline: atomic journal writes and session-journal recovery by client id (`tests/test_durable_journal.py`, `tests/test_native_recovery.py`). Not met: Nautilus cache persistence, general position recovery, any broker-verified restart |
| G6 Monitoring | Freshness, health and alert path for dead worker, stale feed, capture failure, unreconciled state | Injected faults produce visible alerts with redacted account data | M4 | Partial offline: health view, alert sinks and `scripts/ops_status.py` read the real shadow, kill-switch and journal artifacts (`tests/test_health.py`, `tests/test_health_producers.py`). Not met: scheduled running, a tested remote alert path, dead-worker detection |
| G7 Paper operation | Chosen broker's paper account working and a supervised multi-week run, plus a read-only shadow run on live data | Receipts for orders, fills, reconciliation, uptime and tracking error against replay | M5 | Shadow runner and tracking error implemented offline (`tests/test_spy_shadow.py`, `tests/test_spy_signal_parity.py`); live `--fetch` collection not exercised. Blocked for IBKR (paper access never enabled); Alpaca has a read-only preflight only; zero orders submitted |
| G8 Small live pilot | Separately authorized live session at the G0 pilot size with stop rules fixed beforehand | Daily reconciliation, measured slippage versus model, no breach of loss limits | Separate request | Not started |
| G9 Scale or retire | Decision from live evidence | Live-versus-paper-versus-backtest comparison; scale only if tracking error and drawdown are inside bounds | Separate request | Not started |

## Improvement loop on live evidence

```mermaid
flowchart TD
    L[Live and paper receipts] --> M[Tracking error, slippage, breaks, drawdown, uptime]
    M --> Q{Gap vs. backtest?}
    Q -->|Execution or data| I[Infrastructure change cycle]
    Q -->|Strategy| R[GRS cycle against sealed evidence]
    I --> P[Paper rehearsal]
    R --> P
    P --> D[Human decision to promote]
    D --> L
```

Added metrics, in addition to those in [scoring](research-scoring.md): tracking
error of paper and live versus replay, realized versus modeled slippage and cost,
reconciliation breaks, halts and their causes, and feed uptime. They measure the
platform and are not investment returns.

## Immediate next steps

1. User resolves the G0 numbers (below) and the IBKR paper access request.
   Broker choice waits for the comparison spike in the decision record.
   Start a read-only shadow run, which needs neither broker's execution path.
2. Reserve the G2 holdout and write the freeze rule before any further tuning.
3. Run the existing leakage-audit skill on the leading candidate's code.
4. M1 catalog proof and G3 fault fixtures can proceed offline without any broker access.

## Decisions only the user can make

- Capital allowed at risk, and the pilot size as a share of it.
- Whether the 30% drawdown tolerance or the growth target gives way if no candidate
  meets both.
- Permitted instruments: leveraged ETFs, margin, options, shorting.
- Who monitors a live session and how fast they must respond.
- Whether tax is evaluated after personal taxes.
