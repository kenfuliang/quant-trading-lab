---
status: active
updated: 2026-10-27
owner: project-maintainers
---

# Dependency boundary enforcement and structural review

Work status: offline verification complete; hosted verification follows publication. Infrastructure-only follow-up on PR #6
head `0e6749645cbca30b73bfaaa6122416b675233590`.
[Architecture](../architecture.md#enforced-python-dependency-boundaries) owns module
rules, [workflow](../workflow.md) owns delivery, and
[receipt](evidence/2026-10-27-dependency-boundaries.json) records actual evidence.
Scope supports infrastructure reliability; roadmap priority and investment rules
remain unchanged. No new research cycle, financial trial, broker call or download.

## Acceptance and failure cases

- Extract four reviewer functions without changing their bodies; preserve their
  independence from the primary ledger. Replace all current script-helper imports.
- Make CI reject reverse layers, current-to-legacy imports, invalid Python, static
  cycles, unclassified new research modules and unsupported dynamic loading.
- Resolve relative/member/function-local imports and literal dynamic aliases;
  use an injected violation to demonstrate nonzero exit through the Make CI target.
- Preserve all 327 protected files, historical plans, reports, failed evidence and
  the manifest's existing protected-file hashes. Update only its active owner map.
- Show identical saved overall/annual review outputs and unchanged function ASTs;
  reject corrupt inputs, preserve failures and refuse an existing receipt overwrite.
- Run full `make check` and inspect the exact published PR commit's hosted checks.
  Earlier reorganization receipts remain historical evidence, not overwritten results.

## Implementation and recovery

Current study/review hash lists now name the extracted helper. New reviewer CLI
receipts identify both command and helper. No existing plan identity is rewritten
or budget reopened. Original legacy commands remain the compatibility route.
The primary dirty checkout and unpublished research remain untouched.

Rollback is reverting this follow-up commit: restore the PR's prior current imports
and Makefile routing, remove the new library/checks/tests and revert its active map
extension. No data, journal, tracking-store or dependency migration is involved.

## Verification

`make check` passed 400 tests, documentation checks for 91 files, dependency
validation and the boundary check across 55 current modules. The 327 protected
files and existing protected hash map are unchanged. Failure-injection tests prove
nonzero CI-target exit; saved-review extraction passes function-AST, output, input
preservation and receipt-overwrite checks. The receipt records limitations.

## Structural rescore

These are explicit engineering judgments using the prior review's same dimensions
and weights: 5 is partial, 8 clear/tested, 10 consistently enforced/verified. They
are not independently measured product quality, financial evidence or operational
readiness. Weighted score moves from **7.1 to 7.8/10**.

| Perspective | Weight | Before | After |
| --- | --- | --- | --- |
| Responsibility and ownership | 15% | 8 | 8.5 |
| Dependency boundaries | 15% | 6 | 8.5 |
| Discoverability and onboarding | 10% | 6.5 | 6.5 |
| Frozen evidence preservation | 15% | 9 | 9 |
| Single source of truth | 10% | 7.5 | 8 |
| Content and report structure | 10% | 8 | 8 |
| Automated structural checks | 10% | 6 | 8 |
| Growth across research families | 10% | 6 | 6 |
| Evidence recovery and portability | 5% | 5 | 5 |

Ownership and source-of-truth scores improve because reusable reviewer code has an
explicit library owner and current callers cannot fall back to frozen code. The
boundary and automation scores improve because invalid edges have executable CI
failure cases. Static checking is not complete runtime enforcement. Discoverability,
research-family coverage, content completeness and restore proof are unchanged;
this change earns no score increase in those dimensions.

## Lesson and next action

Folder names alone do not enforce architecture. Extract reusable behavior without
changing its mathematics, then test both allowed directions and rejected edges.
Preserving a frozen implementation is compatible with preventing new code from
importing it. The next bounded structural task is a generated evidence index;
restore proof, contributor licensing and report completeness remain separate gaps.
