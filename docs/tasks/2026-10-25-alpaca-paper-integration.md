---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Alpaca paper integration and SPY operational test

Work status: implementation and offline checks complete; broker fills remain
unverified pending market hours.
Canonical owner: [Alpaca SOP](../operations/alpaca-paper.md). This is an explicitly
requested M5 integration slice, not completion of the overall [roadmap](../roadmap.md).

## Scope and acceptance

User requested Alpaca paper integration with NautilusTrader, existing SPY strategy
testing and MLflow logs. Implement a supported public-interface extension because
the installed adapter inventory has no Alpaca adapter. Preserve existing dirty
work and all prior research. No upgrade, live account, paid feed or publication.

Fixed scope: original EMA50/200 long/cash signal, one-share sizing, DAY limit order
policy, USD1000/order maximum, two orders maximum, flat-start account, one first-open
decision, no unattended service. Requirements and failure gates are owned by the SOP.
The closed-market condition does not justify forcing an order or using old signals
as current ones. Existing strategy return assumptions are not ported to paper PnL.

Acceptance: native node/strategy/risk/execution path reaches fake broker, produces
native fills/positions and exits on an EMA reversal; duplicate quote/no-short/
limit/clock/unknown-submit behavior checked. Saved SPY signal sequence reaches
the same path. Authenticated paper preflight and redacted MLflow runs verified.
Actual broker-fill acceptance remains pending if the market is closed.

## Observations so far

- Installed NautilusTrader 1.231.0: no Alpaca adapter; custom bounded clients use
  its public Python/Cython live interfaces without editing installed packages.
- Read-only paper preflight: ACTIVE USD account, no trading/account blocks, SPY
  active/tradable, zero positions and zero open orders. All raw responses remain
  ignored locally; no account identifiers appear in this task.
- Broker clock closed; next open 2026-10-26 09:30 New York = 06:30 Los Angeles.
  Session command correctly returned `not_run_outside_first_open_minute` with
  zero submitted orders. No live or paper order was sent to Alpaca in this task.
- Offline synthetic and saved-SPY signal runs each produced two fake POSTs,
  two native fills and a final flat native position. Fake fills/timestamps do not
  represent historical SPY execution or broker-fill evidence.
- Initial failures were local only: native logging bypass is prohibited in a live
  node, standard factory signature differs from sandbox-specific example, node
  disposal attempted to stop the caller-owned event loop, and native trade IDs
  have a 36-character bound. Corrected through public configuration/interfaces;
  raw failure logs are preserved under `.local/alpaca-paper/`.

## Final evidence and validation

`make check` passed 267 tests, documentation metadata/local links and dependency
consistency. Ten new paper-integration tests exercise the native lifecycle,
saved-SPY replay, complete fake session orchestration, unknown submit, partial-fill
halt, closed clock, quote limits, transport limits, warmup and journal gate.
`git diff --check` passed. No credentials found in publishable files; keys and
private broker responses remain ignored. No hosted CI, commit or publication.

The [redacted receipt](evidence/2026-10-25-alpaca-paper-integration.json) records
final source hashes/snapshots, private artifact paths and exact MLflow run IDs.
All three MLflow summary artifacts were downloaded and byte-compared with their
local originals; run parameters/status/evidence tags were also checked.

| Final-code run | Actual evidence | MLflow |
| --- | --- | --- |
| Synthetic native lifecycle | Two fake POSTs, two native fills, final flat position | [Run](http://127.0.0.1:5050/#/experiments/6/runs/19ea136c7ccc4ff395119cd4de7ababf) |
| Saved-SPY signal replay | Same bounded lifecycle on preserved signal inputs; synthetic timestamps/fills | [Run](http://127.0.0.1:5050/#/experiments/6/runs/e3e4ecb5770b481db3e57483f49e0833) |
| Authenticated paper session | Flat active account; market closed; zero submitted orders/fills | [Run](http://127.0.0.1:5050/#/experiments/6/runs/57defc2a975a43f4873191549c31c321) |

Earlier proof runs and local failures remain preserved. This is not a paper-fill,
financial-performance, full M5 completion or live-readiness claim. Next step is
the bounded session command in the SOP during the first regular-open minute;
unsupported partial/restart outcomes require manual reconciliation.
