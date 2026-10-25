#!/usr/bin/env python3
"""Check maintained documentation metadata and local Markdown link targets."""
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def check_skill_catalog(root):
    """Check discovery entries against installed instructions, without dependencies."""
    catalog = (root / "docs/skills.md").read_text()
    entries = re.findall(
        r"^\| \[[^\]]+\]\(\.\./\.agents/skills/([^/]+)/SKILL\.md\)",
        catalog, re.M,
    )
    installed = {p.parent.name: p for p in (root / ".agents/skills").glob("*/SKILL.md")}
    errors = []
    for name in sorted(set(entries)):
        if entries.count(name) != 1:
            errors.append(f"skills catalog: duplicate entry {name}")
    for name in sorted(set(installed) - set(entries)):
        errors.append(f"skills catalog: installed skill is unlisted: {name}")
    for name in sorted(set(entries) - set(installed)):
        errors.append(f"skills catalog: listed skill is not installed: {name}")
    for name, path in sorted(installed.items()):
        frontmatter = re.match(r"\A---\n(.*?)\n---\n", path.read_text(), re.S)
        identity = re.search(r"^name:\s*([^\n]+)", frontmatter[1], re.M) if frontmatter else None
        if not identity or identity[1].strip() != name:
            errors.append(f"skills catalog: folder/frontmatter name mismatch: {name}")
    return errors


def main():
    documents = [ROOT / "README.md", ROOT / "AGENTS.md"]
    documents += sorted((ROOT / "docs").rglob("*.md"))
    documents += sorted((ROOT / ".agents/skills").rglob("SKILL.md"))
    errors = check_skill_catalog(ROOT)
    for path in documents:
        content = path.read_text()
        if path.is_relative_to(ROOT / "docs"):
            frontmatter = re.match(r"\A---\n(.*?)\n---\n", content, re.S)
            for field in ("status", "updated", "owner"):
                if not frontmatter or not re.search(rf"^{field}:\s*\S+", frontmatter[1], re.M):
                    errors.append(f"{path.relative_to(ROOT)}: missing {field} frontmatter")
        # Ignore examples inside fenced code blocks. External URLs and anchor-only
        # links are outside this check; it validates filesystem targets, not anchors.
        prose = re.sub(r"^```.*?^```[^\n]*", "", content, flags=re.M | re.S)
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", prose):
            target = target.strip().strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            linked = path.parent / unquote(parsed.path)
            if not linked.exists():
                errors.append(f"{path.relative_to(ROOT)}: missing target {target}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Documentation check passed: {len(documents)} files; local targets, docs metadata and skill catalog parity.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
