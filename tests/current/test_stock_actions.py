import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from research.data import manifest as m
from research.data import stock_actions as s
from research.data import yahoo_snapshot as y
from research.evaluation.etf_normalise import normalise

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "data"
SPLITCO = FIXTURES / "yahoo-chart-SPLITCO.json"
REVCO = FIXTURES / "yahoo-chart-REVCO.json"


class FakeResponse:
    def __init__(self, body, status=200):
        self.body, self.status = body, status

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def relabel(path, symbol, mutate=None):
    body = json.loads(path.read_text())
    body["chart"]["result"][0]["meta"]["symbol"] = symbol
    if mutate:
        mutate(body["chart"]["result"][0])
    return json.dumps(body).encode()


class SnapshotFixture(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.root = Path(self._t.name)

    def snapshot(self, bodies: dict, snapshot_id="snap", failed=()):
        """Write response files + a snapshot manifest the way fetch_snapshot would."""
        folder = self.root / "raw" / "yahoo" / snapshot_id
        folder.mkdir(parents=True)
        files, rows = [], []
        for symbol, body in bodies.items():
            (folder / f"response-{symbol}.json").write_bytes(body)
            files.append({"path": f"raw/yahoo/{snapshot_id}/response-{symbol}.json",
                          "sha256": m.sha256_file(folder / f"response-{symbol}.json")})
            rows.append({"symbol": symbol, "status": "received"})
        for symbol, error in failed:
            rows.append({"symbol": symbol, "status": "failed", "error": error})
        (folder / "requests.json").write_text(json.dumps(rows))
        doc = {"schema": m.SCHEMA, "dataset_id": snapshot_id, "kind": "raw-snapshot",
               "created_utc": "2026-11-18T12:00:00Z", "source": "yahoo", "inputs": [], "recipe": None,
               "rights": dict(y.STOCK_RIGHTS), "files": files, "notes": "n"}
        m.write_manifest(self.root, doc)
        return m.read_manifest(self.root, snapshot_id)


class StockActionsTests(SnapshotFixture):
    def test_dividends_are_unadjusted_for_later_splits(self):
        doc = self.snapshot({"SPLITCO": SPLITCO.read_bytes()})
        actions, excluded = s.build_stock_actions(doc, self.root)
        self.assertEqual(excluded, [])
        amounts = {e["ex_date"]: e["amount"] for e in actions["cash_and_in_kind"]}
        # 2024-01-03 dividend precedes the 4:1 split of 2024-01-09: Yahoo's 0.05 is 0.20 raw.
        # 2024-01-10 dividend follows the split: unchanged.
        self.assertEqual(amounts, {"2024-01-03": "0.2", "2024-01-10": "0.06"})
        self.assertEqual(actions["splits"], [
            {"id": "SPLITCO-split-2024-01-09", "symbol": "SPLITCO", "kind": "split",
             "ex_date": "2024-01-09", "ratio": "4"}])

    def test_reverse_and_fractional_splits_exclude_symbol(self):
        fractional = relabel(SPLITCO, "FRACCO", lambda r: [
            v.update(numerator=3, denominator=2, splitRatio="3:2") for v in r["events"]["splits"].values()])
        doc = self.snapshot({"SPLITCO": SPLITCO.read_bytes(), "REVCO": REVCO.read_bytes(), "FRACCO": fractional})
        actions, excluded = s.build_stock_actions(doc, self.root)
        self.assertEqual({e["symbol"] for e in excluded}, {"REVCO", "FRACCO"})
        reasons = {e["symbol"]: e["reason"] for e in excluded}
        self.assertIn("reverse", reasons["REVCO"])
        self.assertIn("non-integer", reasons["FRACCO"])
        kept = {e["symbol"] for e in actions["cash_and_in_kind"]} | {e["symbol"] for e in actions["splits"]}
        self.assertEqual(kept, {"SPLITCO"})

    def test_float_valued_split_terms_are_handled(self):
        body = relabel(SPLITCO, "FLOATCO", lambda r: [
            v.update(numerator=4.0, denominator=1.0) for v in r["events"]["splits"].values()])
        actions, excluded = s.build_stock_actions(self.snapshot({"FLOATCO": body}), self.root)
        self.assertEqual(excluded, [])
        self.assertEqual(actions["splits"][0]["ratio"], "4")
        self.assertEqual(actions["cash_and_in_kind"][0]["amount"], "0.2")

    def test_pay_date_equals_ex_date_with_label(self):
        doc = self.snapshot({"SPLITCO": SPLITCO.read_bytes()})
        actions, _ = s.build_stock_actions(doc, self.root)
        for event in actions["cash_and_in_kind"]:
            self.assertEqual(event["pay_date"], event["ex_date"])
            self.assertEqual(event["pay_date_label"], "pay_date_unknown_credited_on_ex_date")
            self.assertEqual(event["kind"], "cash")
        self.assertEqual(actions["labels"], ["pay_date_unknown_credited_on_ex_date"])

    def test_output_loads_with_etf_normalise(self):
        body = SPLITCO.read_bytes()
        doc = self.snapshot({"SPLITCO": body})
        actions, _ = s.build_stock_actions(doc, self.root)
        frame, _, _ = y.parse_chart(body, "SPLITCO")
        rows = [{"symbol": "SPLITCO", "session": day, "o": r.open, "h": r.high, "l": r.low, "c": r.close,
                 "v": r.volume} for day, r in frame.iterrows()]
        result = normalise(rows, actions, ("SPLITCO",))
        self.assertEqual([(d.ex_date, d.per_share) for d in result.data.dividends],
                         [("2024-01-03", 0.2), ("2024-01-10", 0.06)])
        self.assertEqual([(sp.effective_date, sp.ratio) for sp in result.data.splits], [("2024-01-09", 4)])

    def test_dotted_archive_symbol_maps_to_dashed_yahoo_symbol(self):
        body = relabel(SPLITCO, "BRK-B")
        doc = self.snapshot({"BRK.B": body})
        actions, excluded = s.build_stock_actions(doc, self.root)
        self.assertEqual(excluded, [])
        self.assertEqual({e["symbol"] for e in actions["cash_and_in_kind"]}, {"BRK.B"})
        self.assertEqual(actions["symbol_map"], {"BRK.B": "BRK-B"})

    def test_fetch_failures_are_listed_as_excluded(self):
        doc = self.snapshot({"SPLITCO": SPLITCO.read_bytes()}, failed=[("GONE", "HTTPError: 404")])
        _, excluded = s.build_stock_actions(doc, self.root)
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded[0]["symbol"], "GONE")
        self.assertIn("fetch failed", excluded[0]["reason"])

    def test_write_actions_is_exclusive(self):
        out = self.root / "normalized" / "a.json"
        s.write_actions(out, {"x": 1})
        with self.assertRaises(FileExistsError):
            s.write_actions(out, {"x": 2})
        self.assertEqual(json.loads(out.read_text()), {"x": 1})

    def test_symbols_file_reports_invalid_and_maps_dots(self):
        path = self.root / "cov.csv"
        path.write_text("symbol,status\nAAPL,x\nBRK.B,x\nbad symbol,x\n,x\n")
        symbols, rejected = s.read_symbols_file(path)
        self.assertEqual(symbols, ["AAPL", "BRK.B"])
        self.assertEqual([r["symbol"] for r in rejected], ["BAD SYMBOL"])


