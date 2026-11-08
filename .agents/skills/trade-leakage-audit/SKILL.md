---
name: trade-leakage-audit
description: Audit strategy, feature and evaluation code for lookahead, selection and trial-count leakage before a result is trusted; produce a findings receipt without changing the candidate or rerunning financial trials.
---

# Audit research code for leakage

Read the [data-audit](../../../docs/research-development.md#data-audit) and
[robust-evaluation](../../../docs/research-development.md#robust-evaluation)
procedures, the [feature contract](../../../docs/feature-engineering.md#evaluation-contract)
and the experiment's frozen specification. This reviews code and recorded
evidence. It complements `trade-data-audit` (input bytes and timestamps) and
`trade-robust-evaluation` (statistical verdict); it does not replace either.
No automated lint is installed here, so every finding is a manual reading of
named code lines or a check actually run, never a clean bill from a tool.

Name the code revision, the decision and fill times the study claims, and the
splits and trial budget it froze. If they are missing, report that and stop at
an inventory instead of inferring them.

## Check

- **Timing:** for each signal, trace the latest input bar and the bar the order
  fills on. Flag same-bar close signals filled at that close, centered or
  forward-looking windows, `shift` direction errors, labels joined without a
  purge, and fields knowable only after the decision (adjusted prices,
  restated or dividend data, index membership).
- **Fit leakage:** flag scalers, thresholds, rankings or universes fitted on
  data that includes the evaluation window. Check warm-up does not reach into it.
- **Selection leakage:** trace which results chose the parameters, window or
  universe, and whether any evaluation sample was viewed before the freeze.
  Compare the number of variants actually attempted against the disclosed trial
  count; an undisclosed sweep invalidates any deflated or corrected statistic.
- **Survivorship and universe:** check that membership and delisting are
  point-in-time for new universes; the saved SPY fixture does not test this.
- **Cost realism:** confirm costs and financing apply on the executed bars.

## Return

Give a receipt: code revision and hashes, each check as `passed`, `finding`
(file:line and why) or `not assessed`, the trial count disclosed versus
observed, and an overall **no findings in scope**, **findings**, or
**inconclusive**. A finding is not permission to patch the candidate and reuse
the same evaluation sample; report it and route the correction through
`trade-stage-development` as a new, separately scoped change. Do not launch
runs, refresh data or contact a broker.
