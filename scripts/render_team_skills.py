#!/usr/bin/env python3
"""Export layered team/research maps from the catalog and canonical SOP context.

Layout and captions are presentation, not a second roster or readiness registry.
No services, model training, market data or broker access is used.
"""
from pathlib import Path
import argparse
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'docs/skills.md'
OUTPUT = ROOT / 'docs/diagrams'
INK = '#242921'
PAPER = '#f7f3e9'
COLORS = dict(green='#dce9d4', blue='#dbe8f2', purple='#e3d9ec', orange='#f2d8bf', white='#fffdf7')
FONTS = {f.name for f in font_manager.fontManager.ttflist}
HEADING = 'Marker Felt' if 'Marker Felt' in FONTS else 'DejaVu Sans'
BODY = 'Chalkboard' if 'Chalkboard' in FONTS else 'DejaVu Sans'


def catalog():
    source = CATALOG.read_text()
    parts = re.split(r'^## ', source, flags=re.M)
    sections = {part.split('\n', 1)[0]: part for part in parts[1:]}
    def names(title):
        return re.findall(r'^\| \[([^\]]+)\]\(\.\./\.agents/skills/[^/]+/SKILL\.md\)', sections[title], re.M)
    roles = names('Available advisory skills')
    skills = names('Available project skills') + names('Available research workflows')
    updated = re.search(r'^updated: (.+)$', source, re.M)[1]
    return roles, skills, updated


class Map:
    def __init__(self, title, subtitle, date, output=OUTPUT):
        self.output = Path(output)
        self.fig, self.ax = plt.subplots(figsize=(21, 14), dpi=170)
        self.fig.patch.set_facecolor(PAPER)
        self.ax.set(xlim=(0, 100), ylim=(0, 100))
        self.ax.axis('off')
        self.text(3, 98.8, title, 26, heading=True)
        self.text(3, 94.1, subtitle, 12)
        self.text(97, 98.5, date, 11, ha='right')
        self.text(3, 91, 'IMPLEMENTED = scoped code / instructions     PLANNED = not built     UNVERIFIED = proof incomplete', 10.5)

    def text(self, x, y, value, size=11, heading=False, **kwargs):
        return self.ax.text(x, y, value, va='top', fontsize=size, color=INK,
                            family=[HEADING if heading else BODY, 'DejaVu Sans'], linespacing=1.35, **kwargs)

    def outline(self, x, y, w, h, color='white', dashed=False, lw=1.3):
        patch = FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.35,rounding_size=1.2',
                              facecolor=COLORS[color] if color else 'none', edgecolor=INK,
                              linewidth=lw, linestyle=(0, (4, 3)) if dashed else '-')
        patch.set_sketch_params(scale=.35, length=100, randomness=1.2)
        self.ax.add_patch(patch)

    def panel(self, x, y, w, h, title):
        self.outline(x, y, w, h, color=None, dashed=True)
        self.text(x + 1, y + h - .8, title, 16, heading=True)

    def card(self, x, y, w, h, title, lines, color='white', status=None, size=11):
        self.outline(x, y, w, h, color)
        self.text(x + 1, y + h - .8, title, 14, heading=True)
        self.text(x + 1, y + h - 4.1, '\n'.join(lines), size)
        if status:
            self.text(x + 1, y + 1.85, status, 9.2, weight='bold')

    def arrow(self, points, label=None, label_at=None, dashed=False):
        for a, b in zip(points[:-2], points[1:-1]):
            self.ax.plot([a[0], b[0]], [a[1], b[1]], color=INK, lw=1.2,
                         linestyle='--' if dashed else '-')
        arrow = FancyArrowPatch(points[-2], points[-1], arrowstyle='->', mutation_scale=15,
                                lw=1.2, color=INK, linestyle='--' if dashed else '-')
        arrow.set_sketch_params(scale=.25, length=100, randomness=1.1)
        self.ax.add_patch(arrow)
        if label:
            self.text(*label_at, label, 9.5, ha='center', bbox=dict(facecolor=PAPER, edgecolor='none', pad=1))

    def save(self, name, sources):
        self.text(3, 3.1, sources, 9.2)
        self.text(3, 1.3, 'Presentation snapshot • roles are invoked on demand • each experiment remains explicitly bounded • no automatic trading', 9.2)
        self.output.mkdir(parents=True, exist_ok=True)
        path = self.output / name
        self.fig.savefig(path, facecolor=PAPER, bbox_inches='tight', pad_inches=.3)
        plt.close(self.fig)
        print(path)


