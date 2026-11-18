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

    def test_pipeline_tab_appears_only_when_page_exists(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(db.main(["--dir", t]), 0)
            self.assertNotIn("Pipeline", (Path(t) / "index.html").read_text())
            (Path(t) / "stages.html").write_text("z")
            self.assertEqual(db.main(["--dir", t]), 0)
            page = (Path(t) / "index.html").read_text()
            self.assertIn("Pipeline", page)
            self.assertIn("stages.html", page)

    def test_readiness_tab_appears_only_when_page_exists(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(db.main(["--dir", t]), 0)
            self.assertNotIn("Readiness", (Path(t) / "index.html").read_text())
            (Path(t) / "stages.html").write_text("z")
            (Path(t) / "readiness.html").write_text("r")
            self.assertEqual(db.main(["--dir", t]), 0)
            page = (Path(t) / "index.html").read_text()
            self.assertIn("Readiness", page)
            self.assertIn("readiness.html", page)
            self.assertLess(page.index("Pipeline</button>"), page.index("Readiness</button>"))

    def test_analysis_tab_appears_only_when_page_exists(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(db.main(["--dir", t]), 0)
            self.assertNotIn("Analysis", (Path(t) / "index.html").read_text())
            (Path(t) / "readiness.html").write_text("r")
            (Path(t) / "analysis.html").write_text("a")
            self.assertEqual(db.main(["--dir", t]), 0)
            page = (Path(t) / "index.html").read_text()
            self.assertIn("analysis.html", page)
            self.assertLess(page.index("Readiness</button>"), page.index("Analysis</button>"))

    def test_empty_folder_still_writes_a_page(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(db.main(["--dir", t]), 0)
            self.assertTrue((Path(t) / "index.html").exists())


if __name__ == "__main__":
    unittest.main()
