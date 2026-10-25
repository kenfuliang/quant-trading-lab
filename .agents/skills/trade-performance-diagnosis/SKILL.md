---
name: trade-performance-diagnosis
description: Explain a saved trading strategy's gains, losses or metric differences using account, trade, exposure and regime evidence. Use to diagnose results before proposing strategy changes; it does not start a tuning search.
---

# Trading performance diagnosis

Read [performance diagnosis](../../../docs/research-development.md#performance-diagnosis).
Identify the requested run IDs, immutable manifests, method definitions, ledgers,
benchmark and comparison period. For the current local suite, consult the
[suite protocol](https://github.com/kenfuliang/quant-trading-lab/blob/4586095846c63abf2e0b90dc547654256c3fc45e/research/strategy-suite.md) and the relevant definition
owner; [performance operations](../../../docs/operations/performance.md) locates
saved artifacts. Browser scores are summaries, not substitutes for account paths.

Choose diagnostics that answer the question with available evidence:

- First establish comparability: calendar, initial capital, signal/execution
  timing, dividends, costs, financing and actual exposure. Explain mismatches
  before interpreting a ranking. Compare a common window as a separately labeled
  view, retaining original full-window results.
- Reconcile headline changes to saved account data. Include initial capital in
  peak tracking; distinguish full-path drawdown from calendar-year or stitched
  segment drawdown. Preserve undefined ratios as undefined rather than assigning
  a favorable rank. State Sharpe cadence, annualization and risk-free assumption.
- Decompose what the artifacts support: asset/time contribution, market exposure,
  leverage, timing, turnover, fees, financing, dividend credits and cash drag.
  Distinguish accounting decomposition from causal explanation. Aggregate returns
  alone cannot identify stock-selection skill or factor-adjusted alpha.
- Inspect concentrated profits/losses, recovery duration, holding times and
  regime differences. Fix regime definitions independently of the candidate's
  losses; a regime discovered from those losses is an exploratory hypothesis.
  Show sample counts and overlapping trades rather than implying independence.
- For an apparent improvement, show both benefits and displaced opportunities:
  avoided losses, missed gains and extra trading. Distinguish one favorable
  period or higher risk from persistent incremental information.

Return evidence-linked findings, reproducible calculation definitions, material
limitations, and a short list of testable next hypotheses. Mark unavailable
attribution as unknown and identify the required artifact. If a ledger mismatch
could change the conclusion, report the discrepancy and suspend that conclusion;
unaffected descriptive findings can still be delivered.

Finish when the requested difference is explained to the extent supported, or
the missing evidence is precise. Diagnostics on viewed results remain development
evidence. Proposing a test does not authorize rerunning, editing a strategy,
searching parameters or changing the broker state.
