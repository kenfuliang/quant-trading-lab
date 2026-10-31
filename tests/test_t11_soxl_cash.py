"""Synthetic boundary checks; no prices, financial simulation or broker calls."""
import unittest
from research.studies.t11_soxl_cash.selection import select


class SoxlCashTests(unittest.TestCase):
    def test_full_concentration_and_gate_applied_once(self):
        original = dict(TECL=1/3, SOXL=1/3, TQQQ=1/3)
        saved = original.copy()
        for cap, expected in ((1, .9), (.5, .45), (0, 0)):
            result = select(original, ready=True, gate_cap=cap)
            self.assertAlmostEqual(result.soxl_target_nav, expected)
            self.assertAlmostEqual(result.cash_target_nav, 1 - expected)
        self.assertEqual(original, saved)

    def test_no_rotation_into_other_t11_branches(self):
        for weights in ({'TQQQ': 1.}, {'SPXL': 1.}, {'SOXS': 1.},
                        {'UVXY': 1/3, 'BIL': 1/3, 'BTAL': 1/3}, {}, {'SOXL': 0}):
            with self.subTest(weights=weights):
                result = select(weights, ready=True, gate_cap=1.)
                self.assertEqual((result.soxl_target_nav, result.cash_target_nav), (0, 1))
        self.assertEqual(select({'SOXL': 1}, ready=False, gate_cap=1).soxl_target_nav, 0)

    def test_reject_ambiguous_invalid_or_levered_inputs(self):
        for bad in (float('nan'), float('inf'), -.1, 1.1, True, .3):
            with self.subTest(cap=bad), self.assertRaises(ValueError):
                select({'SOXL': 1}, ready=True, gate_cap=bad)
        for weights in ({'SOXL': float('nan')}, {'SOXL': -1}, {'SOXL': True},
                        {'SOXL': 1, 'TECL': 1}):
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                select(weights, ready=True, gate_cap=1)
        with self.assertRaises(ValueError):
            select({'SOXL': 1}, ready=None, gate_cap=1)


if __name__ == '__main__':
    unittest.main()
