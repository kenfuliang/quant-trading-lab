---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Offline CI

Task state: implementation and hosted verification complete; PR remains unmerged.

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

## Repository publication and rerun

On the user's explicit request, repository visibility was changed to public on
2026-10-25. Before publication, Gitleaks scanned all local Git history (8 commits,
about 59 MB) and found no leaks. This is a credential scan, not a data-licensing audit.
Ignored environments, credentials and local artifacts were not published.

Both latest-head push and PR runs were retried. The PR job started executing on a
GitHub-hosted runner, so the previously observed budget block no longer prevented
startup. The earlier failure observations above remain historical evidence; hosted
installation and checks still need a completed run before being called verified.

Both reruns at head `c9b7a3e4232ba23a60df01c699c982afee15625b` completed
successfully: PR run `40236097865` (38 seconds), push run `40236094493`
(37 seconds). Logs confirm locked binary dependency installation, documentation
checks, dependency consistency and all 27 tests passed on Ubuntu/Python 3.12.
The final documentation update triggers new checks on its own head.

GitHub's [billing documentation](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
states that standard GitHub-hosted runner use is free for public repositories.
The workflow uses the standard `ubuntu-24.04` runner; no larger runner, release,
deployment, broker operation, billing setting or merge was introduced.
