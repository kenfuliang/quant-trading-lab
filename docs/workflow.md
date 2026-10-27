---
status: active
updated: 2026-10-27
owner: project-maintainers
---

# Development workflow

This document owns how a project change moves from request to evidence.
The operator sets scope and external-action authorization. Codex implements,
verifies, and records evidence within that scope. A document or skill is not
authorization to submit orders or change broker/account settings.

```mermaid
flowchart LR
    A[Select roadmap outcome] --> B[Inspect current state]
    B --> C[Define acceptance and failure cases]
    C --> D[Implement one usable slice]
    D --> E[Verify offline behavior]
    E --> F[Review diff and canonical docs]
    F --> G[Record evidence and handoff]
    E -->|failure| D
```

For investment objectives or strategy selection, read [goals](goals.md).
For external repositories, papers, or reported results, follow
[research intake](research-intake.md) before adopting code or performance claims.

## Start a task

1. Read root README, the relevant roadmap milestone, and module owner document.
2. Inspect Git status and existing implementation. Preserve unrelated files. Until
   the first baseline commit, record file hashes for touched implementation inputs;
   never claim a clean Git revision identifies the code.
3. For a multi-step change, create `docs/tasks/<date>-<topic>.md` from the
   [task template](templates/task.md). Define observable acceptance criteria and
   failure cases before implementation. Small edits may record this in the handoff.
4. Choose the smallest useful slice. Database work includes migration and rollback
   or recovery behavior; event work includes duplicate/restart behavior.

Ready means scope, canonical owner, acceptance criteria, and verification are clear.
Seek missing user input only when it blocks a material decision.

## Implement and verify

For changes involving NautilusTrader or MLflow, first apply the
[dependency boundary decision](architecture.md#configure-extend-upgrade-or-patch).
Record whether the change configures a supported feature, extends a public
interface, upgrades a pinned dependency or requires a separately maintained
upstream patch. Follow that choice's evidence requirements before adoption.

- Test across the module's public interface. Use fixtures and fake adapters for
  broker behavior. Ordinary checks are offline and do not start Gateway.
- Run focused checks while developing, then `make check` before handoff.
- For migrations, verify against a disposable database and exercise recovery with
  representative records. Do not call a migration validated before this exists.
- For data changes, verify duplicates, invalid inputs, timestamps, provenance, and
  immutable source handling. For worker changes, exercise failure and restart.
- Inspect generated UI or reports when changed; include representative visual
  evidence. Label simulated state and unavailable data.
- Preserve raw failure evidence in ignored `.local/`; publish redacted outcomes.

## Finish a task

Done requires acceptance evidence, applicable checks and their results, canonical
documentation updates, and an honest account of remaining limitations. Record
changed paths, commands/results, timestamps, and code/data identity. A passing
offline suite proves only the behavior it exercised.

Update README when capability availability changes and roadmap only when milestone
acceptance is met. Update a decision record when changing an architectural choice.
Task closure does not establish paper or live readiness.

Commits and remote publication follow the requested task scope. Before the first
commit, review ignored paths and staged content for secrets, account identifiers,
and generated bulk data. This SOP does not automatically stage or publish files.

## Working rhythm

- Start each session: identify the current milestone and one concrete outcome.
- End each session: leave the task status, evidence, blocker, and next action.
- After an incident: preserve evidence and address its demonstrated cause before
  expanding operation.
- When capabilities change: review roadmap sequence and affected SOPs. Add a new
  skill only for a repeatable workflow that the existing skills do not cover.

## Continuous integration

`make check` includes `make boundaries-check`, an offline static dependency and
frozen-source gate. The [architecture contract](architecture.md#enforced-python-dependency-boundaries)
owns its scope and exemptions; reverse imports, cycles and modified protected
files fail the PR/push checks.

[GitHub Actions CI](../.github/workflows/ci.yml) runs `make check` for every pull
request and branch/tag push. One Ubuntu 24.04 job uses Python 3.12, installs the
locked binary dependencies plus direct requirements into `.venv`, then checks
documentation, dependency consistency and offline tests. The dependency cache is
keyed by both requirements files; changes on the same event/ref cancel stale runs.
The job has a 15-minute timeout, read-only repository access and no persisted Git
credentials. Actions are pinned to full commit revisions; update pins deliberately.

```text
PR / push → pinned environment → make check → GitHub check result
```

Dependency installation requires package-network access. Tests use saved/synthetic
fixtures and do not start Gateway, submit orders, train models, launch MLflow or
run strategy-suite batches. CI validates the checked-out branch's tests; it does
not reproduce every historical report or establish broker readiness. The same
workflow automatically covers additional tests when research branches include it.

This reuses the pinned actions, explicit permissions and credential-free checkout
practices in [NautilusTrader's test workflow](https://github.com/nautechsystems/nautilus_trader/blob/b23139911fd9fed82aed2811c5a8a373202b9480/.github/workflows/test.yml).
Their Rust builds, self-hosted runners, release jobs and deployment credentials
are outside this project's CI requirements. No CD or branch-protection rule is
configured by this workflow. Requiring a successful check before merging is a
separate repository setting.
