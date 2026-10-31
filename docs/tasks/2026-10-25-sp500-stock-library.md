---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Current SPY equity holdings: free historical price acquisition

Work status: acquisition and structural verification complete; financial dataset
qualification remains blocked. User requested downloading “all SPY 500”; interpreted
as the current stock pool, with available 2016–2025 daily history. This expands
the [US-stock library](../data-library.md), not historical strategy research.

## Fixed scope before price acquisition

- Universe: issuer's advertised [SPY daily holdings workbook](https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx),
  linked by its [product page](https://www.ssga.com/us/en/individual/etfs/state-street-spdr-sp-500-etf-trust-spy).
  Local frozen workbook shows 22-Oct-2026: 503 standard equity symbols, plus cash
  and one nonstandard holding retained as exclusions. This is a SPY equity-holdings
  proxy, not a certified S&P historical membership file. No full holdings data is
  redistributed in the public repository.
- Pricing: existing Alpaca Basic credentials, only historical-data HTTPS GET,
  raw SIP/USD daily bars, 2016-01-01 through 2025-12-31. Symbol mapping as-of the
  issuer holdings date. Current membership viewed backward is survivor-selected.
- Bounds: one worker, at most 240 pricing requests including pagination and
  failures, 250 MB response data, 10 MB/response and 15 minutes of acquisition
  time. At least 0.5 seconds between requests. No automatic retries, paid data,
  provider substitution, account/broker calls, orders, strategy runs or imports
  into MLflow performance experiments. Failed requests stop acquisition and leave
  raw responses and a receipt; no run-ID rotation to bypass the bound.
- Batch up to 20 symbols. Preserve source bytes/hashes and exact request windows,
  feed, adjustment, mapping date and pagination identities. Store local source,
  normalized records and a new native catalog separately from prior datasets.

## Acceptance and failure semantics

Validate each symbol independently: source timestamps at New York midnight,
unique chronological dates, finite positive OHLC and envelope, nonnegative volume,
native encoding precision and expected research-calendar sessions. Check missing
sessions between first/last observed bars. Never infer IPO/listing date from the
first observation. Leading/trailing gaps and missing instruments are reported,
not filled or treated as complete ten-year history.

Structurally valid series with no interior gaps may enter an isolated conditional
price catalog after exact native bar/instrument write/read. Invalid or internally
gapped series remain preserved outside that catalog. No data is promoted for
financial comparison: splits/dividends, identity histories, delisting coverage,
full source-use scope and historical membership remain unqualified.

The combined catalog is built in a new staging directory. Publish its dataset
path only after all accepted batches pass native read-back, count/identity checks
and artifact hashing. Tests cover universe parsing/exclusions, missing/invalid data,
pagination failures/limits and incremental native catalog writes. This is a data
acquisition/storage task, not a financial trial or paper-trading operation.

## Evidence

Starting tracked/untracked file hashes preserved under ignored
`.local/sp500-acquisition/before.json`. Frozen issuer file is under
`data/raw/universe/sp500-20261025/holdings.xlsx`. Final counts, local manifest paths,
validation and limitations are recorded below.

- Requested 503 equity symbols; cataloged 500 instruments and **1,212,539 bars**.
  **459** have all 2,514 expected sessions; **41** have partial coverage;
  **FDXF, HONA and VYLR** returned no bars. No invalid/interior-gap series.
  Missing histories were neither filled nor substituted.
- Actual acquisition: **130 requests**, **130,621,651 response bytes**,
  **192.60 seconds**, within every frozen bound.
- Verified all **1,635 artifact hashes** and independently read back every final
  catalog bar, comparing native value/timestamp signatures against normalized
  records in batches. All **1,212,539 bars** matched, across 500 instruments.
- Offline `make check`: exit 0, **272 tests passed**, including five new parser,
  validation, pagination/budget and native catalog tests.
- Local manifest: `data/manifests/spy-equities-2016-2025-v1.json`.
  Catalog: `data/catalog/spy-equities-2016-2025-v1/`.
  Coverage: `data/normalized/spy-equities-2016-2025-v1-coverage.csv`.
- [Redacted evidence receipt](evidence/2026-10-25-sp500-stock-library.json).
  Full issuer holdings and price rows remain ignored local artifacts.

This completes the requested available-price download, not historical-universe
or corporate-action qualification. Financial comparison remains ineligible under
the canonical data contract. No strategies, orders or financial MLflow imports
were executed.
