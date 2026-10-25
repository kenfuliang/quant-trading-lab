---
name: trade-feature-engineering
description: Define and test causal trading features, audit redundancy and feature-label relationships, or translate bounded LLM feature ideas into reproducible diagnostics on qualified saved inputs.
---

# Trading feature engineering

Read the [feature-engineering contract](../../../docs/feature-engineering.md),
[research lifecycle](../../../docs/research-development.md) and the requested
study's exact input/label manifests. Use research intake for external claims.
Finish the requested stage; a feature diagnostic does not launch strategy tuning.

For design, record the mechanism, formula/operator implementation, required fields,
units, window/minimum history, availability/lag, invalid/zero/missing behavior,
family, proposal provenance and expected incremental information beyond existing
features. Freeze candidate count, targets/horizons, comparison baselines, period
roles and stopping rule before reading new outcomes. Existing viewed history and
LLM knowledge of historical events remain development exposure.

For an authorized saved-data test, use or extend the pure feature builder and
bounded diagnostic entrypoint linked by the contract. Do not execute arbitrary
LLM-generated expressions. Verify source/label hashes, causal prefix and future-
perturbation behavior, independent formulas, maturity joins, invalid/constant
inputs and train-only fitted transforms. Keep outcome tables separate from inputs.
Preserve failed attempts; do not repair a failing feature by searching alternatives.

Evaluate eligibility/coverage, redundancy, temporal stability and target-specific
association with counts. Distinguish single-series time association from cross-
sectional IC. Gate-success labels are conditional on the gate and subsequent
policy, not independent forecasts or causal effects. Report small samples,
overlap/dependence, mechanical relationships and unavailable confidence; no
accuracy/alpha claim from descriptive bins or hindsight labels.

LLMs may propose economic mechanisms, simple formulas, tests and critiques within
the frozen proposal budget. Record prompts/context provenance and all proposals,
including rejected duplicates or unimplementable ideas. Similarity and complexity
checks do not certify novelty or alpha; a fluent rationale is not evidence.
Do not add external model calls, uploads, model training or agent delegation unless
that work is within the user's scope and resource limits.

Deliver the registry, immutable diagnostic manifest, quality/causality evidence,
comparison report and a retain-for-next-test/redundant/blocked/inconclusive finding.
Link the next discriminating question without automatically running it. A trading
rule ablation requires its own scoped design/execution budget; do not infer
financial improvement, promotion or broker permission from feature diagnostics.
