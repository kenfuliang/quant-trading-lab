---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Alpaca Basic US-stock data pilot

Work status: complete for the bounded structural price-data pilot; financial-use
qualification remains blocked. Implements the bounded D1 price-data slice of the
[library plan](../data-library.md), alongside the native catalog portion of
[M1](../roadmap.md). [Architecture](../architecture.md) owns dependency boundaries.

## Frozen acquisition scope

- User authorized an Alpaca Basic pilot, validation and local catalog storage.
  Basic subscription was observed in the authenticated UI. The user generated
  paper keys and saved them locally; values/account identifiers stay outside Git.
- Symbols: AAPL, JPM, MSFT and SPY benchmark. Selected survivors are engineering
  fixtures, not a historical stock-selection universe.
- Windows: 2016-01-01 through 2016-01-31, and 2025-12-01 through 2025-12-31.
- Only `GET https://data.alpaca.markets/v2/stocks/bars`; SIP, raw, USD, 1Day,
  ascending order, symbol identity as-of 2025-12-31. Request every pagination token;
  no fallback to IEX, another source, another frequency or paid data.
- At most 20 HTTP attempts, 100 MB overall, 10 MB/response and ten minutes from
  acquisition start; one worker, no retries. Abort on authentication, entitlement,
  quota, transport, pagination, size or validation failure; retain evidence.
- No account/trading endpoint, balance query, orders, engine simulations, strategy
  performance calculation, paid subscription or dependency upgrade.

## Acceptance and limits

Preserve raw response bytes and hashes before parsing. Verify exact expected
calendar sessions per symbol, UTC midnight-New-York daily labels, finite prices,
OHLC envelopes, nonnegative volume, duplicates and native precision. Reject
incomplete data without filling. Retain raw source timestamps; catalog daily OHLC
becomes available at the following New York midnight, not at source start time.
Source publication/revision timing and regular-hours-only semantics are unverified.

Use the installed `ParquetDataCatalog`. Write to a new staging directory, compare
all bar values/timestamps and serialized instrument metadata, then rename to the
dataset catalog. Duplicate identical import must be read-only; a different input
must not modify the existing catalog. Prove a separate-directory restore using
synthetic data. These exercise storage, not native trade/execution accounting.

`ALPACADATA` is a research namespace. Instrument price increments encode observed
precision, not certified exchange trading rules. Successful storage qualifies
only a structurally audited price sample: corporate actions, issuer reconciliation,
historical universe, actual publication times and broader source-use/redistribution
qualification remain absent. It is not eligible for financial strategy comparison.

## Implementation and evidence

[Pilot module](../../research/alpaca_pilot.py) uses a small fixed-route stdlib
transport to preserve raw bytes; the [screened SDK](2026-10-25-independent-data-review.md)
did not promise original wire bytes. It configures supported native interfaces,
does not patch installed dependencies, and isolates provider data under ignored
`data/`. [Offline tests](../../tests/test_alpaca_pilot.py) cover corrupt/missing
data, credential redaction, quota/pagination/HTTP failure, redirect refusal,
native round-trip, duplicate preservation and synthetic restore.

## Observed result

- Dataset ID: `alpaca-us-stock-pilot-v1`. Two authenticated HTTP requests, both
  successful; 18,384 response bytes, about 1.69 seconds acquisition time. No SDK
  installed, subscription changed, broker call or order made.
- 164 bars: 41 per instrument, 19 January 2016 sessions and 22 December 2025
  sessions each. Exact expected coverage, source label/price/volume/duplicate
  checks passed. The ten-year gap is intentional, not a continuous history.
- Native catalog at `data/catalog/alpaca-us-stock-pilot-v1/` contains all four
  research instruments and 164 bars. Every bar value/timestamp and serialized
  instrument matched after write/read; repeat import was read-only. Original
  response, normalized and catalog file hashes were verified independently.
- Four synthetic bars separately proved duplicate import and copy/restore.
  Changed-input rejection left existing catalog file hashes unchanged in tests.
- Independent saved-Yahoo SPY overlap: 41 days × four OHLC fields. Two opens
  (2016-01-25 and 2016-01-29) differ by approximately one cent; binary floating
  source representation makes the absolute deltas slightly greater than $0.01.
  The provider-price disagreement's cause is unverified. Both values remain
  preserved; no averaging, rewriting or provider-equivalence claim.
- Local receipts: `data/manifests/alpaca-us-stock-pilot-v1.json` and
  `data/quality/alpaca-us-stock-pilot-v1.json`; synthetic proof under
  `.local/alpaca-pilot/synthetic/native-storage-v1/`. These files remain ignored.
  The [redacted evidence](evidence/2026-10-25-alpaca-us-stock-pilot.json) records
  file identities and validation outcomes without prices, keys or account IDs.

## Remaining work

Validation: `make check` passed all 257 offline tests (nine new pilot tests),
documentation and dependency checks. `git diff --check` passed. Credentials and
catalog data are Git-ignored; publishable files were checked for the actual local
credential values without printing them. Unrelated prior file hashes were preserved.

This completes acquisition/structural catalog storage requested for this small
pilot. Next, qualify corporate actions and source-use scope, inspect the two
cross-provider opens, then define a bounded continuous-history acquisition.
Neither this dataset nor the earlier blocked multi-asset experiment is eligible
for a financial comparison from this result. No hosted CI, crash recovery,
exchange-certified calendar, unbiased universe or broker parity is claimed.
