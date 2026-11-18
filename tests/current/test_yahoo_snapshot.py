import hashlib
import json
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from research.data import manifest as m
from research.data import yahoo_snapshot as y

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "data" / "yahoo-chart-XLB.json"
RIGHTS = {"source": "yahoo", "use": "private offline research only",
          "redistribution": "not permitted", "ruling": "owner 2026-11-17"}


class FakeResponse:
    def __init__(self, body, status=200):
        self.body, self.status = body, status

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeOpener:
    def __init__(self, behaviour):
        self.behaviour, self.requests = behaviour, []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        symbol = request.full_url.split("/chart/")[1].split("?")[0]
        return self.behaviour(symbol)


def good(symbol):
    body = json.loads(FIXTURE.read_text())
    body["chart"]["result"][0]["meta"]["symbol"] = symbol
    return FakeResponse(json.dumps(body).encode())


NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


class YahooSnapshotTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.root = Path(self._t.name)

    def test_chart_url_epochs(self):
        url = y.chart_url("XLB", "2016-01-01", "2025-12-31")
        self.assertEqual(url, "https://query1.finance.yahoo.com/v8/finance/chart/XLB"
                              "?period1=1451606400&period2=1767225600&interval=1d&events=div%2Csplits")

    def test_parse_fixture_dates_dividend_split(self):
        frame, dividends, splits = y.parse_chart(FIXTURE.read_bytes(), "XLB")
        self.assertEqual(list(frame.index), ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"])
        self.assertEqual(list(frame.columns), ["open", "high", "low", "close", "volume"])
        self.assertEqual(dividends, [{"date": "2024-01-04", "amount": 0.25}])
        self.assertEqual(splits, [{"date": "2024-01-05", "numerator": 2, "denominator": 1, "ratio": "2:1"}])

    def test_parse_refusals(self):
        body = json.loads(FIXTURE.read_text())
        with self.assertRaises(ValueError):
            y.parse_chart(FIXTURE.read_bytes(), "XLE")
        err = {"chart": {"result": None, "error": {"code": "Not Found"}}}
        with self.assertRaises(ValueError):
            y.parse_chart(json.dumps(err).encode(), "XLB")
        r = body["chart"]["result"][0]
        r["timestamp"][1] = r["timestamp"][0]
        with self.assertRaises(ValueError):
            y.parse_chart(json.dumps(body).encode(), "XLB")

    def test_zero_volume_session_is_kept_but_nonpositive_price_is_refused(self):
        body = json.loads(FIXTURE.read_text())
        quote = body["chart"]["result"][0]["indicators"]["quote"][0]
        quote["volume"][0] = 0
        frame, _, _ = y.parse_chart(json.dumps(body).encode(), "XLB")
        self.assertEqual(frame.volume.iloc[0], 0)
        quote["low"][0] = 0
        with self.assertRaises(ValueError):
            y.parse_chart(json.dumps(body).encode(), "XLB")

    def test_fetch_with_fake_opener_writes_receipt_responses_and_manifest(self):
        opener = FakeOpener(good)
        snap = y.fetch_snapshot(["XLB", "XLE"], "2024-01-01", "2024-01-31", "snap-1", self.root,
                                opener=opener, now=NOW)
        self.assertEqual(snap, self.root / "raw" / "yahoo" / "snap-1")
        rows = json.loads((snap / "requests.json").read_text())
        self.assertEqual([r["status"] for r in rows], ["received", "received"])
        self.assertEqual([r["attempt"] for r in rows], [1, 2])
        body = (snap / "response-XLB.json").read_bytes()
        self.assertEqual(rows[0]["sha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual(rows[0]["bytes"], len(body))
        self.assertEqual(rows[0]["http_status"], 200)
        self.assertEqual(rows[0]["utc"], "2026-11-18T12:00:00Z")
        doc = m.read_manifest(self.root, "snap-1")
        self.assertEqual(doc["rights"], RIGHTS)
        self.assertEqual(doc["kind"], "raw-snapshot")
        self.assertIsNone(doc["recipe"])
        self.assertEqual([f["path"] for f in doc["files"]],
                         ["raw/yahoo/snap-1/response-XLB.json", "raw/yahoo/snap-1/response-XLE.json"])
        for req in opener.requests:
            self.assertEqual(req.get_header("User-agent"), "research-snapshot/1")

    def test_http_error_and_chart_error_leave_failed_rows_and_no_response_file(self):
        def behave(symbol):
            if symbol == "XLB":
                raise urllib.error.HTTPError("u", 429, "Too Many", {}, None)
            if symbol == "XLE":
                return FakeResponse(json.dumps({"chart": {"result": None, "error": {"code": "x"}}}).encode())
            return good(symbol)
        opener = FakeOpener(behave)
        with self.assertRaises(y.SnapshotIncomplete):
            y.fetch_snapshot(["XLB", "XLE", "XLF"], "2024-01-01", "2024-01-31", "snap-2", self.root,
                             opener=opener, now=NOW)
        snap = self.root / "raw" / "yahoo" / "snap-2"
        rows = json.loads((snap / "requests.json").read_text())
        self.assertEqual([r["status"] for r in rows], ["failed", "failed", "received"])
        self.assertEqual(rows[0]["http_status"], 429)
        self.assertTrue(rows[0]["error"])
        self.assertTrue(rows[1]["error"])
        self.assertEqual(len(opener.requests), 3)  # no retry
        self.assertFalse((snap / "response-XLB.json").exists())
        self.assertFalse((snap / "response-XLE.json").exists())
        doc = m.read_manifest(self.root, "snap-2")
        self.assertEqual([f["path"] for f in doc["files"]], ["raw/yahoo/snap-2/response-XLF.json"])

    def test_parse_failure_keeps_rejected_body_out_of_manifest(self):
        bad = json.loads(FIXTURE.read_text())
        bad["chart"]["result"][0]["indicators"]["quote"][0]["low"][0] = 0
        body = json.dumps(bad).encode()
        opener = FakeOpener(lambda s: FakeResponse(body) if s == "XLB" else good(s))
        with self.assertRaises(y.SnapshotIncomplete):
            y.fetch_snapshot(["XLB", "XLE"], "2024-01-01", "2024-01-31", "snap-4", self.root,
                             opener=opener, now=NOW)
        snap = self.root / "raw" / "yahoo" / "snap-4"
        self.assertEqual((snap / "rejected-XLB.json").read_bytes(), body)
        self.assertFalse((snap / "response-XLB.json").exists())
        rows = json.loads((snap / "requests.json").read_text())
        self.assertEqual(rows[0]["status"], "failed")
        self.assertEqual(rows[0]["rejected"], "raw/yahoo/snap-4/rejected-XLB.json")
        self.assertTrue(rows[0]["error"])
        self.assertIsNone(rows[1]["rejected"])
        doc = m.read_manifest(self.root, "snap-4")
        self.assertEqual([f["path"] for f in doc["files"]], ["raw/yahoo/snap-4/response-XLE.json"])

    def test_ids_and_symbols_are_validated_before_any_request(self):
        opener = FakeOpener(good)
        for sid in ("../x", "a/b", ".hidden", ""):
            with self.assertRaises(ValueError):
                y.fetch_snapshot(["XLB"], "2024-01-01", "2024-01-31", sid, self.root, opener=opener, now=NOW)
        for sym in ("xlb", "XLB/../x", "X LB", "", "A" * 11):
            with self.assertRaises(ValueError):
                y.fetch_snapshot([sym], "2024-01-01", "2024-01-31", "snap-5", self.root, opener=opener, now=NOW)
        self.assertEqual(opener.requests, [])
        self.assertFalse((self.root / "raw").exists())

    def test_existing_snapshot_id_is_refused(self):
        y.fetch_snapshot(["XLB"], "2024-01-01", "2024-01-31", "snap-3", self.root,
                         opener=FakeOpener(good), now=NOW)
        before = (self.root / "raw/yahoo/snap-3/response-XLB.json").read_bytes()
        opener = FakeOpener(good)
        with self.assertRaises(FileExistsError):
            y.fetch_snapshot(["XLB"], "2024-01-01", "2024-01-31", "snap-3", self.root,
                             opener=opener, now=NOW)
        self.assertEqual(opener.requests, [])
        self.assertEqual((self.root / "raw/yahoo/snap-3/response-XLB.json").read_bytes(), before)


class FetchCliTests(unittest.TestCase):
    def test_bad_ids_and_symbols_exit_one_with_one_line_error(self):
        import contextlib
        import io
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "data_cli", Path(__file__).resolve().parents[2] / "scripts" / "data.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        with tempfile.TemporaryDirectory() as tmp:
            for sid, syms in (("../x", "XLB"), ("ok-id", "X LB")):
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    rc = cli.main(["fetch-yahoo", "--symbols", syms, "--start", "2024-01-01",
                                   "--end", "2024-01-31", "--snapshot-id", sid, "--root", tmp])
                self.assertEqual(rc, 1)
                self.assertEqual(len(err.getvalue().strip().splitlines()), 1)
                self.assertTrue(err.getvalue().startswith("error: "))


if __name__ == "__main__":
    unittest.main()
