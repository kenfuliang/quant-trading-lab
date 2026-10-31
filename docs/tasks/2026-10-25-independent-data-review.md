---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Independent data providers and collectors: screening

**Outcome: screening completed; acquisition and runtime integration unverified.**
Reviewed public primary documentation and six pinned collector repositories on
2026-10-25, America/Los_Angeles. This task researches and plans a local library;
it does not resume the blocked financial experiment or reset its quotas/deadline.
The [library plan](../data-library.md) owns the proposed data contracts and phases;
[research intake](../research-intake.md) owns source-adoption procedure.

Acceptance for this screening: compare recurring free coverage across US stocks,
ETFs, exchange futures and spot forex; separate trials/proxies from equivalent
instruments; identify reusable collectors with revision/license evidence; propose
an offline-first library and a bounded qualification pilot. No market-data API
requests, package installation, accounts, credentials, simulations or broker
operations are part of this task. Public documentation and repository source
files were read; no downloaded code was executed.

## Provider comparison

“Candidate” means documented access worth qualifying, not approved data. Rates,
entitlements and terms can change. Unknown coverage is not a promise of coverage;
free access is separate from local retention, non-display use and redistribution.
No provider below was tested with an authenticated account in this review.

| Provider | US stocks / ETFs: recurring free offer | Spot forex | Exchange futures | Access, history and selection decision |
| --- | --- | --- | --- | --- |
| **Alpaca Basic** | Stocks and ETFs; documented history since 2016; 200 historical requests/minute | Not established by the reviewed offer | Not established by the reviewed offer | Account/API keys required. FAQ allows historical SIP when `end` is at least 15 minutes old; free live feed is IEX. **First equity candidate**, subject to actual entitlement, storage/use terms, actions and delisting audit. Cannot supply 2004–2015 for our existing experiment. [Plans](https://docs.alpaca.markets/us/docs/about-market-data-api), [FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) |
| **Twelve Data Basic** | Advertises US equities and ETFs | Advertises forex | No complete expired-contract archive established | Free Basic: 8 API credits/minute, 800/day; internal non-display usage. Time-series requests have a 5,000-point maximum. Earliest history and action entitlements vary and remain untested. **Second candidate**, especially for a longer-history eligibility probe; no assumption that Basic covers our required dates. [Pricing](https://twelvedata.com/pricing), [historical requests](https://support.twelvedata.com/en/articles/5214728-getting-historical-data) |
| **Alpha Vantage** | Raw daily compact returns latest 100 points; full daily history and daily adjusted endpoint are premium | Documents daily OHLC with compact/full parameters; actual free-key history untested | Commodity/economic series do not establish a contract archive | Standard free limit 25 requests/day. Verified open-source/educational exceptions require provider verification; our public GitHub repo does not automatically qualify. **Small FX/reference candidate; reject as the default long equity backfill.** [Limits](https://www.alphavantage.co/support/), [endpoint rules](https://www.alphavantage.co/documentation/) |
| **Massive Stocks Basic** | Free stock/ETF bars have a rolling two-year window; REST only, no Basic flat files | Separate product; free entitlement not established here | Separate product; free entitlement not established here | **Recent independent cross-check candidate**, not a long-history replacement. Paid archive depth must not be attributed to Basic. [Coverage by plan](https://massive.com/knowledge-base/article/how-much-historical-stock-data-does-massive-have) |
| **Dukascopy** | Selected instruments advertised; stock/ETF/CFD identity must be checked individually | Official export advertises free CSV, tick through monthly, with instrument-specific history | CFD/index series do not establish exchange contracts | **FX export candidate.** Official bulk-export wiki describes AWS Requester Pays: exclude that route under the zero-cost constraint. Automated collector route/permission and sustainable free bulk access remain unverified. [Official export](https://www.dukascopy.com/swiss/english/marketwatch/historical/), [bulk route](https://www.dukascopy.com/wiki/en/development/data-export/) |
| **HistData** | No US cash-equity archive established | Free tick and M1 ZIP/CSV downloads for listed pairs; dates vary per pair | Advertises other feeds, but these do not establish individual expired contracts | **FX file-import candidate.** Fixed EST, no DST; bars are bid prices; Generic ASCII tick format includes ask. Volume removed. Preserve per-file gap reports; financing still absent. Faster FTP/SFTP is not assumed free. [FAQ](https://www.histdata.com/f-a-q/) |
| **Stooq** | Historical-download lead; complete scope and adjustment semantics unverified | Possible lead, not qualified | Possible series lead, not a qualified contract archive | **Hold.** Download page returned browser-verification content, not coverage evidence. Do not bypass the challenge or treat a working third-party reader as permission. [Observed page](https://stooq.com/db/h/) |
| **Yahoo Finance** | Existing local fixtures remain historical evidence; new bulk collection not qualified | Indicative symbols would need source/instrument review | Front-month symbols do not establish roll/expiry accounting | **Hold for permission.** yfinance itself directs users to Yahoo terms. Current terms page fetch returned HTTP 999 in this review; prior saved restriction evidence remains preserved in the [qualification checkpoint](2026-10-25-multi-asset-qualification-v2-checkpoint.md). No new automated price collection. [Collector disclosure](https://github.com/ranaroussi/yfinance) |
| **Databento** | Usage-priced history | Not established for spot FX by reviewed pricing | Exchange futures available through paid datasets | $125 introductory historical credits are **finite trial credit, not a recurring free tier**. No credit activation or billing-enabled job recommended for the present library. [Pricing](https://databento.com/pricing) |
| **CME DataMine** | Outside this equity search | FX futures are different from spot FX | Official futures/options history, with purchased-data API and retrieval fees | **Not a confirmed recurring-free archive.** Recent public settlement displays are not a full contract history. Legacy free FTP advice is stale: CME documents the migration and fees. [Settlement FAQ](https://www.cmegroup.com/articles/faqs/access-to-cme-group-settlement-data-faq.html), [DataMine API](https://www.cmegroup.com/datamine/datamine-api.html) |
| **ECB reference rates** | Not applicable | Public reference-rate downloads | Not applicable | **Supplementary validation/context only.** ECB discourages transaction use; these are not bid/ask execution data or a substitute for a tradable FX feed. [ECB](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html) |

The Alpaca historical/live distinction corrects the earlier shorthand that the
free offer was universally IEX-only. Its historical SIP eligibility is documented,
not yet account-tested. Where an overview and specific FAQ differ, preserve both
and verify the chosen feed explicitly rather than silently falling back to IEX.

**Conclusion:** a recurring-free US daily-equity library beginning in 2016 and
an independent FX library are plausible. No complete, permission-qualified free
all-US-equity history including delistings, or full exchange-futures archive, was
established. This is the result of this screening, not proof no such source exists.

## Collectors and reuse decisions

GitHub default-branch revisions resolved through the public API; README/license
bytes saved and SHA-256 recorded in the [screening receipt](evidence/2026-10-25-independent-data-review.json).
These are source pins for screening, not installed dependency versions. No
transitive-license, dependency-compatibility or security audit is claimed.

| Collector | Pinned revision | Code license inspected | Reuse decision |
| --- | --- | --- | --- |
| [alpaca-py](https://github.com/alpacahq/alpaca-py/tree/66f2ffd797d3cb0e5202daf36d178b67aff89915) | `66f2ffd797d3cb0e5202daf36d178b67aff89915` | Apache-2.0 | Preferred equity SDK candidate. Inspected `StockHistoricalDataClient.get_stock_bars`, batch symbols and pagination delegation. Raw HTTP-response preservation still needs a wrapper/public transport review; the inspected `raw_data` docstring says not implemented, so do not assume it supplies original bytes. Only data-client interfaces belong in ingestion. |
| [twelvedata-python](https://github.com/twelvedata/twelvedata-python/tree/3d53d271a450c50b2199722b5d2db7b92e213d3b) | `3d53d271a450c50b2199722b5d2db7b92e213d3b` | MIT | Official client candidate for equity/FX endpoint probes. We still own date-window checks, pagination, raw responses and credit budgeting. |
| [dukascopy-node](https://github.com/Leo4815162342/dukascopy-node/tree/33a6c6e3de97fab9904afc80a3a2fac8b46d8bfb) | `33a6c6e3de97fab9904afc80a3a2fac8b46d8bfb` | MIT | FX collector candidate only. README requires Node 20+ and says downloads may need Chrome/Chromium. Inspect browser/auth behavior and authorized route before execution; do not launch background browser automation or install Chromium during intake. |
| [pandas-datareader](https://github.com/pydata/pandas-datareader/tree/9a3e2fe8c4e202bf9be6b4543fd1a06c3cdce7de) | `9a3e2fe8c4e202bf9be6b4543fd1a06c3cdce7de` | BSD-3-Clause main terms; bundled notices require review before adoption | Useful reader reference, including [Stooq reader documentation](https://pydata.github.io/pandas-datareader/devel/readers/stooq.html). Main license inspected manually because GitHub SPDX metadata returned `NOASSERTION`. Does not remove Stooq access/rights uncertainty. |
| [Qlib collectors](https://github.com/microsoft/qlib/tree/54355232463878d2eebb91fe0ee5fa7fa1f5976c/scripts/data_collector) | `54355232463878d2eebb91fe0ee5fa7fa1f5976c` | MIT | Reuse collector/normalizer separation and feature/calendar/instrument concepts. Reviewed README lists US/CN Yahoo and index collectors; not an independent licensed US price archive. No need to install Qlib to adopt that design. |
| [yfinance](https://github.com/ranaroussi/yfinance/tree/2081dca0b224512ff768f9c5e6bd9c658a3b8339) | `2081dca0b224512ff768f9c5e6bd9c658a3b8339` | Apache-2.0 | Familiar convenience wrapper; **hold for new collection**. Its code license does not grant Yahoo data rights or complete delisted/contract histories. |

HistData's ZIP/CSV format can use a small local importer rather than another
framework. Collector code licenses never transfer provider data rights. A
non-archived repository is not proof that a particular endpoint works today.

## Why this does not unblock the existing experiment

The fixed SPY/IEF/GLD experiment requires 2004 warmup and 2006–2025 evaluation.
Alpaca's 2016 floor and Massive Basic's rolling two years cannot fill that scope.
Twelve Data's older dates/Basic entitlements are unresolved. Do not splice sources
or shorten the evaluation and call it the same experiment. A newer common-period
comparison would need a separate frozen protocol and all controls recomputed.
No historical financial attempts were made here. The previous blocked goal and
all negative evidence remain unchanged.

## Validation and next action

Source findings are documentation claims. Repo revisions and selected file hashes
were actually retrieved; none of the SDKs was installed or run. Website failures
were retained as unknown/hold outcomes. `make check` passed: documentation and
dependency checks plus 248 offline tests. `git diff --check` passed. The linked
receipt records local checks; no hosted CI was run for these uncommitted changes.

Next implementation: the [library plan's bounded pilot](../data-library.md#first-bounded-qualification-pilot).
Begin with source-use evidence and local/native catalog behavior, then test a
small authorized data request when access is available. This task ends at a
reviewable plan; it does not begin that acquisition pilot.
