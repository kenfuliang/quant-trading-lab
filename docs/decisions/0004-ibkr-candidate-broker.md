---
status: proposed
updated: 2026-11-08
owner: project-maintainers
---

# 0004: Interactive Brokers is a candidate broker, pending a comparison spike

Proposed 2026-11-08 and reworded the same day. It names a candidate for planning
and does not select a final broker. It does not enable paper orders, live
trading, account changes or any deployment; those need their own scoped
authorization.

## Decision

Treat Interactive Brokers, through the NautilusTrader `interactive_brokers`
adapter ([C19](../capabilities.md)), as one candidate for any real-money path.
The existing Alpaca slice is the other. Choose after a time-boxed comparison
spike (below). The [live-readiness plan](../live-readiness.md) owns the gates and
acceptance evidence, which are broker-agnostic until G3.

## Why IBKR is a candidate

- The pinned Nautilus ships an IB data and execution client, so native risk,
  reconciliation and order lifecycle apply without a project-written adapter.
- The mandate allows margin and options; IBKR is the venue in the current
  documents that could support them. Actual permissions remain unverified.

## Why it is not yet the target

- Paper access is an external dependency that was never successfully enabled.
- Gateway needs user-managed login and two-factor approval. Third-party sources
  report a daily restart and a full login about weekly that automation tools
  cannot bypass; this is unverified here and must be observed.
- IBKR paper fills are simulated and may not capture slippage.
- Alpaca already has a working bounded paper session, with no adapter in
  Nautilus and a narrow SPY-only scope. That is a cost for it, not a ban.

## Comparison spike

Time-boxed, read-only or paper-only, and each item needs its own request:

- IBKR: get paper access working; run Gateway through one weekly cycle and record
  restarts, login prompts and entitlement or data limits.
- Alpaca: extend the existing paper session only as far as needed to observe
  fills and reconciliation.
- Both: run a shadow run (live read-only data, recorded would-be orders, no
  orders) and compare against a backtest replay on the same days.

Record observed effort, interruptions and fault-fixture results, then supersede
this record with the choice.

## Consequences

- The Alpaca code keeps its no-live-mode property. No live port, host or mode is
  added to any code path for either broker before G8 is authorized.
- Strategy and risk code stay broker-agnostic Nautilus code so G3 fixtures serve
  either choice.

## Revisit when

The spike finishes, paper access cannot be provisioned, the adapter fails the G3
fault fixtures, or the permitted instruments cannot cover the chosen strategy.
Supersede with a replacement link instead of rewriting it.
