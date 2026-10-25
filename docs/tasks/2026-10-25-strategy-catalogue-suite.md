---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Parallel strategy catalogue and research suite

- Work status: complete for the supported-data batch; all-100 objective remains partial (78 entries unsupported).
- User scope: explicitly requested parallel completion of the 100-name catalogue. Three parallel lanes own catalogue/provenance, daily signal implementations, and browser/MLflow reporting; coordinator owns execution/audit/protocol/integration.
- Canonical owners: [suite protocol](../../research/strategy-suite.md), [performance SOP](../operations/performance.md), [research intake](../research-intake.md).
- Acceptance for this executable batch: 100 unique candidate definitions and explicit prerequisites, 22 causal daily-SPY adaptations, four nominal leverage targets/caps each, independent ledger audits, annual/full-period return/drawdown/Calmar/Sharpe, separate browser/MLflow, no invented performance for unsupported entries.
- Failure cases: source hashes, duplicate dates, missing/unsupported rules, future-data isolation, warm-up, incomplete-worker retention, cache mismatch, repeat import, undefined scores and visible blockers.
- Starting Git revision: a5a73ec9a6fd65395d40fdace7994172d1dc42f8 on main, clean before this task. No broker scope, new data purchases or external publication authorized by this research request.
- Validation: `make check` passed 64 tests plus dependency and doc checks. All 88 financial cases independently reconciled (464904 session ledgers, 246485 fills, maximum difference 1.10e-8 USD). Independent Decimal recalculation checked 1936 annual/full-period score rows and all rank/tie/N/A outcomes. [Evidence receipt](evidence/2026-10-25-strategy-catalogue-suite.json).
- Run identity: 97fc0717512bee9e83b35b7f477ae8218927d587bed17e4377bdcf2853bfca47. Earlier 15- and 21-rule screens remain separate immutable evidence. The final 22-rule batch uses separate MLflow experiment5; original experiments1/2 remain intact. Current readiness review is separate from each immutable trial catalogue snapshot.
- Browser: observed 100 catalogue entries, 22 simulated adaptations and 88 cases; verified year2008, 1x exposure and Sharpe controls, execution/cap disclosures, CSV/provenance and MLflow link. Screenshot: `.local/screenshots/strategy-suite.png`.
- Scope limits:78 entries need other data/instruments. ID19 now uses an audited close-to-open schedule; actual closing-auction fills remain unverified. No claim that free sources cannot exist. Free data source/coverage checks recorded in research intake; no subscriptions/accounts purchased or configured. Results remain in-sample exploratory, with local adaptations explicitly distinguished from published full strategies.
- Canonical impact: suite/daily/allocation/model/overnight method owners added; README, docs map, mandate data budget, performance SOP, architecture and research intake updated. Infrastructure roadmap milestone readiness unchanged.
- Next action: validate and freeze a free multi-asset/input dataset for the next supported families. No paper/live promotion or automatic publication.
