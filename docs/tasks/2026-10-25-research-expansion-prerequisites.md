---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Expanding research beyond viewed SPY: prerequisites

Reviewed official source documentation on2026-10-25. This is an intake and
feasibility record for the [recursive research program](2026-10-25-recursive-research-program.md),
not a replacement portfolio roadmap or investment recommendation. No market dataset
was obtained, account opened, code installed, strategy run or broker contacted.
[Goals](../goals.md) retains the free/local constraint; [research intake](../research-intake.md)
retains reuse policy. The [current inventory](2026-10-25-recursive-research-inventory.md)
explains the audited SPY inputs and single-instrument ledger we actually have.

**Recommendation: prepare a small multi-ETF data/account contract first.** It is a
shorter extension from current stock-like accounting than options, futures or FX,
while allowing asset selection and portfolio construction. This is an engineering
judgment, not evidence that an ETF strategy will be profitable or reach annual
doubling. No new empirical branch is ready today solely because public documentation
exists. No claim is made that complete free data cannot be found.

```text
New hypothesis / universe
          ↓
Source rights + eligible instrument identities + availability timestamps
          ↓
Frozen coverage + corporate actions + calendars / contract events
          ↓
Multi-instrument accounting and executable cost/margin model
          ↓
Offline fixtures + independent reconciliation
          ↓
Bounded development experiment → separate independent-evidence decision
```

## Branch decisions

| Branch | What free official sources establish | Missing prerequisites | Decision for this project |
| --- | --- | --- | --- |
| Multi-asset ETFs | Alpaca Basic documents US stocks/ETFs, history since2016 and limited live IEX coverage; market-data endpoints need authentication | Verified access and use terms; frozen investable ETF universe/inception history; common timestamp/calendar policy; raw prices versus distributions/splits; single shared cash account and allocation/rebalance rules | **GO for contract/fixture preparation; NO-GO for empirical selection until input/account gates pass** |
| Cross-sectional stocks | SEC exposes public submissions/XBRL APIs without API keys; Alpaca documents stock bars/corporate-action interfaces | Historical eligibility including delistings and identifier changes; point-in-time filings/fundamentals; prices/actions; liquidity/borrow if shorting; ranking labels and shared-account execution | **Blocked for credible full-universe selection; narrow fixed-universe mechanics tests can be labeled exploratory** |
| Options | Alpaca historical data begins February2024; its free indicative feed derives quotes/trades rather than supplying actual OPRA observations; OIC explains exercise/assignment | Complete historical chain membership, underlying synchronization, bid/ask/liquidity, expiry/style/deliverable changes; pricing/Greeks/IV assumptions, dividends, exercise/assignment, leg execution and cash/margin | **NO-GO for executable historical strategy claims; GO for synthetic contract/account tests only** |
| Futures | CME specifies contract expiry/roll and daily settlement/margin; DataMine access involves orders/licenses | Per-contract prices/settlements and reference metadata; licensed complete history; causal roll decisions; multiplier/tick/session; variation margin, collateral/interest, delivery avoidance and liquidation | **NO-GO for empirical futures portfolio; GO for isolated contract/settlement fixtures** |
| FX | ECB publishes reference-rate histories with stated reuse conditions; OANDA documents broker-specific funding mechanics | Executable bid/ask or an explicit non-executable statistical question; pair/base-currency convention, publication timing, currency cash books, conversion, rollover/forward funding and settlement calendars | **GO for reference-rate data-contract study; NO-GO for executable spot/carry returns without funding/quote model** |

GO above means a scoped offline prerequisite task, not a live/paper authorization.
New assets chosen after reading prior results do not become an independent holdout.
ETFs sharing equity exposure may offer less economic diversification than their
symbol count suggests; inspect holdings/risk dependencies before claiming novelty.

## What the sources actually say

### Stocks and ETFs: access is not a point-in-time universe

Alpaca's [subscription documentation](https://docs.alpaca.markets/us/docs/about-market-data-api)
describes free Basic accounts, stocks/ETFs, history since2016, limited live IEX,
recent-history restrictions and API-key authentication. It does not prove this user's
entitlement, successful retrieval, surviving/delisted coverage or dataset suitability.
We did not create an account or request credentials.

