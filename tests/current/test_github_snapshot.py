import json
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from research.data import github_snapshot as g
from research.data import manifest as m
from research.data.yahoo_snapshot import SnapshotIncomplete

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "github"
NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
LICENSE_TEXT = b"MIT License\n\nCopyright (c) 2019 someone\n"


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
    def __init__(self, routes):
        self.routes, self.requests = routes, []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        route = self.routes.get(request.full_url)
        if route is None:
            raise urllib.error.HTTPError(request.full_url, 404, "not found", {}, None)
        if isinstance(route, int):
            raise urllib.error.HTTPError(request.full_url, route, "refused", {}, None)
        return FakeResponse(route)


class GithubSnapshotTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.root = Path(self._t.name)

    def test_github_fetch_receipts_and_host_allowlist(self):
        opener = FakeOpener({"https://api.github.com/repos/a/b/contents": b'[{"name": "x"}]',
                             "https://raw.githubusercontent.com/a/b/main/LICENSE": LICENSE_TEXT})
        urls = {"b-contents.json": "https://api.github.com/repos/a/b/contents",
                "b-LICENSE": "https://raw.githubusercontent.com/a/b/main/LICENSE"}
        folder = g.fetch_urls(urls, "gh1", self.root, opener=opener, now=NOW)
        self.assertEqual(folder, self.root / "raw" / "github" / "gh1")
        self.assertEqual([r.get_header("User-agent") for r in opener.requests], ["research-snapshot/1"] * 2)
        rows = json.loads((folder / "requests.json").read_text())
        self.assertEqual([r["status"] for r in rows], ["received", "received"])
        manifest = m.read_manifest(self.root, "gh1")
        self.assertEqual(manifest["kind"], "raw-snapshot")
        self.assertEqual(manifest["rights"]["use"], "private offline research")
        self.assertEqual(manifest["rights"]["ruling"], "owner 2026-11-18 (membership sources)")
        lic = manifest["rights"]["licences"]["b-LICENSE"]
        self.assertEqual(lic["first_line"], "MIT License")
        self.assertEqual(lic["sha256"], m.sha256_file(folder / "b-LICENSE"))
        with self.assertRaises(FileExistsError):  # existing snapshot id refused
            g.fetch_urls(urls, "gh1", self.root, opener=opener, now=NOW)
        # non-GitHub host or scheme: refused before any request, nothing written
        for bad in ("https://query1.finance.yahoo.com/x", "http://api.github.com/x",
                    "https://api.github.com.evil.test/x", "https://evil.test/api.github.com"):
            guard = FakeOpener({})
            with self.assertRaises(ValueError):
                g.fetch_urls({"ok.json": "https://api.github.com/x", "bad.json": bad}, "gh2", self.root,
                             opener=guard, now=NOW)
            self.assertEqual(guard.requests, [])
            self.assertFalse((self.root / "raw" / "github" / "gh2").exists())

    def test_rate_limit_stops_and_is_recorded_blocked(self):
        opener = FakeOpener({"https://api.github.com/a": 403})
        urls = {"a.json": "https://api.github.com/a", "b.json": "https://api.github.com/b"}
        with self.assertRaises(SnapshotIncomplete):
            g.fetch_urls(urls, "gh3", self.root, opener=opener, now=NOW)
        self.assertEqual(len(opener.requests), 1)
        rows = json.loads((self.root / "raw" / "github" / "gh3" / "requests.json").read_text())
        self.assertEqual([r["status"] for r in rows], ["failed", "not_attempted"])
        self.assertEqual(rows[0]["http_status"], 403)
        self.assertIn("a.json", m.read_manifest(self.root, "gh3")["notes"])

    def test_membership_sources_discovery_via_contents_api(self):
        routes = {u: (FIXTURES / f).read_bytes() for u, f in {
            "https://api.github.com/repos/fja05680/sp500/contents": "contents-fja05680.json",
            "https://api.github.com/repos/hanshof/sp500_constituents/contents": "contents-hanshof.json",
            "https://api.github.com/search/repositories?q=index-constitution": "search-index-constitution.json",
        }.items()}
        routes["https://api.github.com/repos/other/sp500-index-constitution/contents"] = b"[]"
        routes["https://raw.githubusercontent.com/fja05680/sp500/master/LICENSE"] = LICENSE_TEXT
        csv_url = ("https://raw.githubusercontent.com/fja05680/sp500/master/S%26P%20500%20Historical"
                   "%20Components%20%26%20Changes%20(Updated).csv")
        routes[csv_url] = b"date,tickers\n"
        routes["https://raw.githubusercontent.com/hanshof/sp500_constituents/main/sp500_constituents.csv"] = b"x\n"
        routes["https://raw.githubusercontent.com/hanshof/sp500_constituents/main/LICENSE"] = LICENSE_TEXT
        opener = FakeOpener(routes)
        g.fetch_urls(g.membership_sources(), "gh4", self.root, opener=opener, now=NOW,
                     expand=g.expand_membership)
        names = {r["name"] for r in json.loads((self.root / "raw/github/gh4/requests.json").read_text())}
        self.assertTrue({"fja05680-components.csv", "fja05680-LICENSE", "hanshof-constituents.csv",
                         "index-constitution-contents.json"} <= names)
        self.assertLess(len(opener.requests), 15)
        urls = [r.full_url for r in opener.requests]
        self.assertIn(csv_url, urls)  # the '(Updated)' file wins over dated and undated ones (the plain file ends 2019-01-11)
        self.assertTrue(all(u.startswith(("https://api.github.com/", "https://raw.githubusercontent.com/"))
                            for u in urls))
        # the index-constitution search result without S&P 500 wording is not used
        self.assertFalse(any("index-constitution-notes" in u for u in urls))


if __name__ == "__main__":
    unittest.main()
