---
status: active
updated: 2026-10-27
owner: project-maintainers
---

# Bounded offline RSI integration

Work status: offline integration demonstrated; final clean-head verification and hosted PR checks pending.
Base: `4fc663164434e15b68324d8266ff421294af717b` (merged PR #6).
This is the user's requested integration of the local offline RSI foundation,
not new strategy research. [Architecture](../architecture.md#offline-rsi-foundation)
owns code/state boundaries, [RSI SOP](../operations/recursive-research.md) owns
handoffs and [GRS](../research-standard.md) retains research/adoption rules.
Native roadmap M1–M5 is unchanged. [Receipt](evidence/2026-10-27-rsi-integration.json).

## Frozen scope and bounds

One port candidate in a clean isolated main checkout. Port the existing three
RSI libraries, current CLI, four test modules, and the minimal read-only C001
helper. Canonical control modules import no frozen implementations or command
scripts. Original local sources, historical 449-test receipt, C001 failure and
all closed financial budgets remain unchanged; current ports get new identities.

At most two full local integration checks and one fresh demo. The demo has one
writer, 120 seconds aggregate, at most two registered subprocess launches and zero
financial slots; no automatic retry. Focused synthetic unit checks are separate
from that single recorded demo. No financial strategy runs, fitting, market-data
downloads, services, broker operations, dependency changes or upstream patches.
PR publication is explicitly requested; merge is outside this task.

## Dependency inventory and explicit split

Original local modules use flat imports and the old foundation CLI runs an
incremental-sizing preflight plus a test-file replay via `runpy`. The historical
runner would require publishing unrelated later study implementations and evidence.
It is therefore excluded, as predeclared in the bounded review's split condition.

The current adapter runs only this checkout's fixed saved-C001 checker, never the
historical runner. It has no execute/case options and requires the complete trusted
historical closure before reservation. Normal clean CI lacks private evidence:
preflight exits **2 / unavailable**; bad hashes/unsafe files exit **1 / failed**.
Neither is a successful check or an invitation to simulate. A valid standalone
`--evidence-root` is read only, not imported or executed. The checker authenticates
the pinned receipt, plan, source, standard, manifest/artifact and diagnostic-helper
bytes. Only the installed current helper executes, after its bytes match the
historical helper identity. Missing evidence stays unavailable on a fresh checkout.

The single fresh demo runs under an enclosing 120-second process timeout covering
preflight, setup, execution, adoption and report writing; the coordinator also bounds
its execution window separately. It first checks real saved evidence, then uses two synthetic
cases across two cycles, not the historical runner. It proves shared exhaustion,
cache reuse and explicit synthetic adoption/rollback. The original process-policy
win/loss/tie replay is preserved, not dynamically loaded or rerun. Its reference
answer grader remains covered by the ported tests. This closes offline integration;
financial-runner integration and general process superiority remain open.

## Acceptance checklist

- [x] Clean pinned main; hashes of original local inputs and base files recorded privately before edits.
- [x] Four minimal current libraries under `research/control/`, CLI under `scripts/current/`; dependency enforcement retained unchanged.
- [x] Original local source/receipts and prior protected historical files preserved; current identities recorded separately.
- [x] All 70 existing foundation tests ported, plus current CLI availability/integrity/attestation coverage; no financial test execution.
- [ ] Full clean-checkout offline checks pass; hosted exact-head checks pass separately.
- [x] Real saved preflight checks the complete local closure; CI covers synthetic mechanics and explicit unavailability without silent skip.
- [x] One bounded demo verifies exhaustion/restart/adopt/rollback; originals checked before/after.
- [x] Existing capability, architecture, SOP/catalog navigation and generated evidence-index owners updated.

## Failures

The second focused test run exposed macOS `/var` versus `/private/var` aliases in
the new missing-evidence test's patched root. The fixture now resolves both paths
before containment comparison. This was a focused unit-test failure; no financial
launch or real demo retry occurred. Logs are retained privately. Standards review also found that losing both execution
state files before the first launch could reset an existing program deadline.
The current coordinator now rejects that missing authority whenever the controller
preexisted or records prior activity; a zero-launch regression verifies no replacement
deadline/log is created. The original local implementation is preserved. Additional
verification outcomes are recorded in the receipt; unavailable historical evidence
is not relabeled as a failed strategy or a passing synthetic financial check.

## Lesson

A local passing suite is not shared integration evidence. A historical read-only
check also has a dependency closure that must be authenticated. Separating a fixed
installed checker from raw historical bytes makes that closure explicit without
executing old study code. The public repository can verify engineering mechanics
while correctly reporting that private historical inputs are unavailable.

## Rollback and remaining gaps

Revert the additive current RSI files, new tests and documentation/index changes.
Preserve all historical inputs and demo/failed-test outputs. No store migration,
financial adoption or broker rollback is involved.

Financial adapters, authenticated cross-program evaluation-access history,
broader known-lesson retrieval, withheld process-policy evaluation and independent
financial evidence remain unavailable/unverified. This PR neither changes a
financial incumbent nor demonstrates recursive financial improvement.


## Observed validation

The first full offline check passed 501 tests before the final authority guard was
added. The final focused suite passes 74 tests: all 70 original behaviors plus four
current integration/recovery regressions. The standards reviewer independently
reran the new zero-launch deadline regression. Both review tracks have no remaining
blocking finding; the requirements reviewer requested the enclosing total-demo bound.

The current installed checker verified 296 historical files and recognized the
1,019-session diagnostic transition. The real demo completed once with two synthetic
process launches, zero financial slots, exhausted-budget refusal, verified cache
reuse and explicit synthetic adoption/rollback. Its enclosing 120-second invocation
completed in under one second. All 13 snapshotted local foundation files and 296
checked local historical files remain byte-identical; 405 protected shared-main files
also retain their original bytes in the integration checkout. All 25 demo artifacts
are separately hash verified. The original 449-test receipt is not rewritten.
Final clean-head and hosted CI evidence will be linked in the PR; these counts do
not imply any financial result or native runtime proof.
