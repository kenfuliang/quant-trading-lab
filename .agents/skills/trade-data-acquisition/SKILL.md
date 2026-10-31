---
name: trade-data-acquisition
description: Perform an explicitly requested bounded historical-data download into immutable local snapshots and a conditional catalog using supported project collectors; preserve provenance, coverage gaps and failures.
---

# Bounded historical data acquisition

Read [current status](../../../README.md) and the
[acquisition procedure](../../../docs/data-library.md#bounded-acquisition-procedure).
For collector changes, first read trade-infra-change from the
[catalog](../../../docs/skills.md); this skill operates existing collectors.
For source discovery without acquisition, use trade-research-intake instead.

Resolve the requested source, universe and membership date, instrument identities,
window/warm-up, fields, feed, adjustment and intended use. Inspect the collector's
current fixed scope and limits; do not assume it accepts arbitrary dates, symbols,
feeds or resume. A mismatch needs a separately scoped implementation or a precise
blocker, not an undocumented flag or silent provider substitution.

Freeze the plan before networking: exact endpoint class, new exclusive dataset ID,
aggregate requests/bytes/time/concurrency, pagination, retry/stop behavior, existing
attempt ledger, source-use evidence and disk capacity. Reuse existing local data
where suitable. Credential presence is not entitlement proof. Never print secrets,
pass them in command arguments or call account/order APIs for historical bars.
Default to the project's free/local constraint; the current-stock collector's
240-request bound is a scoped receipt, not a universal allowance for future work.

Preserve raw bytes before parsing, request/page identities, code/environment hashes,
normalized records and native catalog evidence. Report full/partial/unavailable/
invalid/gapped series separately. Do not infer listing dates or historical index
membership, forward-fill gaps, overwrite a prior snapshot or rotate dataset IDs to
bypass a failed/exhausted plan. On transport/auth/schema/budget failure, preserve
responses, manifest and staging; diagnose before any newly authorized continuation.

Return actual limits consumed, paths/hashes, coverage/exclusions, native write/read
checks and unresolved rights/actions/identity/timing issues. A completed download
is conditional storage, not financial eligibility. For a requested fitness verdict,
read trade-data-audit and hand it the frozen manifest plus named experiment's
requirements. No backtest, MLflow financial import or broker exercise follows
implicitly from acquisition.
