---
status: active
updated: 2026-10-28
owner: research-intake
---

# Market-condition components: bounded QuantConnect review

**Completed research-only screening of four representative ideas.** No financial runs, dataset downloads, package installation, source export or broker operations. This is not verification of all market-condition entries. The [existing622-record mapping](../../research/catalogs/qc-stage-fit-v1/mapping.csv) and original catalog remain unchanged. [Intake](../research-intake.md) owns rights and [GRS](../research-standard.md) owns adoption; this receipt does not add a mandatory pipeline stage.

```mermaid
flowchart LR
  D[Qualified past-only market proxy inputs] --> C[Optional context: state + confidence + freshness]
  C -. advisory context .-> P[Unchanged position proposal]
  P --> R[Mandatory portfolio risk and sizing]
  R --> E[Execution and evidence]
```

| Idea / exact inventory ID | Actual component fit | Disposition and useful control |
| --- | --- | --- |
| Momentum and State of Market Filters, QC-T-15357 | Broad-index trailing252-session return is genuine optional context; stock ranking and allocation are separate parts. | Best simple contract candidate; compare unchanged policy with/without filter and existing EMA gate. Exact original input blocked. |
| HMM Intraday Regime Detection, QC-C-86 | Inventory title only. Separate official HMM documentation supports a variance-regime hypothesis, not identity of86. | Causal research candidate; compare with fixed realized-volatility threshold. Intraday implementation unverified. |
| Sentiment and Style Rotation, QC-T-15310 | Equity-option sentiment informs conditional style positioning; not a universal risk score. | Hold for series identity/availability; static style, VIX-only and fixed-exposure controls. |
| Gradient Boosting Model, QC-T-15270 | SPY10-minute return prediction belongs to position proposal, not market-context classification. | Route out of current daily-context lane; compare mean/zero predictor and simple indicator under identical costs. |

## Sources, contracts and blockers

**Broad-market momentum.** The [current official method](https://www.quantconnect.com/research/15357/momentum-and-state-of-market-filters/) names discontinued Wilshire/FRED input. Its pinned licensed predecessor instead imports a Yahoo-origin Dropbox CSV. These are different source revisions. A substitute SPY study represents a large-cap proxy adaptation, not exact whole-market reproduction. Context output should carry proxy identity, prior return, eligibility, information time and missing/stale status. Existing trend gating is economic overlap; code duplication remains unverified.

**Volatility/HMM.** The [official documentation](https://www.quantconnect.com/docs/v2/research-environment/applying-research/hidden-markov-models) uses a two-variance return model and historical smoothed state probabilities. Inference: those historical chart labels can use later observations inside the fit window; they cannot serve as past tradable labels. A trailing endpoint estimate is not automatically future-leaking, but requires fit-cutoff audit, convergence checks and variance-ordered states rather than assuming state0 always means low risk. Output should be `p_high_variance`, fit/model identity and freshness—not predicted crash probability. A one-index model measures a market proxy, not breadth across the whole market. Daily SPY adaptation may be feasible after qualification; original intraday identity remains unknown. Community86,399 and765 are related title leads, not proven duplicates.

**Sentiment/style.** The [official method](https://www.quantconnect.com/research/15310/sentiment-and-style-rotation-effect-in-stocks/) conditions style holdings on VIX/put-call relationships. Its current custom input URL names `totalpc.csv` despite equity-ratio prose; the licensed legacy fragment uses `equitypc.csv`. That discrepancy must be resolved before treating either series as equivalent. Free coverage, rights, release time and point-in-time style membership remain unqualified. Preserve two distinct state features and a conditional style preference; do not collapse them into a calibrated market-loss score.

**ML predictor.** The [GBM tutorial](https://www.quantconnect.com/research/15270/gradient-boosting-model/) forecasts10-minuteSPY returns from technical indicators, uses monthly training and explicitly omits training implementation from its method fragment. It reports underperformance versusSPY; that is a source claim, not our reproduction. Daily local prices cannot support this exact horizon. Mature labels, chronological fitting and execution costs remain prerequisites. Return forecast and variance-state probability are different interfaces.

## Local source verification and reuse

Three already-saved Apache2.0 method fragments from `QuantConnect/Tutorials` revision `4a341890296f7e79e095508f06170c72ccaa629c` were read and their hashes verified against the [existing package review](../../research/catalogs/qc-tutorial-packages-v1/review.json). That review qualifies no complete licensed implementation for these three tutorials. Fragment rights do not grant rights to attached website backtests, neighboring unlicensed repositories, market data or result artifacts. The HMM page has no pinned live revision or separately verified source-export grant in this review. No third-party source was copied into maintained code.

The [machine receipt](evidence/2026-10-28-qc-market-components.json) records exact paths, hashes, source URLs, interfaces, unknowns and dispositions. Mutable official pages were observed2026-10-28; their exact live revision is unknown. Three web calls were used within the eight-call cap. This is a finite screening task, not a financial RSI cycle or Calmar improvement claim.

## Best next bounded question

Start with **zero-financial causal overlap analysis**: does one frozen broad-index trend context add information beyond our existing EMA/volatility gate, or mostly duplicate it? Preserve original gate decisions and inspect missed rebounds, warnings while already in cash, information timestamps and state disagreement on saved viewed history. First qualify the chosen proxy and distinguish large-cap substitution from whole-market coverage. Only after that result should a separately frozen one-stage financial comparison receive a budget. HMM is a later challenge against the simple realized-volatility baseline; sentiment is held for data identity, and intraday GBM belongs in another lane.

Lesson: a regime chart, sentiment-conditioned allocation and return forecast can all look like “market intelligence” while solving different tasks. Extract typed causal outputs and simple controls before combining them.
