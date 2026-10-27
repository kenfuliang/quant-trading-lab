---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Layered team and research workflow exports

Task state: complete for local generation and validation. User requested the
reference image's grouped panels, restrained pastel colors and hand-drawn visual
style, with clear skills, SOPs, handoffs and readiness labels.

## Delivered

- [Team map](../diagrams/team-skills.png): mandate, coordination, acceptance,
  advisory roles, shared procedures, handoff contracts and tooling/readiness.
- [Research workflow](../diagrams/research-workflow.png): intake/design, input
  audit, feature/model design, bounded experiment, diagnosis/evaluation and
  decision/history, with labeled artifact handoffs and the evidence feedback path.
- [Renderer](../../scripts/render_team_skills.py): generates both exports,
  checks displayed roles/workflows against the canonical catalog, and uses local
  handwritten fonts with a portable readable fallback. No font files are bundled.

The [catalog](../skills.md) owns roster/readiness, the
[research procedure](../research-development.md) owns handoffs, and root README
owns current capabilities. The diagrams are presentation snapshots, not new
policy registries. Role-to-skill groupings show typical shared use, not exclusive
ownership. IMPLEMENTED is qualified to instructions or a scoped tooling slice;
PLANNED describes unbuilt work; UNVERIFIED describes incomplete evidence.

## Validation and scope

Both final PNGs were rendered and visually inspected for legible labels, layout,
status distinctions and handoffs. A first pass exposed missing arrow glyphs and
tight status spacing; font fallback and layout spacing were corrected.
`make check` passed documentation/link/catalog validation, dependency consistency
and 221 offline tests before the final presentation-only spacing adjustment;
documentation checks passed again with this receipt.

No financial simulation, training, service, broker operation or readiness upgrade
was performed. Prior research artifacts remain unchanged. The previous team PNG
is preserved in Git history; these exports have not been committed or published.
