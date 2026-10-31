import unittest
from research.sector_resolution import resolved_sector,matched_weights
from research.quantconnect.stock_risk_policy import sector_weights


class SectorResolutionTests(unittest.TestCase):
    def test_native_hierarchy_and_conflicting_evidence(self):
        self.assertEqual(resolved_sector(0,31110,31110010),(311,'native_group'))
        self.assertEqual(resolved_sector(0,0,10280010),(102,'native_industry'))
        self.assertEqual(resolved_sector(0,0,0,310),(310,'native_security'))
        with self.assertRaises(ValueError):resolved_sector(0,31110,10280010)
        with self.assertRaises(ValueError):resolved_sector(0,31110,0,102)

    def test_future_and_current_day_sources_cannot_fill_history(self):
        row=dict(sid='A',available_date='2025-02-18',effective_from='2025-01-01',effective_to='2025-12-31',sector=311,source_id='filing-20250218')
        for when in ['2025-01-02','2025-02-18']:
            with self.assertRaises(ValueError):resolved_sector(0,0,0,sid='A',when=when,fallbacks=[row])
        self.assertEqual(resolved_sector(0,0,0,sid='A',when='2025-03-03',fallbacks=[row]),(311,'filing-20250218'))
        with self.assertRaises(ValueError):resolved_sector(0,0,0,sid='B',when='2025-03-03',fallbacks=[row])

    def test_unknown_and_bad_codes_do_not_silently_become_cash(self):
        for args in [(0,0,0),(999,0,0),(0,311,0),(0,0,31110)]:
            with self.assertRaises(ValueError):resolved_sector(*args)

    def test_control_matches_total_without_sector_tilt(self):
        original=dict(A=.2,B=.2,C=.2,D=.2,E=.2)
        limited=sector_weights(original,dict(A=311,B=311,C=311,D=103,E=103))
        matched=matched_weights(original,limited)
        self.assertAlmostEqual(sum(limited.values()),sum(matched.values()))
        self.assertEqual(set(original),set(matched))
        self.assertTrue(all(abs(w-.16)<1e-12 for w in matched.values()))
        self.assertNotEqual(limited,matched)

    def test_control_rejects_invalid_budget(self):
        for original,limited in [({},{}),({'A':.2},{'A':.3}),({'A':.2},{'A':-.1})]:
            with self.assertRaises(ValueError):matched_weights(original,limited)
