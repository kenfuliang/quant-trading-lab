import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from research.data import manifest as m
from research.evaluation import etf_normalise as n
from research.evaluation.market_model import MarketDataError, validate

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "data"
NAMES = ("AAA", "PAR", "KID")


def load():
    rows = json.loads((FIXTURES / "etf-bars.json").read_text())
    actions = json.loads((FIXTURES / "etf-actions.json").read_text())
    return rows, actions


class NormaliseTests(unittest.TestCase):
    def test_rounds_half_even_and_counts_changes(self):
        rows, actions = load()
        result = n.normalise(rows, actions, NAMES)
        aaa = result.data.bars["AAA"]
        self.assertEqual(aaa["open"].iloc[1], 10.12)  # 10.125 tie goes to the even cent
        self.assertEqual(aaa["close"].iloc[1], 10.20)  # 10.2049 rounds down
        self.assertEqual(result.rounding["AAA"], {"open": 1, "high": 0, "low": 0, "close": 1})
        self.assertEqual(result.rounding["KID"], {"open": 0, "high": 0, "low": 0, "close": 0})
        self.assertEqual(aaa["volume"].iloc[1], 1100.0)

    def test_rounding_to_zero_raises(self):
        rows, actions = load()
        rows[0] = dict(rows[0], l="0.004")
        with self.assertRaisesRegex(MarketDataError, "AAA.*non-positive"):
            n.normalise(rows, actions, NAMES)

    def test_in_kind_becomes_cash_equivalent_with_pinned_value(self):
        rows, actions = load()
        result = n.normalise(rows, actions, NAMES)
        par = [d for d in result.data.dividends if d.instrument == "PAR"]
        self.assertEqual(len(par), 1)
        self.assertEqual((par[0].ex_date, par[0].pay_date), ("2024-01-04", "2024-01-08"))
        self.assertEqual(par[0].per_share, 10.005)  # 0.5 * KID close 20.01
        self.assertEqual(len(result.converted), 1)
        converted = result.converted[0]
        self.assertEqual(converted["id"], "PAR-2024-01-04")
        self.assertEqual(converted["per_share"], "10.005000")
        self.assertEqual(converted["label"], "in_kind_cash_equivalent")
        self.assertEqual(converted["child_symbol"], "KID")

    def test_child_not_requested_uses_full_rows(self):
        rows, actions = load()
        result = n.normalise(rows, actions, ("AAA", "PAR"))
        par = [d for d in result.data.dividends if d.instrument == "PAR"]
        self.assertEqual(par[0].per_share, 10.005)

    def test_missing_child_bar_raises(self):
        rows, actions = load()
        rows = [r for r in rows if not (r["symbol"] == "KID" and r["session"] == "2024-01-04")]
        with self.assertRaisesRegex(MarketDataError, "child KID has no bar"):
            n.normalise(rows, actions, ("AAA", "PAR"))
        with self.assertRaises(MarketDataError):
            n.normalise(rows, actions, NAMES)

    def test_unsupported_kind_raises_even_outside_window(self):
        rows, actions = load()
        actions["cash_and_in_kind"].append({"id": "AAA-odd", "symbol": "AAA", "kind": "stock",
                                            "ex_date": "2023-01-03", "pay_date": "2023-01-04"})
        with self.assertRaisesRegex(MarketDataError, "AAA-odd.*unsupported"):
            n.normalise(rows, actions, NAMES)

    def test_malformed_inputs_raise_market_data_error_with_identity(self):
        rows, actions = load()
        broken = [dict(r) for r in rows]
        del broken[3]["c"]
        with self.assertRaisesRegex(MarketDataError, "AAA 2024-01-05"):
            n.normalise(broken, actions, NAMES)
        actions["cash_and_in_kind"][0] = {"id": "AAA-bad", "symbol": "AAA", "kind": "cash",
                                          "ex_date": "2024-01-03", "pay_date": "2024-01-04"}
        with self.assertRaisesRegex(MarketDataError, "AAA-bad"):
            n.normalise(rows, actions, NAMES)
        rows2, actions2 = load()
        actions2["cash_and_in_kind"][0]["amount"] = "abc"
        with self.assertRaisesRegex(MarketDataError, "AAA-2024-01-03"):
            n.normalise(rows2, actions2, NAMES)

    def test_event_paid_after_window_is_excluded_and_listed(self):
        rows, actions = load()
        result = n.normalise(rows, actions, NAMES)
        self.assertEqual([e["id"] for e in result.excluded], ["AAA-2024-01-09"])
        self.assertEqual(result.excluded[0]["pay_date"], "2024-02-01")
        self.assertIn("pay_date", result.excluded[0]["reason"])
        aaa = [d for d in result.data.dividends if d.instrument == "AAA"]
        self.assertEqual([(d.ex_date, d.per_share) for d in aaa], [("2024-01-03", 0.10)])

    def test_result_passes_market_model_validate(self):
        rows, actions = load()
        result = n.normalise(rows, actions, NAMES)
        validate(result.data)
        self.assertEqual(len(result.data.sessions), 6)
        self.assertEqual([(s.instrument, s.effective_date, s.ratio) for s in result.data.splits],
                         [("AAA", "2024-01-05", 2)])

    def test_bar_and_session_rules(self):
        rows, actions = load()
        with self.assertRaisesRegex(MarketDataError, "duplicate"):
            n.normalise(rows + [rows[0]], actions, NAMES)
        with self.assertRaisesRegex(MarketDataError, "session lists differ"):
            n.normalise([r for r in rows if not (r["symbol"] == "KID" and r["session"] == "2024-01-09")],
                        actions, NAMES)
        with self.assertRaisesRegex(MarketDataError, "no bars"):
            n.normalise(rows, actions, NAMES + ("NOPE",))

    def test_adjusted_close_split_and_dividend_factors(self):
        rows, actions = load()
        result = n.normalise(rows, actions, NAMES)
        adjusted = n.adjusted_close(result.data)
        aaa = adjusted["AAA"]
        # dividend 0.10 ex 01-03 on previous close 10.20: factor 1 - 0.10/10.20; split 2:1 on 01-05
        self.assertAlmostEqual(aaa.iloc[0], 10.20 * (1 - 0.10 / 10.20) / 2, places=9)
        self.assertAlmostEqual(aaa.iloc[0], 5.05, places=9)
        self.assertAlmostEqual(aaa.iloc[1], 10.20 / 2, places=9)  # on/after ex-date: dividend not applied
        self.assertAlmostEqual(aaa.iloc[2], 10.30 / 2, places=9)
        self.assertAlmostEqual(aaa.iloc[3], 5.10, places=9)  # on the split date: unchanged
        self.assertEqual(list(aaa.index), list(result.data.sessions))
        kid = adjusted["KID"]
        self.assertAlmostEqual(kid.iloc[0], 20.10, places=9)