def team(roles, skills, date, output=OUTPUT):
    m = Map('OUR QUANT TEAM + SHARED SKILLS',
            f'{len(roles)} advisory roles • {len(skills)} shared workflow skills • collaboration, procedures and readiness', date, output)
    m.panel(3, 74, 24, 14, 'MANDATE LAYER')
    m.card(4, 75, 22, 9.5, 'YOU / PROJECT MANDATE',
           ['Objectives • risk tolerance • scope', 'SOP: docs/goals.md'], 'white', 'IMPLEMENTED • mandate record', size=10)
    m.panel(31, 74, 35, 14, 'COORDINATION LAYER')
    m.card(32, 75, 33, 9.5, '/ask-director + trade-project',
           ['Priorities → owner → bounded next task', 'SOP: docs/advisory-team.md'], 'orange', 'IMPLEMENTED • advisory instructions', size=10)
    m.panel(71, 74, 26, 14, 'ACCEPTANCE LAYER')
    m.card(72, 75, 24, 9.5, 'EVIDENCE BEFORE PROMOTION',
           ['Budgets • falsifiers • risk review', 'SOP: docs/research-scoring.md'], 'purple', 'IMPLEMENTED • decision contracts', size=10)
    m.arrow([(27.5, 81), (30.5, 81)])
    m.arrow([(66.5, 81), (70.5, 81)])
    m.panel(3, 29, 66, 40, 'ADVISORY TEAM • shared workflows, not exclusive assignments')
    role_cards = [
        ('/ask-infra', 'Native platform + reliability', ['trade-capability-review', 'trade-infra-change', 'trade-local-ops'], 'blue'),
        ('/ask-quant', 'Hypotheses + research evidence', ['trade-research-intake', 'trade-research-design', 'trade-data-audit'], 'green'),
        ('/ask-algo', 'Trading logic + implementation', ['trade-experiment', 'trade-performance-diagnosis'], 'orange'),
        ('/ask-risk', 'Downside + readiness challenge', ['trade-robust-evaluation', 'trade-portfolio-analysis', 'trade-promotion-review'], 'purple'),
        ('/ask-ml', 'Prediction + feature hypotheses', ['trade-feature-engineering', 'trade-candidate-evolution', 'trade-robust-evaluation'], 'green'),
        ('/ask-ml-infra', 'Reproducible ML run contracts', ['trade-research-history', 'trade-infra-change'], 'blue'),
    ]
    if set(roles) != {'/ask-director', *(r[0] for r in role_cards)}:
        raise ValueError('Review the layout for the changed advisory catalog.')
    displayed = {'trade-project', 'trade-diagram'}
    for i, (name, remit, assigned, color) in enumerate(role_cards):
        displayed.update(assigned)
        x, y = 4.3 + (i % 3) * 21.3, 49 if i < 3 else 31
        m.card(x, y, 19.5, 16, name, [remit, '', *assigned], color,
               'IMPLEMENTED • instructions', size=9.3)
    if displayed != set(skills):
        raise ValueError('Every cataloged workflow must be represented in the team map.')
    m.panel(73, 29, 24, 40, 'SOP / KNOWLEDGE LAYER')
    m.card(74, 47, 22, 18, 'SHARED PROCEDURES',
           ['trade-diagram → PNG exports', 'Development → docs/workflow.md', 'Research → research-development.md', 'Features → feature-engineering.md', 'Local ops → operations/local.md', 'Incidents → operations/incidents.md'],
           'white', 'IMPLEMENTED • procedure documents', size=9.1)
    m.card(74, 31, 22, 14, 'HANDOFF CONTRACT',
           ['Question + owner + input hashes', 'Limits + outputs + failures', 'Decision + next evidence step'],
           'purple', 'IMPLEMENTED • scoped handoff rules', size=10)
    m.arrow([(48, 73.3), (48, 70)], 'scope + owner', (54, 72))
    m.arrow([(72.2, 52), (69.5, 52)])
    m.panel(3, 6.7, 94, 18, 'TOOLING + OPERATIONAL BOUNDARIES')
    m.card(4.3, 8, 29, 12.3, 'LOCAL RESEARCH + TRACKING',
           ['Saved SPY ledgers / diagnostics', 'Nautilus reports + MLflow imports'], 'green',
           'IMPLEMENTED • scoped saved-data path', size=10)
    m.card(35.8, 8, 29, 12.3, 'AUTOMATION + EXECUTION',
           ['Generic retraining / model serving', 'Paper-order and live execution paths'], 'orange',
           'PLANNED • no automatic activation', size=10)
    m.card(67.3, 8, 28.4, 12.3, 'EVIDENCE STILL NEEDED',
           ['Broker connection + full restore', 'Independent alpha / learned benefit'], 'purple',
           'UNVERIFIED • proof incomplete', size=10)
    m.arrow([(35, 28.3), (35, 25.5)], 'receipts + recommendations', (49, 27.2))
    m.save('team-skills.png', 'Owners: docs/skills.md • docs/advisory-team.md • docs/README.md • current capability truth: README.md')


