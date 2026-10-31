---
status: active
updated: 2026-10-28
owner: project-maintainers
---

# T11 gated Alpaca paper launch readiness

**Blocked; not launched.** User authorized a USD10,000 cap and one supervised
paper session. No orders, cancellations, account changes or live operations occurred.
[Redacted receipt](evidence/2026-10-28-alpaca-t11-readiness.json).
The [Alpaca SOP](../operations/alpaca-paper.md) remains the existing adapter owner;
this task does not expand its one-SPY-share order whitelist.

```mermaid
flowchart LR
    A[Paper account and24 asset checks: passed] --> B[T11 port and indicator/data parity: missing]
    B --> C[Multi-ETF staged execution and recovery: missing]
    C --> D[Reviewed USD10000 order plan]
    D --> E[One supervised paper session: not started]
```

One existing read-only preflight passed against the fixed paper host. The ACTIVE
USD paper account had no positions or open orders, and cash covered the chosen
cap. A separate bounded GET-only asset inspection found all24 declared T11
indicator/possible target symbols active and tradable. This is metadata, not
verified current-session data coverage, per-symbol buying power or fill readiness.
Credentials stayed in their ignored local source and were never printed/exported.
Private account/HTTP responses remain in ignored local run folders.

The checked broker clock was closed; next open was2026-10-28 06:30 America/Los_Angeles.
The existing script `preflight` was used; `session` was not run. It would run
SPY EMA rather than T11. No background trader or next-open scheduler is installed.
No paper-performance metric, Calmar or financial result is inferred from these checks.

The frozen T11 source is the saved gated QuantConnect implementation, identified
by SHA in the receipt. It needs daily Wilder RSI/SMA inputs and adjusted histories,
a RAW-SPY EMA/volatility gate with persistent hysteresis/initialization, several
possible ETF positions and cash, and staged MOO reductions/buys. Its gate can
suppress inverse/volatility positions. The current adapter instead supports SPY
only, one share, first-open-minute DAY limits and no general partial-fill/restart
recovery. Relaxing its whitelist alone would not implement the requested algorithm.

Required next implementation: a separate pure-policy port with frozen initialization
and source parity checks; provider/data normalization and completed-close guards;
multi-ETF paper-only routing, capped allocation independent of whole-account equity,
staged own-order handling and durable partial-fill/unknown/restart reconciliation.
Only after those gates pass can a current reviewed order plan be executed in the
single supervised session. Preserve the original SPY integration and source studies.
No unattended operation, unrelated-position liquidation or new live authorization
is inferred from the requested pilot.

Source references: [Alpaca paper specification](https://docs.alpaca.markets/us/docs/paper-trading),
[opening order types](https://docs.alpaca.markets/us/docs/orders-at-alpaca),
[free historical SIP delay](https://docs.alpaca.markets/us/docs/market-data-faq).
No paid data/service was used. Readiness observations are time-specific and require
refresh before a later order-bearing session. This is operational evidence, not
a completed financial research cycle or an amendment to its closed budgets.
