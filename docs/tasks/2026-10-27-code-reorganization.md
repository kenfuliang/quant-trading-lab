---
status: active
updated: 2026-10-27
owner: project-maintainers
---

# Research package reorganization

Infrastructure-only change against main `033779f34e9944338ce474ead89aded352961791`.
[Architecture](../architecture.md#research-package-layout-and-frozen-compatibility)
owns placement; [development workflow](../workflow.md) owns acceptance.
No new financial research, downloads, services, broker activity or dependency changes.
The primary dirty checkout and its unpublished work remain outside this PR.

## Acceptance and failure cases

- Canonical implementations occupy features, policies, evaluation, control and
  studies/spy; their imports resolve within the new graph.
- Existing scripts/imports, plans, reports, reporting code and legacy tests retain
  their bytes. `research/compatibility.json` records baseline hashes and owners.
- Current commands use current implementations and new source identities.
  Historical gate defaults use a separate current plan/state/output namespace;
  existing evidence cannot be silently adopted as a new run.
- Legacy and current synthetic behavior agrees for signals, accounting and
  annual/temporal metrics. Hash drift and source mutation remain fail-closed.
- Both test graphs are discovered by `make check`. Source identity changes do
  not unlock a completed or failed experiment's budget.
- Rollback: revert this additive migration and Makefile/docs changes. No stored
  artifacts or dependency migration is required.

## Evidence and limits

Verification is recorded in [receipt](evidence/2026-10-27-code-reorganization.json).
An initial synthetic suite found an incorrect repository-root depth after nesting;
that path adaptation was corrected before final verification. Full financial
historical reruns are deliberately excluded: old strict preflight checks retain
any pre-existing hash/data failures. Passing synthetic parity is not financial
alpha, independent validation or broker readiness.

## Lesson

A byte-hashed source path is an experiment input. Retain its original implementation
as an immutable compatibility copy while directing new work to explicit canonical
packages. Do not replace it with a forwarding wrapper and pretend its hash survived.
