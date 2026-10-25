---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Offline CI

Task state: implementation complete; hosted validation pending.

Scope: a separate PR based on `main`, without importing skills or research changes.
The [development workflow](../workflow.md#continuous-integration) owns the CI contract.

Acceptance: pull requests and pushes trigger a pinned Python 3.12 job that installs
locked dependencies and runs `make check`; the GitHub run must establish the actual
hosted result. Failed checks must fail the job. No broker, credentials, services,
financial trials, deployment or branch-protection changes belong to this task.

Source review: NautilusTrader's test workflow at commit
`b23139911fd9fed82aed2811c5a8a373202b9480` uses immutable action pins, explicit
permissions and nonpersistent checkout credentials. This project adopts those
practices with hosted Ubuntu and installed wheels, retaining its existing checks
instead of copying upstream's Rust/release/self-hosted build system.

Validation results will be recorded after the PR's hosted run.
