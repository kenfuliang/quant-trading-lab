---
status: proposed
updated: 2026-11-08
owner: project-maintainers
---

# 0004: Interactive Brokers is the target broker for any real-money path

Proposed 2026-11-08 at the user's direction. It selects a target for planning and
for the order of future work. It does not enable paper orders, live trading,
account changes or any deployment; those need their own scoped authorization.

## Decision

Plan the path to real-money trading around Interactive Brokers through the
NautilusTrader `interactive_brokers` adapter ([C19](../capabilities.md)). The
[live-readiness plan](../live-readiness.md) owns the gates and acceptance evidence.

## Why

- The pinned Nautilus ships an IB data and execution client, so native risk,
  reconciliation and order lifecycle apply without a project-written adapter.
- The mandate allows margin and options; IBKR is the venue in the current
  documents that could support them. Actual permissions remain unverified.
- The existing Alpaca slice is a narrow SPY pilot with a hardcoded paper host. It
  stays as bounded integration evidence and is not extended into the live path.

## Consequences and costs

- Paper access is an external dependency that was never successfully enabled.
  Until it is, every gate from G7 onward is blocked.
- Gateway runs on the user's Mac and needs user-managed login and two-factor
  authentication, so unattended operation is a known gap to design for.
- IBKR paper fills are simulated, so paper evidence verifies plumbing and
  reconciliation, not slippage or queue position. G8 exists for that reason.
- The Alpaca code keeps its no-live-mode property. IBKR live access is not added
  to any code path until G8 is separately authorized.

## Revisit when

Paper access cannot be provisioned, the adapter fails the G3 fault fixtures, or
the permitted instruments cannot cover the chosen strategy. Supersede this record
with a replacement link instead of rewriting it.
