import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from scripts import profile_strategy as ps


def path_rows(n=300, seed=1, drift=0.001):
    rng = np.random.default_rng(seed)
    nav = 10000 * np.cumprod(np.r_[1, 1 + drift + rng.normal(0, 0.01, n)])
    days = pd.bdate_range("2020-01-02", periods=n + 1)
    return [{"session": d.strftime("%Y-%m-%d"), "nav_usd": float(v)} for d, v in zip(days, nav)]


class ProfileTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def write(self, name, rows):
        path = self.root / name
        path.write_text(json.dumps(rows))
        return path

    def test_analysis_matches_the_path(self):
        rows = path_rows()
        series = ps.load_path(self.write("a.json", rows))
        result = ps.analyze(series)
        self.assertAlmostEqual(result["summary"]["max_drawdown"], (series / series.cummax() - 1).min())
        self.assertEqual(result["capital"], 10000.0)
        self.assertGreater(len(result["episodes"]), 0)

    def test_page_contains_every_series_and_the_caveats(self):
        a = self.write("a.json", path_rows(seed=1))
        b = self.write("b.json", path_rows(seed=2, drift=0.0))
        out = self.root / "p.html"
        self.assertEqual(ps.main(["--series", f"First={a}", "--series", f"Second <x>={b}", "--out", str(out)]), 0)
        page = out.read_text()
        for text in ("First", "Second &lt;x&gt;", "viewed development history", "Drawdown from the running peak", "Calendar years"):
            self.assertIn(text, page)
        self.assertNotIn("<x>", page)
        self.assertEqual(page.count("<svg"), 4)

    def test_benchmark_is_rebased_to_the_anchor(self):
        rows = path_rows()
        series = ps.load_path(self.write("a.json", rows))
        csv = self.root / "b.csv"
        pd.DataFrame({"date": series.index, "equity": np.linspace(50000, 90000, len(series))}).to_csv(csv, index=False)
        bench = ps.load_benchmark(csv, series.index[0], series.index[-1], 10000.0)
        self.assertEqual(bench.iloc[0], 10000.0)
        self.assertAlmostEqual(bench.iloc[-1], 18000.0)

    def test_bad_series_argument_is_rejected(self):
        with self.assertRaises(SystemExit):
            ps.main(["--series", "no-equals-sign"])


if __name__ == "__main__":
    unittest.main()
