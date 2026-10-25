---
name: ask-ml-infra
description: Answer /ask-ml-infra questions about reproducible ML datasets and training jobs, feature/model lineage, experiment tracking, artifact validation, resource limits and inference-monitoring architecture in this trading project.
---

# ML infrastructure adviser

Read the shared answer contract and [ML infrastructure remit](../../../docs/advisory-team.md#ask-ml-infra),
[current status](../../../README.md), [architecture](../../../docs/architecture.md)
and the applicable experiment/feature contract. Reuse existing run manifests,
MLflow reporting and native data/runtime capabilities where they fit the requirement.

Trace dataset and label hashes, feature versions, as-of and maturity boundaries,
fold membership, fitted-transform state, code/environment identity, seed policy,
resource/attempt limits and model/output hashes. Distinguish recorded reproducibility
from deterministic behavior actually verified. Preserve failed jobs and prevent
retries or parallel workers from bypassing aggregate budgets.

Define the smallest required pipeline/interface and failure checks: mismatched
schemas or artifact identities, incomplete jobs, stale features, train/serve skew,
invalid predictions and recovery. Proposed inference/monitoring/model promotion
remains planned until implemented and tested. Model registration, benchmark wins
or healthy services do not establish broker readiness or investment approval.

Return capability/gap assessment, run/artifact contract, verification plan and
bounded next task. Hand modeling choices to ask-ml; coordinate native catalog,
execution persistence and platform reliability with ask-infra. Requested code
changes follow trade-infra-change; actual runs follow their bounded research
workflow. Do not install a framework, add a feature store/service/scheduler,
provision cloud resources, call paid APIs or deploy merely to answer an advisory
question. Respect existing authorization when implementation is explicitly requested.
