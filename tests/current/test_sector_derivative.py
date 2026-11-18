import json
import tempfile
import unittest
from pathlib import Path

from research.evaluation.market_model import Dividend, MarketDataError, Split
from research.evaluation.sector_derivative import load_sector_derivative

SESSIONS = ("2025-12-03", "2025-12-04", "2025-12-05")


def _bar(symbol, session, o, h, l, c, v):
    # Recorded columns of data/normalized/alpaca-sector-etfs-2016-2025-v1.json (strings).
    return {
        "symbol": symbol, "session": session, "source_timestamp": f"{session}T05:00:00Z",
        "ts_event": 0, "ts_init": 0, "o": o, "h": h, "l": l, "c": c, "v": v,
    }


def _actions(cash=(), splits=()):
    # Recorded layout of ...-issuer-actions-v2.json.
    return {
        "schema": "sector-issuer-actions-v2",
        "cash_and_in_kind": list(cash),
        "excluded_issuer_rows": [{"symbol": "SPY", "ex_date": "2025-12-03", "pay_date": "2025-12-05",
                                  "source_row": "1", "reason": "issuer_explicit_zero_distribution", "amount": "0"}],
        "splits": list(splits),
        "identities": {}, "split_reviews": {}, "source_workbook_sha256": "x", "policy": "x",
    }


class SectorDerivativeLoaderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _write(self, bars, actions):
        bars_path, actions_path = self.root / "bars.json", self.root / "actions.json"
        bars_path.write_text(json.dumps(bars), encoding="utf-8")
        actions_path.write_text(json.dumps(actions), encoding="utf-8")
        return bars_path, actions_path

    def _bars(self, symbols=("SPY", "XLE")):
        rows = []
        for symbol in symbols:
            for i, day in enumerate(SESSIONS):
                rows.append(_bar(symbol, day, f"{100 + i}.10", f"{101 + i}.00", f"{99 + i}.50", f"{100 + i}.75", "12345"))
        return rows

    def test_loader_maps_recorded_columns(self):
        cash = {"id": "SPY-2025-12-03", "symbol": "SPY", "kind": "cash", "ex_date": "2025-12-03",
                "pay_date": "2025-12-05", "amount": "1.993368", "cusip": "x", "source_row": "2",
                "components": {"G": "1.993368", "H": "", "I": ""}}
        other = dict(cash, id="XLB-2025-12-03", symbol="XLB")
        split = {"id": "XLE-split-2025-12-05", "symbol": "XLE", "kind": "split", "ex_date": "2025-12-05",
                 "ratio": "2", "source_sha256": "x"}
        bars_path, actions_path = self._write(self._bars(("SPY", "XLE", "XLB")), _actions([cash, other], [split]))

        data = load_sector_derivative(bars_path, actions_path, ("SPY", "XLE"))

        self.assertEqual(data.sessions, SESSIONS)
        self.assertEqual(list(data.bars), ["SPY", "XLE"])
        spy = data.bars["SPY"]
        self.assertEqual(list(spy.index), list(SESSIONS))
        self.assertEqual(list(spy.columns), ["open", "high", "low", "close", "volume"])
        self.assertEqual(spy.loc["2025-12-04"].tolist(), [101.10, 102.00, 100.50, 101.75, 12345.0])
        self.assertEqual(data.dividends, (Dividend("SPY", "2025-12-03", "2025-12-05", 1.993368),))
        self.assertEqual(data.splits, (Split("XLE", "2025-12-05", 2),))

    def test_loader_rejects_mismatched_sessions(self):
        bars = [row for row in self._bars() if not (row["symbol"] == "XLE" and row["session"] == SESSIONS[1])]
        bars_path, actions_path = self._write(bars, _actions())
        with self.assertRaises(MarketDataError) as caught:
            load_sector_derivative(bars_path, actions_path, ("SPY", "XLE"))
        self.assertIn("XLE", str(caught.exception))

    def test_loader_rejects_in_kind_event_for_requested_instrument(self):
        in_kind = {"id": "SPY-2025-12-04", "symbol": "SPY", "kind": "in_kind", "ex_date": "2025-12-04",
                   "pay_date": "2025-12-05", "cusip": "x", "source_row": "3", "components": {},
                   "child_symbol": "XLRE", "ratio": "0.139146"}
        bars_path, actions_path = self._write(self._bars(), _actions([in_kind]))
        with self.assertRaises(MarketDataError) as caught:
            load_sector_derivative(bars_path, actions_path, ("SPY", "XLE"))
        self.assertIn("SPY-2025-12-04", str(caught.exception))

    def test_loader_rejects_missing_instrument(self):
        bars_path, actions_path = self._write(self._bars(), _actions())
        with self.assertRaises(MarketDataError) as caught:
            load_sector_derivative(bars_path, actions_path, ("SPY", "XLF"))
        self.assertIn("XLF", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
