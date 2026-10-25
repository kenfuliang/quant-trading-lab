---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# ML modeling and ML infrastructure advisers

Work status: complete for role/skill creation and RSI handoff documentation.
Requested2026-10-25: add both teams. Canonical owner:
[advisory contracts](../advisory-team.md#ml-team-handoff-in-rsi);
[skill map](../skills.md) owns discovery, [lifecycle](../research-development.md)
owns bounded work and [architecture](../architecture.md) owns infrastructure.

Created [`ask-ml`](../../.agents/skills/ask-ml/SKILL.md) and
[`ask-ml-infra`](../../.agents/skills/ask-ml-infra/SKILL.md). They are advisory team
perspectives, not launched agents or independent validation. Their remits cover
modeling target/baseline/calibration/evaluation and ML data/run/artifact reliability,
respectively. Quant retains economic/evidence review, infra the native platform,
algo forecast-to-order logic, and risk downside/promotion constraints.

Updated AGENTS exact-prefix routing, trade-project, skill hierarchy/counts,
README capability status and RSI handoff. Seven advisers plus five general and
ten research workflows give22project-local skills. Native slash-menu registration
and a generic ML training/inference service remain unimplemented.

Manual routing review cases:

| Request | Primary owner / required handoff |
| --- | --- |
| Define a target and a simple predictor benchmark | ask-ml; quant checks mechanism and information boundary |
| Diagnose calibration and sparse gate labels | ask-ml; existing robust-evaluation workflow |
| Specify dataset/fold/transform/model hashes and reload checks | ask-ml-infra; native infra seams remain ask-infra |
| Define pure causal feature formulas | trade-feature-engineering, with modeling consultation as needed |
| Translate a forecast to positions/orders | ask-algo and ask-risk; model score does not authorize trading |

Both roles require requested bounded execution before training/search, preserving
existing free/local constraints. No fit attempts, financial runs, agents, package
installations, services, cloud resources, paid APIs, broker changes, commits or
publication were launched by this task.

Validation: both new skills passed the bundled skill validator using existing
system Python/PyYAML; documentation/link metadata and whitespace checks passed.
This verifies packaging/references and the manually reviewed responsibilities,
not measured role effectiveness or a staffed team. No runtime behavior changed,
so no model training or additional software tests were needed.
