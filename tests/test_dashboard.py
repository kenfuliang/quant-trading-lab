import tempfile
import unittest
from pathlib import Path

from scripts import dashboard as db


class DashboardTests(unittest.TestCase):
    def test_only_existing_pages_get_tabs_and_labels_are_escaped(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "holdings.html").write_text("x")
            (Path(t) / "target.html").write_text("y")
            self.assertEqual(db.main(["--dir", t]), 0)
            page = (Path(t) / "index.html").read_text()
            self.assertIn("Holdings", page)
            self.assertIn("Target log", page)
            self.assertNotIn("Progress</button>", page)
            self.assertEqual(page.count("<iframe"), 1)

    def test_empty_folder_still_writes_a_page(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(db.main(["--dir", t]), 0)
            self.assertTrue((Path(t) / "index.html").exists())


if __name__ == "__main__":
    unittest.main()