def workflow(skills, date, output=OUTPUT):
    m = Map('BOUNDED RESEARCH • RECURSIVE IMPROVEMENT',
            'Explicit handoffs → preserved evidence → one justified next question; no unattended optimizer implied', date, output)
    m.panel(3, 74, 25, 14, 'INPUT / MANDATE LAYER')
    m.card(4, 75, 23, 9.5, 'QUESTION + FIXED BUDGET',
           ['Objective • controls • stop criteria', 'SOP: goals.md / research-development.md'],
           'white', 'IMPLEMENTED • bounded design rules', size=9.6)
    m.panel(33, 74, 33, 14, 'EVIDENCE / KNOWLEDGE LAYER')
    m.card(34, 75, 31, 9.5, 'RESEARCH HISTORY + SCORE CONTRACT',
           ['All trials, failures, hashes and decisions', 'SOP: research-scoring.md / task receipts'],
           'green', 'IMPLEMENTED • saved records + controller', size=9.6)
    m.panel(71, 74, 26, 14, 'SOP / REVIEW LAYER')
    m.card(72, 75, 24, 9.5, 'OWNER + ACCEPTANCE RULES',
           ['Quant / ML / infra / risk handoffs', 'SOP: workflow.md / advisory-team.md'],
           'purple', 'IMPLEMENTED • consultation contracts', size=9.5)
    m.arrow([(28.5, 81), (32.5, 81)])
    m.arrow([(66.5, 81), (70.5, 81)])
    m.panel(3, 27, 94, 41.5, 'BOUNDED RESEARCH LOOP • request can select one stage; each stage has its own scope')
    steps = [
        (5, 49, '1. INTAKE + DESIGN', ['trade-research-intake', 'trade-research-design', '', 'Handoff: hypothesis / plan / trial cap'], 'green', 'IMPLEMENTED • instructions + plans'),
        (36, 49, '2. AUDIT INPUTS', ['trade-data-audit', '', 'Handoff: provenance / quality / rights', 'Invalid or unqualified → stop'], 'blue', 'IMPLEMENTED • scoped saved-input checks'),
        (67, 49, '3. FEATURES + MODEL DESIGN', ['trade-feature-engineering', '/ask-ml ↔ /ask-ml-infra', 'Handoff: causal matrix / matured labels', 'Generic training pipeline: PLANNED'], 'purple', 'IMPLEMENTED • feature diagnostics'),
        (67, 29, '4. BOUNDED EXPERIMENT', ['trade-experiment', '', 'Handoff: config / ledgers / costs / audit', 'Frozen limits; preserve failed trials'], 'orange', 'IMPLEMENTED • offline simulation slice'),
        (36, 29, '5. DIAGNOSE + EVALUATE', ['trade-performance-diagnosis', 'trade-robust-evaluation', 'Returns / drawdown / underwater time', 'Independent predictive lift: UNVERIFIED'], 'blue', 'IMPLEMENTED • descriptive diagnostics'),
        (5, 29, '6. DECIDE + RECORD', ['trade-portfolio-analysis', 'trade-promotion-review', 'trade-research-history', 'Handoff: verdict / failures / uncertainty'], 'green', 'IMPLEMENTED • scoped recommendations'),
    ]
    for x, y, title, lines, color, status in steps:
        for line in lines:
            if line.startswith('trade-') and line not in skills:
                raise ValueError('Unknown workflow in map: ' + line)
        m.card(x, y, 26, 15.5, title, lines, color, status, size=9.5)
    m.arrow([(31.5, 57), (35.5, 57)], 'plan', (33.5, 59.2))
    m.arrow([(62.5, 57), (66.5, 57)], 'hashes', (64.5, 59.2))
    m.arrow([(94, 56), (95.3, 56), (95.3, 37), (94, 37)])
    m.arrow([(66.5, 37), (62.5, 37)], 'ledger', (64.5, 39.2))
    m.arrow([(35.5, 37), (31.5, 37)], 'verdict', (33.5, 39.2))
    m.arrow([(16, 73.3), (16, 69.3)], 'bounded request', (25, 72))
    m.arrow([(84, 73.3), (84, 69.3)])
    m.arrow([(4.5, 37), (1.4, 37), (1.4, 71.4), (49, 71.4), (49, 73.3)],
            'all outcomes + next question', (44, 72.9))
    m.text(5, 25.1, 'Next bounded proposal: trade-candidate-evolution → a new design; continuation is not automatic.', 10.5)
    m.panel(3, 6.7, 46, 15, 'TOOL / ARTIFACT LAYER')
    m.card(4, 8, 44, 9.5, 'ENGINE APIS + LEDGERS + MLFLOW',
           ['Project definitions / audits; native engine/report interfaces', 'MLflow tracks supplied values + artifacts; it does not validate alpha'],
           'blue', 'IMPLEMENTED • saved-result tooling; SOP: operations/performance.md', size=9.5)
    m.panel(53, 6.7, 44, 15, 'NEXT-STAGE READINESS GATES')
    m.card(54, 8, 42, 9.5, 'SEPARATE OPERATIONAL EVIDENCE',
           ['PLANNED: autonomous retraining / paper orders / live execution', 'UNVERIFIED: broker connectivity / full recovery / independent alpha'],
           'orange', 'SOPs: operations/paper-connection.md + incidents.md', size=9.5)
    m.save('research-workflow.png', 'Owners: docs/research-development.md • docs/feature-engineering.md • docs/research-scoring.md • README.md')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diagram', choices=('team', 'research', 'all'), default='all')
    parser.add_argument('--output-dir', type=Path, default=OUTPUT)
    args = parser.parse_args()
    roles, skills, date = catalog()
    if args.diagram in ('team', 'all'):
        team(roles, skills, date, args.output_dir)
    if args.diagram in ('research', 'all'):
        workflow(skills, date, args.output_dir)


if __name__ == '__main__':
    main()
