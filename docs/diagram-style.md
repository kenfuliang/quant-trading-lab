---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Diagram style and QA SOP

This document owns the preferred diagram style and production/inspection procedure.
The [catalog](skills.md) owns discovery and readiness; [architecture](architecture.md)
owns system boundaries; [research development](research-development.md) owns stage
handoffs. PNGs are derived presentations, not independent policy or roster owners.
The [trade-diagram skill](../.agents/skills/trade-diagram/SKILL.md) applies this SOP.

```text
Canonical sources → choose view and scope → layered layout → render PNG
       ↑                                                    ↓
       └──────── correct source/visual mismatch ← inspect every export
```

## Preferred visual language

- Warm cream canvas, dark ink, restrained pastel cards and dashed rounded group
  boundaries. Exact palette values and drawing helpers live in the
  [renderer](../scripts/render_team_skills.py), rather than a second palette list.
- Handwritten headings with readable body text. Prefer available local fonts;
  fall back to readable bundled fonts and cover arrow glyphs. Do not bundle fonts
  without redistribution rights or download fonts merely to reproduce this style.
- Use layers for related responsibilities, cards for roles/stages, and arrows for
  actual handoffs. Label the artifact or decision crossing a boundary where useful.
  Keep a team ownership view distinct from an execution or research-cycle view.
- Short titles, enough whitespace and concise content. Split an overloaded view
  rather than shrink text until the exported image becomes difficult to read.
- Write IMPLEMENTED, PLANNED and UNVERIFIED as text; color alone is insufficient.
  Qualify IMPLEMENTED to the specific instructions, tests or tooling that exist.
  Written SOPs do not prove exercised recovery; advisory roles do not prove staffed
  independent teams; tracked results do not prove alpha or broker readiness.

User-requested alternatives take precedence over the default style. For quantitative
plots, use the applicable analytical chart workflow instead of turning data into
decorative architecture cards. For explicit image edits, follow the environment's
image-editing tool rules; this renderer handles source-driven diagram exports.

## Existing exports

From the repository root, using the pinned local environment:

```sh
.venv/bin/python scripts/render_team_skills.py --diagram team
.venv/bin/python scripts/render_team_skills.py --diagram research
.venv/bin/python scripts/render_team_skills.py --diagram all
```

Default outputs are [team-skills.png](diagrams/team-skills.png) and
[research-workflow.png](diagrams/research-workflow.png). Preserve historical research
artifacts; these are refreshable presentation exports. For a bounded test, select
a new output directory, for example:

```sh
.venv/bin/python scripts/render_team_skills.py --diagram team --output-dir .local/diagram-test/team
.venv/bin/python scripts/render_team_skills.py --diagram research --output-dir .local/diagram-test/research
```

Use an unused directory when retaining evaluation evidence. The renderer checks
displayed roles/workflows against catalog entries and fails on layout/catalog
mismatch; it does not independently infer changes to readiness or assess all prose.
Review source owners before refreshing captions. The drawing helpers can support
another explicitly implemented view; the CLI currently supports only these two.

## Acceptance and handoff

1. Check semantic fidelity: exact skill names, correct ownership, useful artifact
   handoffs, all trials/failures retained conceptually, and no implied automatic
   deployment or unsupported readiness claim.
2. Open each PNG at normal viewing size and inspect legibility, clipping, overlap,
   arrow direction, contrast, status text and source references. A file signature
   or a passing script does not replace visual inspection.
3. Run relevant checks. `make docs-check` verifies references/catalog inventory;
   `make check` verifies the offline suite. Rendering tests validate view selection,
   output isolation and catalog mismatch behavior, not subjective visual quality.
4. Deliver requested PNGs and their real paths, source owners, any remaining
   limitation, and actual validation results. State whether changes are local,
   committed or published. A usage test is not proof of improved agent quality.

The reference image is style inspiration only. Do not copy its tool architecture,
numeric thresholds or claims into this project's capability truth.
