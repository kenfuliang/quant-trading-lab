---
name: trade-local-ops
description: Check the local trading environment, diagnose failed runs, or perform requested read-only broker observation using this project's operating procedures.
---

# Local trading operations

Find the repository root containing `paper_trading/` and `docs/README.md`.
Read root README for current verification status and `docs/operations/local.md`
for commands and completion criteria.

- Environment check: run local checks and report their actual scope.
- Requested broker observation: select the provider-specific SOP: IBKR uses
  `docs/operations/paper-connection.md`; Alpaca uses
  `docs/operations/alpaca-paper.md`. Verify prerequisites and use only the requested
  read-only observation/preflight mode. Session/order modes are separate scope.
- Failure, stale data, crash, or uncertain external outcome: read
  `docs/operations/incidents.md`; preserve evidence before recovery.

Stop the requested check at its documented completion or failure condition.
Report mode, checks/results, redacted evidence, uncertainty, and next action.
Never label a successful configuration check as broker or order verification.
The procedures govern existing authorization; they do not authorize account
changes, order submission, cancellation, or liquidation.
