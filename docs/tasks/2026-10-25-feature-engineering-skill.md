---
status: active
updated: 2026-10-25
owner: research-maintainers
---

# Feature-engineering skill and first saved-SPY test

Work status: complete for skill creation, RSI integration and the bounded saved-data diagnostic.
Requested2026-10-25: research established features/LLM engineering, build the skill,
connect RSI and test existing SPY inputs/outcome labels. Canonical owners:
[feature contract](../feature-engineering.md), [RSI lifecycle](../research-development.md),
[skill hierarchy](../skills.md), [scoring](../research-scoring.md). No new strategy
performance or infrastructure milestone is claimed.

## Research first and concrete reuse

Original sources reviewed before fixing candidates:

- Qlib `Alpha158/Alpha360`, pinned54355232463878d2eebb91fe0ee5fa7fa1f5976c:
  [loader](https://github.com/microsoft/qlib/blob/54355232463878d2eebb91fe0ee5fa7fa1f5976c/qlib/contrib/data/loader.py)
  and [benchmark](https://github.com/microsoft/qlib/blob/54355232463878d2eebb91fe0ee5fa7fa1f5976c/examples/benchmarks/README.md).
  Reuse interpretable operator families and separate signal/portfolio diagnostics.
- [101Formulaic Alphas,2016v3](https://arxiv.org/abs/1601.00991v3): reusable
  price/volume expression vocabulary. No single-SPY relabeling of cross-sectional
  ranks and no101-formula sweep.
- [RD-Agent(Q),2025v2](https://arxiv.org/html/2505.15155v2), repo inspected at
  484776c211e4fbbeef03e0ec00d6bbee7362a4f4: hypothesis→implementation→validation→
  feedback and recorded research tasks. No framework adoption, agents or API calls.
- [AlphaAgent,2025v2](https://arxiv.org/abs/2502.16789v2): hypothesis/formula
  alignment, duplicate/formula similarity and complexity control. The current
  study uses fixed reviewed functions, not arbitrary LLM expression execution.

The [canonical contract](../feature-engineering.md#established-feature-families-and-source-reuse)
records iconic feature families, unavailable inputs and transfer limitations.
These public results remain source claims, not our reproductions. No upstream
code/data licensing or paid-data adoption is asserted. A nonmatching arXiv record
encountered during lookup was excluded; the correct AlphaAgent identifier is
2502.16789v2. No unrelated paper supplied evidence.

## Installed skill and RSI integration

[`trade-feature-engineering`](../../.agents/skills/trade-feature-engineering/SKILL.md)
is created project-locally and routes through `trade-project` and the skill map.
Ten research workflows and20total local skills now exist. Feature work fits between
input audit and experiment, or after diagnosis when a bounded feature question is
registered. It does not automatically launch trading-rule ablations or promotion.

The skill owns procedure; the canonical feature contract owns meanings; pure
implementation lives in `research/feature_engineering.py`; the saved-SPY entrypoint
is `scripts/feature_diagnostic.py`. No duplicated feature code inside skill assets.
Existing numerical and temporal evidence remain unchanged.

## Frozen test

[Design](../../research/plans/spy-feature-diagnostic-v1.design.json) fixed before
new feature outcomes were examined: three candidates, one proposal round,
one21-session label horizon, zero financial simulations, new downloads, paid/API
calls or package installs. The current assistant generated the proposals from
already viewed history and research; there was no external LLM request or blind
LLM-versus-human comparison.

| Candidate | Fixed formula at preceding close | Reference/question |
| --- | --- | --- |
| Volatility ratio20/60 | Sample standard deviation20returns divided by60returns | Risk dynamics beyond existing sigma20 |
| EMA gap | EMA50/EMA200−1, same adjust/minimum history as saved rule | Continuous trend distance beyond binary crossover |
| Average range20 | Mean20of(high−low)/close | Range-based risk proxy and redundancy with sigma20 |

All OHLC rounded to cents per existing fixture, shifted exactly once to next
session. Full2004warmup;5,283existing2005–2025decision sessions. Labels are the
saved5bpprice-peak-ablated EMA comparison, unchanged21-session account returns,
gaps and outcome classes. Existing sigma20and binary EMA are two references,
not additional candidate searches. Future21-session raw-SPY volatility is a
separate realized-risk outcome, not a contemporaneous input or a trading forecast.

Bin boundaries and sigma20median use2005–2011features only. For calibration and
fixed2012–2018/2019–2025development blocks, retain labels only if they mature
within that block. All periods remain viewed development. Report all90predeclared
association cells (three candidates plus two references × three targets × three
periods × two sampling views); no strongest-cell selection or unadjusted p-values.
A fixed21-session stride reduces future-window overlap but does not create
independent samples or remove persistent volatility dependence.

## Actual findings

[Browser-readable diagnostic](http://127.0.0.1:8765/features/20261025-v1/index.html)
and ignored `.local/performance/features/20261025-v1/` preserve the registry,
causal input matrix, separate joined-outcome diagnostic, fixed cuts, associations,
redundancy, bin counts and immutable code/source manifests.

All five candidate/reference columns are finite across5,283evaluation sessions.
Prefix/future perturbation passed at three real-source boundaries;15,849scalar
formula/risk checks passed. Independent comparison of EMA gap with saved prior-close
fast/slow indicators is included in the final receipt. Source/calendar/action/
publication/rights limitations and modeled ex-date dividend cash remain visible.

### Subsequent risk: time-series rank association

Each block has83fixed-stride complete21-session outcome anchors. These are
Spearman correlations with subsequently realized annualized volatility, not IC
across stocks, calibrated forecasts, significance tests or alpha.

| Input |2012–2018|2019–2025|
| --- | ---: | ---: |
| Candidate: volatility ratio20/60 |0.103|0.222|
| Candidate: EMA gap |−0.034|−0.298|
| Candidate: average range20 |0.346|0.534|
| Reference: sigma20 |0.292|0.494|
| Reference: binary EMA |−0.105|−0.409|

The primary ratio is not a stronger standalone risk association than sigma20in
these views. Range has a higher association but rank correlation with sigma20is
0.928and0.946on the block's complete daily rows: substantial redundancy. No formal
incremental predictive test, confidence interval or superiority claim follows.
Ratio-versus-sigma20correlations are0.601and0.537, so it is not a duplicate by
rank correlation alone.

Using fixed calibration terciles, ratio low/middle/high bins have subsequent mean
annualized volatility10.75/12.10/12.54%in2012–2018and14.26/14.38/21.02%in2019–2025.
These daily outcomes overlap. Within sigma20strata the ordering is not uniform:
in low-sigma2012–2018it is10.76/11.77/10.32%; in high-sigma2019–2025it is
19.14/19.67/23.77%. This supports a context question, not a universal ratio threshold.

Return associations are unstable: ratio versus future base-account return is
+0.103then−0.059on the fixed-stride anchors. EMA gap changes−0.042to+0.121;
range changes+0.137to−0.072. Risk association must not become a profit score.

### Existing gate labels and sample limits

Ratio terciles contain only4/0/2distinct reduction-episode starts in2012–2018
and4/1/4in2019–2025. Corresponding actionable-session counts14/3/22and26/24/52
are repeated/overlapping policy decisions, not more independent episodes. Some
sigma/feature cells have zero episode starts. Preserve full helped/missed/worsened
counts in `bins.json`; do not infer a stable classifier, calibrated probability
or decision threshold from these sparse cells.

## Evaluation and decision

**Skill useful for the scoped task:** it produced a traceable registry, caught the
need to distinguish risk/return targets, enforced causality and fixed calibration,
retained redundant/inconclusive results, and identified inadequate gate-label
samples. This is an exercised workflow with deterministic checks, not evidence
that skill instructions causally improve research versus a no-skill assistant.

- Primary volatility ratio: **inconclusive incremental value**; retain as a research
  reference, not a selected trading input. Do not launch a ratio threshold search.
- Average range: **redundancy caution**; no automatic addition despite stronger
  standalone risk association.
- EMA gap: **unstable return relationship**; no directional entry rule adopted.
- Next informative question, proposal only: would a strictly prospective calibrated
  risk model using sigma20plus the ratio improve risk forecasting versus sigma20
  alone? That needs a separately scoped model, evaluation and resource budget.
  The prior continuous-sizing proposal remains unchanged and unexecuted.

Eight synthetic regression tests exercise future perturbation, prefix/lag,
independent formulas, zero/invalid inputs, train-only cuts, target anchoring and
maturity boundary. Manual skill-contract review covers leakage proposal rejection,
unavailable cross-sectional inputs and finite candidate-budget handling. There
was no independent agent forward-test or measured LLM performance advantage.

Skill validator initially lackedPyYAMLin the project environment; the same bundled
validator passed using system Python's existingPyYAML6.0.3without installation or
project dependency changes. Final checks and exact identities are in the
[machine receipt](evidence/2026-10-25-feature-engineering-skill.json).

Final validation:216tests passed,77documentation/skill files passed link and metadata checks, dependencies consistent, and `git diff --check` passed. Skill structure validated with the bundled validator via system Python. Browser readback confirmed the registry, quality,83-anchor association counts, fixed-bin results, small episode counts and downloads. No feature or policy search followed the findings.
