# Project instructions

This workspace is building a local trading platform. Current priority is
infrastructure reliability and observability. Use existing research as a fixture;
strategy tuning belongs to an explicitly requested research task.

- Start with [README](README.md) for implemented capabilities and blockers.
- For every research cycle, follow the single [golden research standard](docs/research-standard.md).
  Freeze one change and finite bounds, log all attempts/evidence and close with a lesson.
  Use its cycle register and paper-report criteria; do not duplicate adoption rules.
- Before documentation edits, read [documentation conventions](docs/README.md).
- For implementation, review [architecture](docs/architecture.md), then follow
  [development workflow](docs/workflow.md). Select work from [roadmap](docs/roadmap.md).
- For environment checks, use [local operations](docs/operations/local.md).
  For broker checks, use [paper observation](docs/operations/paper-connection.md).
  For failures or uncertain external state, use [incident SOP](docs/operations/incidents.md).
- For team selection, skill discovery or `/ask-*` routing, use the single
  [teams and skills catalog](docs/skills.md), or the `trade-project` router.
  Read the selected SKILL.md and linked role contract/procedure. The catalog owns
  exact prefixes and readiness; planned entries are not installed. Consultation
  does not launch agents or mutate platform/broker state by default.
- Preserve existing datasets, run evidence, and unrelated work. Verify Git state
  before changing it.
- Credentials stay outside tracked files. Broker operations follow the paper SOP;
  ordinary local verification must remain offline and order-free.
- Include a diagram when explaining structure or flow. Describe validation actually
  performed and distinguish implemented, unverified, blocked, and planned behavior.
