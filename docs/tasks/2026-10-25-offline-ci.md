---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Offline CI

Task state: implementation complete; hosted execution blocked by Actions budget.

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

## Validation and blocker

Local `make check` passed: documentation/link checks, dependency consistency and
27 offline tests. YAML structure validation confirmed both triggers, read-only
permissions and the final `make check` step. The branch is based directly on
`a5a73ec9a6fd65395d40fdace7994172d1dc42f8`; existing skills/research PRs were not changed.

At implementation head `799fc3de81ac13dc6d138b548b73adfa84261892`, GitHub created
both [push](https://github.com/kenfuliang/quant-trading-lab/actions/runs/40236043044)
and [PR](https://github.com/kenfuliang/quant-trading-lab/actions/runs/40236044073)
runs. Both failed before any job steps ran. Their check annotations say:
“The job was not started because an Actions budget is preventing further use.”
No job logs or hosted dependency/test results exist for these runs. This is an
account budget restriction, not evidence of a workflow installation/test failure.

The workflow is implemented, but Ubuntu dependency installation and test execution
remain unverified. The user/account administrator must resolve the Actions budget
before rerunning both events. The agent changed no billing, spending limit,
repository visibility, runner configuration or merge policy. PR #3 remains draft.
The final documentation-only update records this blocker; its runs may encounter
the same restriction until account state changes.
