---
status: active
updated: 2026-10-29
owner: project-maintainers
---

# T11 gated paper runner implementation

User selected T11 + risk gate, completing its runner first. Authorization remains
USD10,000, one supervised paper session. No new historical financial runs,
scheduling, live trading or dependency changes are included.

Canonical operating owner: [Alpaca paper SOP](../operations/alpaca-paper.md).
Historical [readiness receipt](2026-10-28-alpaca-t11-readiness.md) is preserved.

## Frozen acceptance

- Separate multi-ETF preparation from the existing one-share SPY adapter.
- Flat-start allocation at most USD10,000, 90% deployment times gate cap;
  no borrowing, shorts, pyramiding, more than three targets or substituted policy.
- Produce whole-share auction-limit proposals from causal, fresh observations.
  Limits protect submitted purchase consideration, not subsequent market value.
- Persist an exclusive, atomic, fsynced intent before submission. A reservation
  survives restart; an unknown submission never becomes automatically retryable.
- Reconcile client ID, symbol, side, quantity, type and cumulative partial fills;
  preserve unknown, rejected and canceled outcomes. Never cancel unrelated orders.
- Fake-broker tests exercise duplicate/restart and malformed-state failures;
  normal verification remains offline and order-free.
- Keep the order-bearing broker CLI disabled until qualified T11 signals and
  a native multi-instrument execution bridge pass their own end-to-end checks.
  This preparatory slice is not a second live order-management system.

## Current evidence

Authenticated read-only preflight passed at 2026-10-29T06:47:16Z (UTC): flat
account, no open orders, market closed; no orders submitted. Private receipt:
`.local/alpaca-paper/runs/20261029T064715124141Z-preflight/summary.json`.
The earlier sandbox network failure remains preserved separately.

Implementation and offline acceptance results are recorded below on completion.

## Implemented preparation and validation

- [x] Separate offline proposal builder: 24-symbol allowlist, at most three
  positive targets, 1/.5/0 gate cap, whole-share auction limits and cash reserve.
- [x] Exclusive atomic/fsynced intent journal; restart duplicate prevention,
  cumulative partial-fill observations and terminal/identity consistency checks.
- [x] Five focused tests cover caps, quote freshness, causality, cutoff, locks,
  restart, duplicate observations, partial cancellation and contradictory fills.
- [x] `make check` passed: 520 offline tests, 167 documentation files and package
  consistency. `git diff --check` passed. Zero new financial runs or paper orders.
- [ ] Qualified live T11 feature/gate producer; asserted qualification is not proof.
- [ ] Native multi-instrument execution bridge, aggregate cap and staged trades.
- [ ] End-to-end fake-broker native integration, failure recovery and supervised
  actual paper session. The existing SPY native adapter remains unchanged.

**Disposition: preparatory slice verified; full runner incomplete and launch
blocked.** No new order-bearing CLI, overnight orders, scheduler or service was
created. Proposed auction limits change source execution and do not establish
historical T11 parity. No performance score or leaderboard entry is appropriate.

Private validation log: `.local/t11-paper-preparation/make-check.log`.
Redacted [receipt](evidence/2026-10-28-t11-paper-preparation.json) records code hashes.


## October29 read-only rehearsal checkpoint

The [latest rehearsal](2026-10-29-t11-paper-rehearsal.md) adds a separate prototype
feature/gate/policy preview from fresh Alpaca data, with zero orders. This makes
concrete progress beyond synthetic proposal fixtures; operational qualification
and the native multi-ETF bridge remain incomplete. No readiness requirement is
waived and no actual paper session is claimed.
