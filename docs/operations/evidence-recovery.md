---
status: active
updated: 2026-10-27
owner: project-maintainers
---

# Closed research file-bundle recovery

This SOP owns copy-only recovery of closed file bundles. [Local operations](local.md)
owns general storage; [incident handling](incidents.md) owns uncertainty;
[roadmap M3](../roadmap.md) retains database/runtime recovery requirements.
[Drill and evidence](../tasks/2026-10-27-evidence-recovery.md) report the tested scope.

```text
Closed original + saved artifact hashes
                  ↓ validate every regular file
Recovery copy outside checkout + pinned inventory SHA-256
                  ↓ restore into nonexistent disposable directory
Restored bytes and original terminal status
                  ↓ verify originals and recovery copy stayed unchanged
Redacted receipt; no financial rerun or resumption
```

## Preconditions

Select a closed bundle with a saved `manifest.json` declaring a supported terminal
status and a complete `artifact_hashes` map for every other file. The
[implementation](../../research/control/evidence_recovery.py) owns the exact supported
status set; unknown/running/pending states fail. This tool does not stop writers
or lock live stores. It is for finalized, stable bundles, not active data or databases.
Before/after hashes detect observed changes; this is not an atomic live snapshot.

Ensure the bundle is appropriate for private storage. No credential collection or
provider download is part of recovery. Archive only the selected existing evidence;
full project/dependency backups need their own scope. Choose a recovery-copy parent
outside the checkout, on appropriate storage, and separate restore parent. Both
parents must exist; each destination must be nonexistent, even if an existing
folder is empty. Preserve prior copies and partial failures; use a new destination.

## Commands

From the intended project checkout, using its pinned Python environment:

```sh
.venv/bin/python scripts/current/evidence_recovery.py backup SOURCE NEW_COPY
.venv/bin/python scripts/current/evidence_recovery.py restore COPY NEW_RESTORE --inventory-sha256 SHA_FROM_BACKUP_RECEIPT
```

`backup` writes only the new copy's `files/` payload and `inventory.json`; record
its printed inventory SHA separately. The inventory covers every original file,
including the saved manifest. `restore` requires that pinned SHA, validates the
copy and original artifact hashes, then copies into a new destination. Its result
preserves the original status; restoring a failed run does not repair it, renew its
budget or resume workers. No original manifest is rewritten.

Each operation rejects symlinks, special files, unsafe inventory paths, hash/coverage
mismatches and overlapping roots. Copying uses exclusive file creation; interruption
leaves partial output in place and the next call refuses that destination. Preserve
all errors, copies and partial output. There is no automatic retry, cleanup, order
submission or process resumption. Do not mistake retained partial output for a
verified successful recovery.

## Verification and limits

Record source identity, original status, saved manifest SHA, pinned recovery
inventory SHA, file counts, command/exit, source before/after hashes, restored
hashes, storage location and UTC time. Verify the original and recovery copy remain
unchanged; failed records and their statuses must remain byte-identical. Keep raw
private paths/content local and publish only a redacted receipt.

The scoped drill restored one completed and one failed historical bundle from
copies outside the checkout, totaling 38 files. CI tests the mechanics with synthetic
success/failure fixtures, corrupt files, wrong inventory SHA, incomplete coverage,
symlinks, overlap, interrupted backup/restore and no-overwrite behavior. CI does not
access private real bundles or claim to repeat that historical restore drill.

This is same-machine file-bundle recovery proof. It does not establish offsite or
different-disk survivability, encryption/access-control policy, scheduled retention,
MLflow/SQLite consistency, broker/native runtime recovery, complete external
input/code dependency closure or financial reproducibility. File permissions,
ownership and timestamps are not promised; verification concerns bytes and saved
status. A recovery inventory hash is not a signature or authentication of scientific
claims. M3 remains incomplete.
