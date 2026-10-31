"""Invented inputs only; no credentials, HTTP, broker or financial simulations."""
import unittest
from datetime import date,timedelta
from paper_trading.t11_preview import close_map,features,gate_preview
from paper_trading.t11_pilot import SYMBOLS


class PreviewTests(unittest.TestCase):
    def test_bar_integrity_missing_duplicate_and_future(self):
        bar={'t':'2026-01-02T05:00:00Z','o':100,'h':101,'l':99,'c':100,'v':1000}
        good={'bars':{'SPY':[bar]}}
        self.assertEqual(close_map([good],{'SPY'},{'2026-01-02'})['SPY']['2026-01-02'],100)
        for pages in [[good,good],[{'bars':{}}],[{'bars':{'SPY':[bar|{'c':102}]}}]]:
            with self.assertRaises(ValueError):close_map(pages,{'SPY'},{'2026-01-02'})
        with self.assertRaises(ValueError):close_map([good],{'SPY'},{'2026-01-01'})

    def test_features_full_universe_and_lookback(self):
        days=[str(date(2025,1,1)+timedelta(days=i)) for i in range(230)]
        closes={s:{d:100+i*.1 for i,d in enumerate(days)} for s in SYMBOLS}
        f=features(closes,days)
        self.assertEqual(len(f['qqq_history']),61)
        self.assertEqual(f['rsi10']['SPY'],100)
        with self.assertRaises(ValueError):features(closes,days[:100])

    def test_gate_steady_trend_green_and_seed_stability(self):
        raw={str(date(2020,1,1)+timedelta(days=i)):100+i*.1 for i in range(1000)}
        gate=gate_preview(raw)
        self.assertEqual(gate['state'],'green')
        self.assertEqual(gate['cap'],1.)
        self.assertTrue(gate['last60_states_match_half_seed'])
        self.assertFalse(gate['original2004_seed_parity'])
        with self.assertRaises(ValueError):gate_preview(dict(list(raw.items())[:100]))