def bar_rows(symbol, closes: dict):
    return [{"symbol": symbol, "session": day, "c": str(close)} for day, close in closes.items()]


class PostWindowAdjustmentTests(SnapshotFixture):
    """Yahoo closes and dividends can be adjusted for events after the window end; Alpaca's are raw."""

    def bars(self, files: dict):
        folder = self.root / "normalized" / "bars"
        folder.mkdir(parents=True)
        for symbol, closes in files.items():
            (folder / f"{symbol}.json").write_text(json.dumps(bar_rows(symbol, closes)))
        return "normalized/bars"

    def yahoo_body(self, symbol, factor):
        """SPLITCO as Yahoo reports it: history adjusted for the in-window 4:1 split (the first five
        sessions precede it) and, by `factor`, for an event after the window."""
        def mutate(result):
            quote = result["indicators"]["quote"][0]
            for key in ("open", "high", "low", "close"):
                quote[key] = [v / factor / (4 if i < 5 else 1) for i, v in enumerate(quote[key])]
        return relabel(SPLITCO, symbol, mutate)

    def test_post_window_ratio_uses_yahoo_splits_and_median(self):
        yahoo = {"2024-01-02": 25.0, "2024-01-03": 25.5, "2024-01-09": 26.0}  # split-adjusted history
        splits = [{"date": "2024-01-09", "numerator": 4, "denominator": 1}]
        alpaca = {"2024-01-02": 100.0, "2024-01-03": 102.0, "2024-01-09": 26.0}
        self.assertAlmostEqual(s.post_window_ratio(alpaca, yahoo, splits), 1.0)

    def test_constant_25x_ratio_is_excluded_and_1_001_is_kept(self):
        frame, _, _ = y.parse_chart(SPLITCO.read_bytes(), "SPLITCO")
        traded = {day: float(row.close) for day, row in frame.iterrows()}  # the archive's raw closes
        doc = self.snapshot({"BIGCO": self.yahoo_body("BIGCO", 25), "NEARCO": self.yahoo_body("NEARCO", 1.001)})
        folder = self.bars({"BIGCO": traded, "NEARCO": traded})
        actions, excluded = s.build_stock_actions(doc, self.root, bars_dir=folder)
        self.assertEqual([e["symbol"] for e in excluded], ["BIGCO"])
        self.assertIn("post-window", excluded[0]["reason"])
        self.assertIn("25", excluded[0]["reason"])
        self.assertEqual({e["symbol"] for e in actions["splits"]}, {"NEARCO"})
        self.assertNotIn("BIGCO", {e["symbol"] for e in actions["cash_and_in_kind"]})
        info = actions["post_window_adjustment"]
        self.assertEqual([e["symbol"] for e in info["excluded"]], ["BIGCO"])
        self.assertAlmostEqual(info["excluded"][0]["median_ratio"], 25.0, places=3)
        self.assertEqual(info["checked"], 2)

    def test_cli_bars_dir_excludes_and_refuses_a_second_write(self):
        from scripts import data as data_cli
        frame, _, _ = y.parse_chart(SPLITCO.read_bytes(), "SPLITCO")
        traded = {day: float(row.close) for day, row in frame.iterrows()}
        self.snapshot({"BIGCO": self.yahoo_body("BIGCO", 25)})
        folder = self.bars({"BIGCO": traded})
        argv = ["stock-actions", "--root", str(self.root), "--snapshot", "snap", "--out", "normalized/a.json",
                "--bars-dir", folder]
        self.assertEqual(data_cli.main(argv), 0)
        doc = json.loads((self.root / "normalized" / "a.json").read_text())
        self.assertEqual(doc["post_window_adjustment"]["excluded"][0]["symbol"], "BIGCO")
        self.assertEqual(data_cli.main(argv), 1)

    def test_without_bars_dir_nothing_is_checked(self):
        doc = self.snapshot({"SPLITCO": SPLITCO.read_bytes()})
        actions, excluded = s.build_stock_actions(doc, self.root)
        self.assertEqual(excluded, [])
        self.assertNotIn("post_window_adjustment", actions)

    def test_symbol_without_bar_file_is_listed_unchecked(self):
        doc = self.snapshot({"SPLITCO": SPLITCO.read_bytes()})
        folder = self.bars({})
        actions, excluded = s.build_stock_actions(doc, self.root, bars_dir=folder)
        self.assertEqual(excluded, [])
        self.assertEqual(actions["post_window_adjustment"]["unchecked"], ["SPLITCO"])


