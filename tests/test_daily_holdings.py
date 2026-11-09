import json
import tempfile
import unittest
from pathlib import Path

from scripts import daily_holdings as dh

SESSIONS = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]


def close_path():
    return [{"session": s, "nav_usd": 10000.0 + i * 100, "export_sample_utc": f"2024-01-{3 + i:02d}T05:00:00+00:00",
             "mapping": "x"} for i, s in enumerate(SESSIONS)]


def order(oid, symbol, qty, created, filled, price=10.0, status=3, tag="funded-v1:buy"):
    return {"id": oid, "status": status, "symbol": {"value": symbol}, "quantity": qty, "price": price,
            "time": f"{created}T21:00:00Z", "lastFillTime": f"{filled}T21:00:00Z", "tag": tag}


def export(orders, trades=()):
    base = {}
    for r in close_path():
        base[int(dh._epoch(r["export_sample_utc"]))] = 0.5
    return {"charts": {"Exposure": {"series": {"Equity - Long Ratio": {"values": [[t, v] for t, v in base.items()]}}},
                       "Portfolio Turnover": {"series": {"Portfolio Turnover": {"values": [[t, 0.1] for t in base]}}}},
            "orders": {str(o["id"]): o for o in orders}, "totalPerformance": {"closedTrades": list(trades)}}


class DailyHoldingsTests(unittest.TestCase):
    def test_positions_are_the_cumulative_fills_by_fill_date(self):
        data = dh.build_dataset("S", close_path(), export([
            order(1, "TQQQ", 10, "2024-01-02", "2024-01-03"), order(2, "SQQQ", 5, "2024-01-03", "2024-01-04"),
            order(3, "TQQQ", -10, "2024-01-04", "2024-01-05", tag="funded-v1:reduce")]))
        self.assertEqual(dh.positions_on(data, "2024-01-02"), {})
        self.assertEqual(dh.positions_on(data, "2024-01-03")["TQQQ"][0], 10.0)
        self.assertEqual(sorted(dh.positions_on(data, "2024-01-04")), ["SQQQ", "TQQQ"])
        self.assertEqual(list(dh.positions_on(data, "2024-01-05")), ["SQQQ"])

    def test_decisions_are_keyed_by_created_date_and_fills_by_fill_date(self):
        data = dh.build_dataset("S", close_path(), export([order(1, "TQQQ", 10, "2024-01-02", "2024-01-03")]))
        self.assertIn("2024-01-02", data["decided"])
        self.assertIn("2024-01-03", data["orders"])
        self.assertNotIn("2024-01-03", data["decided"])

    def test_unfilled_and_off_calendar_orders_are_ignored_or_counted(self):
        data = dh.build_dataset("S", close_path(), export([
            order(1, "TQQQ", 10, "2024-01-02", "2024-01-03", status=1), order(2, "TQQQ", 10, "2024-01-02", "2024-02-01")]))
        self.assertEqual(data["pos"], {})
        self.assertEqual(data["unmatched_orders"], 1)

    def test_exposure_and_turnover_align_to_sessions(self):
        data = dh.build_dataset("S", close_path(), export([]))
        self.assertEqual(data["expo"], [0.5] * 4)
        self.assertEqual(data["turn"], [0.1] * 4)

    def test_closed_trades_are_keyed_by_exit_date(self):
        trade = {"symbols": [{"value": "TQQQ"}], "entryTime": "2024-01-03T21:00:00Z", "exitTime": "2024-01-05T21:00:00Z",
                 "quantity": 10, "entryPrice": 10.0, "exitPrice": 11.0, "profitLoss": 10.0, "totalFees": 1.0}
        data = dh.build_dataset("S", close_path(), export([], [trade]))
        self.assertEqual(data["trades"]["2024-01-05"][0][5], 10.0)

    def test_page_embeds_data_safely_and_cli_runs(self):
        with tempfile.TemporaryDirectory() as t:
            cp, ex, out = Path(t) / "c.json", Path(t) / "e.json", Path(t) / "h.html"
            cp.write_text(json.dumps(close_path()))
            ex.write_text(json.dumps(export([order(1, "</script>", 1, "2024-01-02", "2024-01-03")])))
            self.assertEqual(dh.main(["--strategy", f"S={cp},{ex}", "--out", str(out)]), 0)
            page = out.read_text()
            self.assertIn("Per-day holdings", page)
            self.assertEqual(page.count("</script>"), 1)
            self.assertIn("not reconciled", page)

    def test_bad_argument_is_rejected(self):
        with self.assertRaises(SystemExit):
            dh.main(["--strategy", "missing-parts"])


if __name__ == "__main__":
    unittest.main()
