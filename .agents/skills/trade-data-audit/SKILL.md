---
name: trade-data-audit
description: Audit frozen local trading inputs for provenance, timestamp integrity, coverage and fitness for a specified experiment; produce an evidence receipt without refreshing the data.
---

# Audit saved research inputs

Read [data-audit policy](../../../docs/research-development.md#data-audit),
[current capabilities](../../../README.md) and the experiment's methodology.
This audits saved inputs now; it does not establish native Nautilus catalog
validation, exchange certification or permission to redistribute provider data.

Identify the actual input path, intended instruments, evaluation/warm-up dates,
decision/execution timing and expected fields from the requested experiment.
If those are missing, inventory the snapshot and report the fitness questions
that remain unresolved instead of inventing a provider contract.

Use filesystem reads, SHA-256 and existing Python loaders. For the saved SPY Yahoo
snapshot, `research.spy_backtest.load_data(Path(...))` is an offline parser that
returns frame, dividends and metadata; inspect its present checks before relying
on them. It rejects splits rather than handling them. It does not prove complete
exchange-calendar coverage, point-in-time availability or data-use rights.

- Hash original bytes before transformations; compare with the exact referencing
  manifest. Preserve originals and identify any normalized output separately.
- Check observed coverage, ordering/duplicates, missing/nonfinite fields, price
  consistency, event joins, adjustment semantics and warm-up against the experiment.
  Distinguish a tested check from one merely available in a loader.
- Check timezone, session mapping and when each field became knowable against
  signal and fill times. Daily OHLC cannot establish intraday event ordering or
  executable quotes. For new universes, identify delisting and survivorship gaps.
- Record source/version, transformations, rights evidence and unresolved questions.
  Free access and a matching checksum do not establish a license or data accuracy.

Return a receipt with input paths/hashes, observed rows/dates/events, checks
performed and results, method/code identity, rights status, limitations and
`eligible`, `conditional` or `blocked` **for the named experiment**. An unknown
material adjustment, timestamp convention or required input blocks eligibility;
an audit can still finish with a useful blocked result. Do not silently repair,
download, refresh or replace inputs. Link failures and proposed corrections;
create a new snapshot/receipt if a separately scoped correction is implemented.
