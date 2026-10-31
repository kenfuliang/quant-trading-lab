#!/usr/bin/env python3
"""Render the canonical catalog as a standalone PNG; no services or data access."""
from pathlib import Path
import re
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "docs/skills.md"
OUTPUT = ROOT / "docs/diagrams/team-skills.png"


def entries(section):
    return re.findall(
        r"^\| \[([^\]]+)\]\(\.\./\.agents/skills/[^/]+/SKILL\.md\) \| ([^|]+)\|",
        section, re.M,
    )


def main():
    content = CATALOG.read_text()
    sections = re.split(r"^## ", content, flags=re.M)
    sections = {part.split("\n", 1)[0]: part for part in sections[1:]}
    roles = entries(sections["Available advisory skills"])
    platform = entries(sections["Available project skills"])
    research = entries(sections["Available research workflows"])
    directors = [role for role in roles if role[0] == "/ask-director"]
    specialists = [role for role in roles if role not in directors]
    if len(directors) != 1 or len(specialists) > 8:
        raise ValueError("Review the diagram layout for the changed team hierarchy.")

    fig, ax = plt.subplots(figsize=(18, 14), dpi=160)
    fig.patch.set_facecolor("#f4f6f8")
    ax.set(xlim=(0, 100), ylim=(0, 100))
    ax.axis("off")
    navy, muted = "#142d43", "#516476"

    def text(x, y, value, size=11, color=navy, **kwargs):
        ax.text(x, y, value, fontsize=size, color=color, va="top", **kwargs)

    def box(x, y, width, height, fill="white", edge="#d4dfe7"):
        ax.add_patch(FancyBboxPatch(
            (x, y), width, height, boxstyle="round,pad=0.5,rounding_size=1",
            facecolor=fill, edgecolor=edge, linewidth=1,
        ))

    text(4, 98, "QUANT RESEARCH LAB", size=24, weight="bold")
    text(4, 93.5, f"{len(roles)} advisory roles  /  {len(platform) + len(research)} shared workflow skills", size=14)
    text(96, 97, "Team structure + skill map", size=12, ha="right", color=muted)
    box(28, 84, 44, 6, fill="#142d43", edge="#142d43")
    text(50, 88.3, "YOU  ·  objectives, constraints and authorization", size=12, color="white", ha="center")
    ax.annotate("", xy=(50, 81.7), xytext=(50, 83.5), arrowprops=dict(arrowstyle="->", color=muted))
    box(28, 75, 44, 6, fill="#dcebf4", edge="#a8c6da")
    text(50, 79.5, directors[0][0], size=13, weight="bold", ha="center")
    text(50, 77.1, "Priorities, evidence and coordination", size=10, ha="center")

    columns = 4 if len(specialists) > 6 else 3
    card_width = 21 if columns == 4 else 28
    stride = 23.5 if columns == 4 else 32
    for column in range(columns):
        center = 4 + card_width / 2 + column * stride
        ax.annotate("", xy=(center, 70.7), xytext=(50, 74.5), arrowprops=dict(arrowstyle="->", color="#94abbc", lw=1))
    # A second branch runs through the left gutter to the lower advisory row.
    last_center = 4 + card_width / 2 + (columns - 1) * stride
    ax.plot([50, 2, 2, last_center], [74.5, 74.5, 56.7, 56.7], color="#94abbc", lw=1)
    for column in range(len(specialists) - columns):
        center = 4 + card_width / 2 + column * stride
        ax.annotate("", xy=(center, 55.7), xytext=(center, 56.7), arrowprops=dict(arrowstyle="->", color="#94abbc", lw=1))
    for i, (name, question) in enumerate(specialists):
        column, row = i % columns, i // columns
        x, y = 4 + column * stride, 58 - row * 15
        box(x, y, card_width, 12)
        text(x + 1.6, y + 10.7, name, size=13, weight="bold")
        text(x + 1.6, y + 7.3, textwrap.fill(question.strip(), width=28 if columns == 4 else 37), size=10, linespacing=1.35, color=muted)
    text(4, 40.8, "Roles collaborate and cross-review; workflows below are shared, not exclusive assignments.", size=11, color=muted)

    box(4, 8, 37, 28)
    box(44, 8, 52, 28)
    text(6, 34.2, "PROJECT WORKFLOWS", size=13, weight="bold")
    text(46, 34.2, "BOUNDED RESEARCH WORKFLOWS", size=13, weight="bold")
    platform_spacing = min(4.1, 18.5 / max(1, len(platform) - 1))
    for i, (name, _) in enumerate(platform):
        text(6, 29.7 - i * platform_spacing, name, size=11.5, family="monospace")
    research_spacing = min(2.05, 18.5 / max(1, len(research) - 1))
    for i, (name, _) in enumerate(research):
        text(46, 29.7 - i * research_spacing, name, size=10.8, family="monospace")
    text(4, 5.7, "Instruction availability is separate from tested runtime or broker readiness. Roles are invoked on demand.", size=11, weight="bold")
    text(4, 3, "Source: docs/skills.md  ·  Role contracts: docs/advisory-team.md  ·  SOP owners: docs/README.md", size=10, color=muted)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=.3)
    plt.close(fig)
    print(OUTPUT)


if __name__ == "__main__":
    main()
