import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SkillDiscoveryTests(unittest.TestCase):
    def test_claude_code_path_resolves_to_canonical_skills(self):
        link = ROOT / ".claude/skills"
        self.assertEqual(link.resolve(), (ROOT / ".agents/skills").resolve())
        self.assertTrue((link / "trade-project/SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
