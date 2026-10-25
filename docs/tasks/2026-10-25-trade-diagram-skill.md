---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# trade-diagram skill and two-view usage test

Task state: complete for local creation and two-view usage acceptance. Scope: package the existing preferred PNG style as a
project-local skill, register it in the catalog and exercise team/research exports.
The [diagram style SOP](../diagram-style.md) owns style and QA; the
[catalog](../skills.md) owns discovery and readiness. Rendering remains in the
shared project script, not a duplicate skill asset.

## Acceptance fixed before testing

1. Skill format/references validate and the catalog matches installed entrypoints.
2. Following the skill/SOP, independently select team and research CLI views into
   separate unused local directories. Each produces only its requested valid PNG
   without changing existing presentation exports.
3. Inspect both images for preferred styling, exact skill names, SOP references,
   artifact handoffs, readable layout and qualified readiness labels. A written
   skill is not proof of better model answers or operational readiness.
4. Refresh the two requested presentation exports, run relevant offline checks and
   retain source/output identities and actual results in an evaluation receipt.

## Results

Skill format validation passed. The catalog now matches 23 installed entrypoints.
Both independently selected CLI views produced only their requested valid PNG
(2868 × 1947) in new local output directories; original presentation exports stayed
unchanged during that test. Visual inspection found tight SOP/status spacing in the
team view; the first outputs and source snapshot were retained, spacing was revised,
and the inspected revision passed. The research image was unchanged by that fix.

The final presentation exports exactly match the inspected revision bytes. Two
new regression tests cover selected outputs/isolation and rejection of an unmapped
workflow before output. `make check` passed all 223 offline tests, dependency
consistency and documentation/catalog checks. The
[evaluation receipt](evidence/2026-10-25-trade-diagram-skill.json) records source,
output, dimensions, hashes and the preserved first-pass correction.

This is a local usage/acceptance test, not a blind comparison or independent
agent evaluation; no incremental answer-quality benefit is claimed. The supported
CLI views are team and research. New architectural views require an actual layout
extension using the shared helpers. No financial experiment, model training,
service startup, broker operation, commit or publication was performed.
