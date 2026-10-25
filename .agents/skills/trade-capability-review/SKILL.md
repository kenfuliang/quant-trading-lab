---
name: trade-capability-review
description: Assess what the pinned NautilusTrader version already supplies, including installed Python versus Rust interfaces, optional dependencies, and compatibility before adding or replacing infrastructure.
---

# Nautilus capability review

Locate this repository and read [documentation conventions](../../../docs/README.md),
[capability matrix](../../../docs/capabilities.md), and the relevant upstream
reference. Verify vendor revision/dirty state and installed version before drawing
compatibility conclusions. Use local pinned source before relying on latest docs.

For import/configuration evidence, use the existing
`scripts/audit_nautilus_capabilities.py` from the repository root. It emits JSON
without constructing nodes or connecting. Preserve dated receipts; run new probes
to stdout or a new evidence path rather than overwriting historical evidence.

Inspect the exact runtime and adapter path. Distinguish source presence, installed
symbol, configured facility, behavior verification and external integration.
Python/Cython and Rust/PyO3 surfaces are not interchangeable by assumption.

Record a reuse/configure/extend/defer decision with source evidence, verification
level and actual gap. Update the matrix when requested; change roadmap/architecture
only when in scope and supported by findings. Readiness is not established by an
upstream test existing. Stop at the review's evidence level; separate behavior or
broker experiments require their own task scope.