class FetchOptionTests(SnapshotFixture):
    def opener(self, behaviour):
        self.requests = []

        def call(request, timeout=None):
            self.requests.append(request.full_url)
            return behaviour(request.full_url.split("/chart/")[1].split("?")[0])
        return call

    def test_symbol_map_requests_dashed_symbol_and_keys_files_by_archive_symbol(self):
        opener = self.opener(lambda sym: FakeResponse(relabel(SPLITCO, sym)))
        snap = y.fetch_snapshot(["BRK.B"], "2024-01-01", "2024-01-31", "s1", self.root, opener=opener,
                                symbol_map={"BRK.B": "BRK-B"}, rights=y.STOCK_RIGHTS)
        self.assertIn("/chart/BRK-B?", self.requests[0])
        self.assertTrue((snap / "response-BRK.B.json").exists())
        rows = json.loads((snap / "requests.json").read_text())
        self.assertEqual(rows[0]["request_symbol"], "BRK-B")
        doc = m.read_manifest(self.root, "s1")
        self.assertEqual(doc["rights"]["ruling"], "owner 2026-11-18")
        self.assertIn("stock", doc["rights"]["scope"])

    def test_stops_after_consecutive_http_failures(self):
        def behave(sym):
            raise urllib.error.HTTPError("u", 429, "Too Many", {}, None)
        symbols = [f"S{i}" for i in range(9)]
        with self.assertRaises(y.SnapshotIncomplete):
            y.fetch_snapshot(symbols, "2024-01-01", "2024-01-31", "s2", self.root,
                             opener=self.opener(behave), max_consecutive_http_failures=5)
        self.assertEqual(len(self.requests), 5)
        rows = json.loads((self.root / "raw" / "yahoo" / "s2" / "requests.json").read_text())
        self.assertEqual([r["status"] for r in rows[5:]], ["not_attempted"] * 4)
        doc = m.read_manifest(self.root, "s2")
        self.assertIn("stopped after 5 consecutive HTTP failures", doc["notes"])

    def test_non_http_failures_count_toward_the_stop(self):
        def behave(sym):
            raise urllib.error.URLError("connection reset") if sym != "S2" else TimeoutError("timed out")
        symbols = [f"S{i}" for i in range(9)]
        with self.assertRaises(y.SnapshotIncomplete):
            y.fetch_snapshot(symbols, "2024-01-01", "2024-01-31", "s5", self.root,
                             opener=self.opener(behave), max_consecutive_http_failures=5)
        self.assertEqual(len(self.requests), 5)
        rows = json.loads((self.root / "raw" / "yahoo" / "s5" / "requests.json").read_text())
        self.assertEqual([r["status"] for r in rows[5:]], ["not_attempted"] * 4)

    def test_success_resets_consecutive_counter(self):
        def behave(sym):
            if sym in ("S1", "S3"):
                return FakeResponse(relabel(SPLITCO, sym))
            raise urllib.error.HTTPError("u", 403, "Forbidden", {}, None)
        symbols = [f"S{i}" for i in range(6)]
        with self.assertRaises(y.SnapshotIncomplete):
            y.fetch_snapshot(symbols, "2024-01-01", "2024-01-31", "s3", self.root,
                             opener=self.opener(behave), max_consecutive_http_failures=3)
        self.assertEqual(len(self.requests), 6)

    def test_pause_is_applied_between_requests_only(self):
        pauses = []
        opener = self.opener(lambda sym: FakeResponse(relabel(SPLITCO, sym)))
        y.fetch_snapshot(["A", "B", "C"], "2024-01-01", "2024-01-31", "s4", self.root, opener=opener,
                         pause=0.3, sleep=pauses.append)
        self.assertEqual(pauses, [0.3, 0.3])


if __name__ == "__main__":
    unittest.main()