The [bar interface](https://docs.alpaca.markets/us/reference/stockbars) and
[corporate-action interface](https://docs.alpaca.markets/us/v1.1/reference/corporateactions-1)
are relevant adapter specifications. A dedicated normalized action receipt should
record action identity, announcement/availability, ex/effective/pay dates, type and
adjustment policy. Using dividend-adjusted prices while also crediting dividends
would double count; applying a future split to historical share counts needs a
consistent price/position policy. These are our required accounting tests, not a
claim that every provider field has been reconciled.

The published [Alpaca terms](https://files.alpaca.markets/disclosures/library/TermsAndConditions.pdf)
restrict ordinary content use to personal/non-commercial purposes and refer to
additional account/third-party agreements. Free API access is not an unrestricted
right to redistribute downloaded prices or feed a public data service. Verify the
applicable current account/feed rights for the exact intended use before acquisition
or publication; keep any subsequently approved raw inputs private by default.

[SEC APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
provide filing histories and extracted XBRL facts, update as filings disseminate and
include data aggregated across submissions. The frames interface uses the latest
filed matching observations. Therefore our stock-selection adapter must retain
accession and availability chronology, distinguish reporting period from knowledge
at the decision, and prevent later amendments/restatements entering earlier signals.
SEC data alone does not provide historical tradable prices or complete market-wide
membership. Its [developer guidance](https://www.sec.gov/about/developer-resources)
requires compliant automated access; no bulk data was fetched in this review.

A fixed handful of today's surviving stocks can test pipeline mechanics. It cannot
support a survivor-free broad stock-selection claim. A stock's currently displayed
ticker is not a durable historical security identifier. For ETFs, include inception,
closures/mergers and selection rules rather than choosing today's winners and
backfilling them before they existed.

### Options: free indicative observations have a narrower claim scope

Alpaca's [historical options specification](https://docs.alpaca.markets/us/docs/historical-option-data)
states history starts February2024 and distinguishes free derived indicative data
from subscribed actual OPRA quotes. Indicative output can test parsing and a declared
statistical proxy; it cannot establish historical executable bid/ask fills. Short
history and unavailable expired-chain coverage remain explicit uncertainties here.

IBKR's [historical limitations](https://www.interactivebrokers.com/docs/tws-api/doc/md/introduction)
exclude expired options, end-of-day options data and delisted securities. Its delayed
watchlist exception is not a promise of a comprehensive free historical chain. Our
paper-access resolution must not be treated as solving those research prerequisites.

[OIC exercise guidance](https://www.optionseducation.org/optionsoverview/exercising-options)
explains American exercise, broker cutoffs and assignment. Our model must encode
style, expiry/settlement, multiplier/deliverable and resulting stock/cash obligations,
including early assignment/dividend cases. A payoff diagram or Black–Scholes mark
is not historical execution evidence; a long premium return is not portfolio-equity
return. Margin and multi-leg partial fills require their own tests.

### Futures: a continuous signal series is not a tradable account

[CME expiry/roll guidance](https://www.cmegroup.com/education/courses/introduction-to-futures/understanding-futures-expiration-contract-roll)
describes moving positions between actual contracts and cash/physical settlement.
Our input needs contract identifiers and a roll rule using information available
then. Preserve separate raw execution prices; adjusted continuous series can inform
features but cannot silently substitute for contractual fills or roll costs.

[CME mark-to-market guidance](https://www.cmegroup.com/education/courses/introduction-to-futures/mark-to-market)
explains exchange settlement, daily P&L cash movements and margin replenishment.
A futures margin deposit is not a purchase price or the whole account denominator.
The existing stock share/debit model does not supply contract variation margin,
expiry/delivery or collateral accounting.

[CME DataMine](https://www.cmegroup.com/datamine.html) and its
[settlement-data FAQ](https://www.cmegroup.com/articles/faqs/access-to-cme-group-settlement-data-faq.html)
describe ordering/licensing/access channels and applicable fees. No complete free
contract history was verified. Public educational tables or sample files do not
establish unrestricted historical-data rights. IBKR additionally excludes expired
futures older than two years; it is not a complete long-history fallback.

### FX: free reference rates are useful, but not executable prices

The [ECB reference-rate page](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html)
provides downloadable time series, euro-base conventions and publication timing,
and discourages transactional use of its informational rates. They can support
reference conversion/statistical research with the correct availability lag; they
do not contain executable spreads or prove fill availability at the quoted value.
[ECB reuse conditions](https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html)
require accurate reproduction/source acknowledgement and disclosure of modifications;
additional conditions apply to sold documents and separately authored publications.

[OANDA's funding explanation](https://www.oanda.com/us-en/trading/financing-fees/)
and [funding FAQ](https://help.oanda.com/us/en/faqs/financing-costs-us.htm) show that
rates differ by side/pair, change over time and incorporate funding/administration,
with currency conversion and multi-day rollover effects. This illustrates the model
requirement, not validation of IBKR's rates or permission to open an OANDA account.
Choose whether the instrument is broker-financed rolling spot, actual currency
cash balances or a forward; those are different economic contracts. Applying the
SPY ledger's constant USD debit rate is not a valid universal carry model.

## Smallest useful next free/local infrastructure packet

Propose one offline **multi-instrument input contract and catalog round-trip proof**,
consistent with the existing [M1 roadmap](../roadmap.md#next-work-packet-m1):

1. Use tiny synthetic two-instrument fixtures—not invented market performance—with
   separate identifiers, inception dates, calendars and availability timestamps.
2. Preserve raw versus normalized identity, source-use/redistribution status and
   action-event versions. Verify duplicates, missing sessions and stale prices fail
   or are explicitly excluded rather than silently forward-filled for fills.
3. Prove native catalog write/read retains identity, timestamps and values; verify
   split/share/cash-dividend accounting and exact common return intervals.
4. Specify one net cash account, per-asset positions, cash reserve, fixed allocation
   and deterministic rebalance ordering. Reconcile it independently before using
   real multi-ETF data. Do not simply average full-capital equity curves and call
   that a financed rebalanced portfolio.
5. Then select a concrete free-source/universe acquisition packet with documented
   rights, actual coverage and frozen selection criteria. If access needs new
   accounts/credentials, record that dependency; do not create them under this task.

Acceptance is trustworthy data/account behavior and named remaining source gaps.
It is not a positive backtest. Keep futures/options/FX as separately blocked branches
with these specific reopening triggers, so the research allocator can move toward
feasible questions instead of repeatedly rediscovering the same missing inputs.
