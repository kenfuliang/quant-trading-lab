---
status: active
updated: 2026-10-28
owner: research-maintainers
---

# Published leaderboard provenance snapshot

This is a **supporting aggregate provenance snapshot**, not a second leaderboard.
The [canonical leaderboard](../leaderboard.md) owns the single table. The
[machine snapshot](evidence/2026-10-28-leaderboard-source-catalog.json) records all43
entry identities, original displayed values and source-file hashes. The original
later-study reports, raw checks and financial summaries remain in the local research
history and are not imported by this PR. A hash identifies bytes; it does not make
unpublished evidence available or prove its truth. Values here are transcription
of saved development summaries, not newly reproduced or independently audited results.
No market data, dense NAV, credentials or third-party strategy source is published.

## Context A

2020–2025; USD10,000 whole shares; native IB fees +25bp slippage; staged MOO,90% nominal targets;6% debit ACT/360, no credit interest. Monthly selection versus entry-only SPY; realized exposure and universe differ. Latest completed selection study replaces the earlier coverage-limited comparison for this view.



Stock momentum has the highest displayed Calmar in this cohort, but its longest underwater stretch exceeds SPY. Fixed selected universes and viewed history limit generalization. Annual and temporal detail: [selection browser](http://127.0.0.1:8765/selection-completion-v1/index.html).

## Context A2

Same2020–2025 fixture as A, but50bp slippage and one additional observed-session decision delay. These rows form their own paired stress context.



Stock momentum crosses30% drawdown under this stress. The stress was selected after observing its earlier result; this is disclosed development evidence.

## Context B

2020–2025; USD10,000; native IB margin/default fees +25bp slippage;90% base target; staged MOO;6% debit ACT/360; no credit interest. Embedded leveraged/inverse/volatility ETFs mean nominal allocation does not describe underlying economic leverage.



Gated T11 improves displayed Calmar and drawdown depth, but reduces CAGR and extends underwater time. None meets the approximate30% drawdown reference. All three finish below a prior peak. [Annual and temporal browser](http://127.0.0.1:8765/qc504-t11-gate-v1/index.html).

## Context C

2020–2025; USD10,000;25bp slippage, native IB fees,90% base target, staged MOO and6% debit financing. Historical classification gaps were grouped as unknown. These results are historical diagnostics; the repaired sector-only comparison is D.



Do not treat the21.07% sector-only CAGR as the repaired sector strategy. D changes the classification treatment and adds a target-matched control. [Monthly selections, contribution and annual browser](http://127.0.0.1:8765/stock-risk-v1/index.html).

## Context D

2020–2025; USD10,000;25bp slippage, native IB fees, staged MOO,90% base allocation and6% debit ACT/360. No market gate. Historical sector mappings are repaired under the study’s availability contract. Target-matched control matches intended allocation, not exact realized exposure.



Sector cap improves Calmar by0.0643 against its matched control, while trailing the original momentum policy in growth and Calmar. This is a scoped tradeoff, not universal dominance. [Annual/contribution browser](http://127.0.0.1:8765/sector-matched-v1/index.html).

## Context E

2017-01-03–2025-12-31; USD300,000; USD1/order +5bp slippage;98% gross targets; no financing/interest model. Matched repaired buying-power setting2; observed closing cash remains positive and gross below99%.



Sector momentum has a much shorter worst underwater run than SPY, but lower CAGR and more total underwater closes. The gate leads Calmar with lower growth and a longer worst underwater episode. [Annual browser](http://127.0.0.1:8765/sector-momentum-v1/index.html).

## Context F1

2016–2025; USD300,000; fixed29-stock legacy pool, minute execution, unchanged source sizing and6% debit ACT/360. Native bid/ask fills remain; this is not frictionless.



`on`/`off` means1% per-stock stop enabled/disabled; `s` is the matching SPY hold. Every CAPM variant loses to its matched SPY on CAGR, Calmar, drawdown and longest underwater period. Retain as negative baselines. [All90 annual rows and contrasts](http://127.0.0.1:8765/capm-ablation-v1/index.html).

## Context F2

2016–2025; USD300,000; fixed29-stock legacy pool, minute execution, unchanged source sizing and6% debit ACT/360. No added slippage.



`on`/`off` means1% per-stock stop enabled/disabled; `s` is the matching SPY hold. Every CAPM variant loses to its matched SPY on CAGR, Calmar, drawdown and longest underwater period. Retain as negative baselines. [All90 annual rows and contrasts](http://127.0.0.1:8765/capm-ablation-v1/index.html).

## Context F3

2016–2025; USD300,000; fixed29-stock legacy pool, minute execution, unchanged source sizing and6% debit ACT/360. 25bp added slippage is a stress assumption, not measured execution.



`on`/`off` means1% per-stock stop enabled/disabled; `s` is the matching SPY hold. Every CAPM variant loses to its matched SPY on CAGR, Calmar, drawdown and longest underwater period. Retain as negative baselines. [All90 annual rows and contrasts](http://127.0.0.1:8765/capm-ablation-v1/index.html).

## Context G

2016–2025; USD300,000; 98% targets, native IB commissions +5bp slippage;6% debit ACT/360 and3% short borrow ACT/365; no credit interest. This minute-execution cohort is separate from CAPM and pairs, even where dates match.



Improvement screen failed versus SPY. Beating an intraday-long losing control did not establish a useful portfolio. [Annual and temporal browser](http://127.0.0.1:8765/dual-thrust-spy-v1/index.html).

## Context H

2016–2025; USD300,000; native IB commissions +5bp/fill,6% debit ACT/360 and3% short borrow ACT/365. RAW execution,250 strictly-prior-session fitting,9:32 next-session execution. The fixed surviving pair is selected ex post.



Pairs improvement screen failed. The high-growth pair-hold control has65.70% drawdown and hindsight selection; it is not a discovered robust strategy. [Result/annual and temporal browser](http://127.0.0.1:8765/stock-pairs-spy-v1/index.html).

## Unranked and historical records

G-Score was closed after a failed fundamentals/input-semantics probe, with zero
qualified financial results. The three W1 prototypes passed synthetic engineering
checks only and remain unwired. Their saved lessons are captured in the machine
snapshot, with hashes of their original reports/receipts. No financial metric is
invented for these outcomes. Earlier selection and rejected-order sleeve studies
are historical/superseded contexts; retained links and hashes identify originals.

The local SPY/leverage/strategy suite already represented in this repository keeps
its original published methodology. Later unpublished financial-study metadata is
only a provenance pointer in this snapshot. New studies must add their own adequate
source/receipt evidence; this publication does not waive those closure requirements.