class TwoDividendTests(unittest.TestCase):
    def test_cumulative_dividend_factors(self):
        from research.evaluation.market_model import Dividend, MarketData
        import pandas as pd
        days = ("d1", "d2", "d3", "d4")
        frame = pd.DataFrame({"open": [10.0] * 4, "high": [10.0] * 4, "low": [10.0] * 4,
                              "close": [10.0, 8.0, 8.0, 5.0], "volume": [1.0] * 4},
                             index=pd.Index(days, name="date"))
        data = MarketData(days, {"X": frame},
                          (Dividend("X", "d2", "d2", 1.0), Dividend("X", "d4", "d4", 0.5)), ())
        adjusted = n.adjusted_close(data)["X"]
        f2, f4 = 1 - 1.0 / 10.0, 1 - 0.5 / 8.0
        self.assertAlmostEqual(adjusted.iloc[0], 10.0 * f2 * f4, places=9)
        self.assertAlmostEqual(adjusted.iloc[1], 8.0 * f4, places=9)
        self.assertAlmostEqual(adjusted.iloc[2], 8.0 * f4, places=9)
        self.assertAlmostEqual(adjusted.iloc[3], 5.0, places=9)


def load_cli():
    spec = importlib.util.spec_from_file_location(
        "data_cli", Path(__file__).resolve().parents[2] / "scripts" / "data.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    return cli


class NormaliseCommandTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.root = Path(self._t.name)
        self.cli = load_cli()

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = self.cli.main(list(argv))
        return rc, out.getvalue(), err.getvalue()

    def test_normalise_command_writes_manifest_and_blocks_on_absent_input(self):
        bars = self.root / "normalized" / "src-v1.json"
        actions = self.root / "normalized" / "src-v1-actions.json"
        args = ["normalise", "--bars", str(bars), "--actions", str(actions),
                "--dataset-id", "src-n1", "--root", str(self.root)]
        rc, _, err = self.run_cli(*args)
        self.assertEqual(rc, 2)
        self.assertTrue(err.startswith("blocked: data absent: "))
        self.assertFalse((self.root / "manifests" / "src-n1.json").exists())

        bars.parent.mkdir(parents=True)
        shutil.copy(FIXTURES / "etf-bars.json", bars)
        shutil.copy(FIXTURES / "etf-actions.json", actions)
        source = {"schema": "sector-etf-acquisition-v1", "dataset_id": "src-v1", "feed": "sip",
                  "redistribution": "not_qualified", "personal_use_review": "terms retained"}
        (self.root / "manifests").mkdir()
        (self.root / "manifests" / "src-v1.json").write_text(json.dumps(source))
        rc, out, err = self.run_cli(*args)
        self.assertEqual(rc, 0, err)
        doc = m.read_manifest(self.root, "src-n1")
        self.assertEqual(doc["kind"], "normalised")
        self.assertEqual(doc["recipe"], "etf-normalise/v1")
        self.assertEqual([e["path"] for e in doc["inputs"]],
                         ["normalized/src-v1.json", "normalized/src-v1-actions.json"])
        self.assertEqual(doc["rights"]["redistribution"], "not_qualified")
        self.assertEqual(doc["rights"]["personal_use_review"], "terms retained")
        self.assertEqual(doc["files"], [])
        self.assertIn("rounding changed 2 values", out)
        self.assertIn("converted 1", out)
        self.assertIn("excluded 1", out)
        self.assertIn("PAR-2024-01-04", out)

        rc, _, err = self.run_cli(*args)  # exclusive create: second run refuses
        self.assertEqual(rc, 1)
        self.assertTrue(err.startswith("error: "))

    def test_inputs_outside_data_root_are_refused(self):
        rc, _, err = self.run_cli("normalise", "--bars", str(FIXTURES / "etf-bars.json"),
                                  "--actions", str(FIXTURES / "etf-actions.json"),
                                  "--dataset-id", "x-n1", "--root", str(self.root))
        self.assertEqual(rc, 1)
        self.assertTrue(err.startswith("error: "))


if __name__ == "__main__":
    unittest.main()
