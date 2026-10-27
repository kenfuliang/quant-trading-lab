---
status: active
updated: 2026-10-27
owner: project-maintainers
---

# Local environment SOP

This file owns setup, routine checks, and handling local project storage. Run
commands from the repository root. Root README owns current capability status.

## Fresh checkout

The project repository is public; local account data and credentials remain ignored:

```sh
git clone https://github.com/kenfuliang/quant-trading-lab.git
cd quant-trading-lab
```

Source code, documentation, tests, original SPY fixtures and audit receipts are
tracked. Generated leverage result directories, MLflow state, local screenshots,
data-provider caches, environments and the upstream checkout stay ignored.
Recreate reports with the [performance SOP](performance.md); Git alone does not
back up local experimental results or operational state.

The installed wheel is enough for normal checks and saved-result simulations.
For source-based capability review, optionally reconstruct the pinned checkout:

```sh
mkdir -p vendor
git clone --branch v1.231.0 --depth 1 https://github.com/nautechsystems/nautilus_trader.git vendor/nautilus_trader
git -C vendor/nautilus_trader rev-parse HEAD
```

Expected reviewed revision: `27a8e54e7ac3c57d6cbf8891f0283dfbaee97317`.
Verify it before treating an upstream checkout as the reviewed source.

## Reconstruct the environment

Use Python 3.12 on the current macOS ARM64 target. Preserve an existing environment
until a replacement passes checks. For a fresh checkout without `.venv/`:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
make check
make doctor
```

Installation needs package-network access. Routine checks use local fixtures only.
The existing environment is verified separately; the reconstruction recipe needs
fresh-environment evidence when dependencies or platform change. Keep direct
dependencies in requirements.txt and update the lock deliberately in an isolated
environment. Consult the pinned upstream version, not examples from a newer release.

## Routine operation

1. Read README capability status and the active task; inspect Git changes.
2. Run `make doctor` for engine/configuration checks. It builds configuration only.
3. Run `make check` for document links, dependency consistency, and offline tests.
4. Record failures and exit results in the task. A passing doctor does not verify
   Gateway, market-data receipt, order execution, or platform modules still planned.
5. For requested broker observation, follow the separate [paper SOP](paper-connection.md).

## Storage and recovery

- Keep credentials outside tracked files; use Gateway for its own credentials.
  `.env*` is ignored, but an ignored file is not a secure backup or sharing mechanism.
- Store private logs under `.local/`. Check redaction before sharing engine output.
- Preserve reports and frozen inputs. Before moving/removing data, identify readers
  and verify a usable copy with matching content hashes.
- Stop active writers before making a file-based recovery copy. Include source
  inputs, reports, project code/configuration and lock files. Store a recovery copy
  outside this checkout; verify hashes and restore it to a separate location.
- Future database backups must use a consistent database export and preserve
  referenced artifacts. Copying a running database directory is not a backup SOP.
  Backend choice and tested restore commands belong to [M3](../roadmap.md); no
  database backup command is implemented today.
- Keep backups private if they contain account information; omit credentials from
  ordinary project archives. Retention and scheduling will be defined with M3.

Stop/restart of a future execution worker must follow reconciliation in the
[incident SOP](incidents.md). Current check commands do not manage external orders.

## Closed research evidence copies

The [evidence recovery SOP](evidence-recovery.md) supplies verified copy/restore
commands for closed manifest-qualified file bundles. One completed and one failed
historical bundle have a scoped same-machine drill. Database, MLflow and native
runtime restore remain unverified; this does not complete M3.
