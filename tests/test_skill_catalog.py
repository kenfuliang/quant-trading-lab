import tempfile
import unittest
from pathlib import Path

from scripts.check_docs import check_skill_catalog


class SkillCatalogTests(unittest.TestCase):
    def fixture(self, root, entries, installed):
        (root / "docs").mkdir()
        (root / "docs/skills.md").write_text("\n".join(
            f"| [{name}](../.agents/skills/{name}/SKILL.md) | Description |"
            for name in entries
        ))
        for folder, identity in installed.items():
            path = root / ".agents/skills" / folder / "SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"---\nname: {identity}\ndescription: Test skill\n---\n")

    def test_matching_inventory_allows_planned_names_in_prose(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, ["ask-ml"], {"ask-ml": "ask-ml"})
            with (root / "docs/skills.md").open("a") as catalog:
                catalog.write("\nPlanned: ask-options\n")
            self.assertEqual(check_skill_catalog(root), [])

    def test_unlisted_installed_skill_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, [], {"new-role": "new-role"})
            self.assertIn("unlisted: new-role", "\n".join(check_skill_catalog(root)))

    def test_missing_and_duplicate_catalog_entries_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, ["missing", "missing"], {})
            errors = "\n".join(check_skill_catalog(root))
            self.assertIn("duplicate entry missing", errors)
            self.assertIn("not installed: missing", errors)

    def test_frontmatter_identity_must_match_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, ["ask-ml"], {"ask-ml": "ask-ml-infra"})
            self.assertIn("name mismatch: ask-ml", "\n".join(check_skill_catalog(root)))
