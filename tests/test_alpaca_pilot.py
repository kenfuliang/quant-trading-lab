import copy
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from research import alpaca_pilot as pilot


def page():
    return {"bars": {s: [{"t": "2016-01-04T05:00:00Z", "o": "100.1234",
            "h": "102.25", "l": "99.5", "c": "101.1", "v": "12345.25"}]
            for s in pilot.SYMBOLS}, "next_page_token": None}


ONE_DAY = (("2016-01-04", "2016-01-04"),)


def response(data):
    result = io.BytesIO(data)
    result.status = 200
    result.headers = {"Content-Type": "application/json"}
    return result


class PilotValidationTests(unittest.TestCase):
    def test_complete_coverage_and_conservative_availability(self):
        rows = pilot.validate_pages([page()], ONE_DAY)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["ts_event"], 1451970000000000000)  # Jan 5, 05:00 UTC
        self.assertEqual(rows[0]["o"], "100.1234")
        self.assertEqual(rows[0]["v"], "12345.25")

    def test_incomplete_duplicate_and_unexpected_data_rejected(self):
        missing = page()
        del missing["bars"]["JPM"]
        extra = page()
        extra["bars"]["GOOG"] = []
        wrong_day = page()
        wrong_day["bars"]["AAPL"][0]["t"] = "2016-01-01T05:00:00Z"
        for pages in ([missing], [page(), page()], [extra], [wrong_day], [{"message": "forbidden"}]):
            with self.subTest(pages=pages), self.assertRaises(ValueError):
                pilot.validate_pages(pages, ONE_DAY)

    def test_price_timestamp_and_precision_corruption_rejected(self):
        for key, value in [("o", "NaN"), ("l", "103"), ("v", "-1"), ("o", True),
                           ("o", "1.0000000001"), ("t", "2016-01-04T00:00:00"),
                           ("t", "2016-01-04T06:00:00Z")]:
            payload = page()
            payload["bars"]["AAPL"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                pilot.validate_pages([payload], ONE_DAY)

    def test_credentials_not_sourced_and_permission_check(self):
        with tempfile.TemporaryDirectory() as t, patch.dict(os.environ, {}, clear=True):
            p = Path(t) / "credentials"
            p.write_text('APCA_API_KEY_ID=testkey\nAPCA_API_SECRET_KEY=testsecret\nIGNORED=$(touch never)\n')
            p.chmod(0o600)
            self.assertEqual(pilot.credentials(p), ("testkey", "testsecret"))
            self.assertFalse((Path(t) / "never").exists())
            p.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "owner-only"):
                pilot.credentials(p)
            with self.assertRaisesRegex(ValueError, "Missing"):
                pilot.credentials(Path(t) / "missing")


class NativeCatalogTests(unittest.TestCase):
    def test_exact_round_trip_repeat_and_separate_restore(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t) / "proof"
            result = pilot.synthetic_proof(root)
            self.assertEqual(result["data_kind"], "synthetic_not_alpaca")
            self.assertEqual(result["first"]["bars"], 4)
            self.assertEqual(result["repeat"]["status"], "identical_read_only")
            self.assertEqual(result["restore"]["status"], "identical_read_only")
            before = {str(p.relative_to(root / "catalog")): pilot.digest(p)
                      for p in (root / "catalog").rglob("*") if p.is_file()}
            rows = json.loads((root / "synthetic-normalized.json").read_text())
            changed = copy.deepcopy(rows)
            changed[0]["c"] = "101.2"
            with self.assertRaisesRegex(ValueError, "differs"):
                pilot.catalog_import(changed, root / "catalog")
            after = {str(p.relative_to(root / "catalog")): pilot.digest(p)
                     for p in (root / "catalog").rglob("*") if p.is_file()}
            self.assertEqual(before, after)
            (root / "restored-catalog").rename(root / "offline-restore")
            self.assertEqual(pilot.catalog_import(rows, root / "offline-restore")["bars"], 4)


class TransportTests(unittest.TestCase):
    def test_fixed_endpoint_raw_bytes_and_page_tokens(self):
        payload = page()
        payload["next_page_token"] = "next"
        responses = [json.dumps(payload).encode(), json.dumps(page()).encode(), json.dumps(page()).encode()]
        seen = []

        def open_response(req, timeout):
            seen.append(req)
            return response(responses[len(seen) - 1])

        with tempfile.TemporaryDirectory() as t, patch.object(pilot.urllib.request, "build_opener") as build, patch.object(pilot.time, "sleep"):
            build.return_value.open.side_effect = open_response
            pages, receipt = pilot.acquire(Path(t) / "raw", ("private-key", "private-secret"))
            self.assertEqual(receipt["attempts"], 3)
            self.assertEqual(len(pages), 3)
            self.assertTrue(all(r.full_url.startswith(pilot.ENDPOINT + "?") for r in seen))
            self.assertIn("page_token=next", seen[1].full_url)
            self.assertIn("feed=sip", seen[0].full_url)
            saved = (Path(t) / "raw" / "requests.json").read_text()
            self.assertNotIn("private-key", saved)
            self.assertNotIn("private-secret", saved)
            self.assertEqual((Path(t) / "raw" / "response-01.json").read_bytes(), responses[0])

    def test_http_failure_no_retry_or_secret_logging(self):
        error = pilot.urllib.error.HTTPError(pilot.ENDPOINT, 403, "private-secret", {}, None)
        with tempfile.TemporaryDirectory() as t, patch.object(pilot.urllib.request, "build_opener") as build:
            build.return_value.open.side_effect = error
            with self.assertRaises(ValueError) as caught:
                pilot.acquire(Path(t) / "raw", ("private-key", "private-secret"))
            self.assertNotIn("private-secret", str(caught.exception))
            receipt = (Path(t) / "raw" / "requests.json").read_text()
            self.assertNotIn("private-secret", receipt)
            self.assertEqual(json.loads(receipt)[0]["http_status"], 403)
            self.assertEqual(build.return_value.open.call_count, 1)

    def test_budget_stops_before_request_and_repeated_token_stops(self):
        with tempfile.TemporaryDirectory() as t, patch.object(pilot.urllib.request, "build_opener") as build:
            with self.assertRaisesRegex(ValueError, "budget"):
                pilot.acquire(Path(t) / "raw", ("k", "s"), request_limit=0)
            build.return_value.open.assert_not_called()
        payload = page()
        payload["next_page_token"] = "again"
        with tempfile.TemporaryDirectory() as t, patch.object(pilot.urllib.request, "build_opener") as build, patch.object(pilot.time, "sleep"):
            build.return_value.open.side_effect = lambda *a, **kw: response(json.dumps(payload).encode())
            with self.assertRaisesRegex(ValueError, "pagination"):
                pilot.acquire(Path(t) / "raw", ("k", "s"))
            self.assertEqual(build.return_value.open.call_count, 2)

    def test_redirect_refused(self):
        with self.assertRaisesRegex(ValueError, "Redirect refused"):
            pilot.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://other.example")


if __name__ == "__main__":
    unittest.main()
