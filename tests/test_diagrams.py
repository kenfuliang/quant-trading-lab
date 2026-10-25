import subprocess
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image
import matplotlib.pyplot as plt

from scripts.render_team_skills import catalog, team

ROOT = Path(__file__).resolve().parents[1]


class DiagramExportsTests(unittest.TestCase):
    def test_selected_views_write_valid_pngs_only_to_requested_directory(self):
        originals = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / 'docs/diagrams').glob('*.png')}
        for view, filename in [('team', 'team-skills.png'), ('research', 'research-workflow.png')]:
            with self.subTest(view=view), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / 'exports'
                result = subprocess.run(
                    [sys.executable, str(ROOT / 'scripts/render_team_skills.py'),
                     '--diagram', view, '--output-dir', str(output)],
                    cwd=ROOT, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual([p.name for p in output.iterdir()], [filename])
                self.assertEqual({p: hashlib.sha256(p.read_bytes()).hexdigest() for p in originals}, originals)
                with Image.open(output / filename) as image:
                    self.assertEqual(image.format, 'PNG')
                    self.assertGreaterEqual(image.width, 2000)
                    self.assertGreaterEqual(image.height, 1500)
                    image.verify()

    def test_uncataloged_workflow_cannot_silently_disappear_from_map(self):
        roles, skills, date = catalog()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'exports'
            try:
                with self.assertRaisesRegex(ValueError, 'Every cataloged workflow'):
                    team(roles, [*skills, 'unmapped-new-workflow'], date, output)
                self.assertFalse(output.exists())
            finally:
                plt.close('all')
