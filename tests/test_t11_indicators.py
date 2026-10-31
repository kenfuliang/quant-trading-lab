"""Invented prices and independent rational calculations; no vendor data files."""
from decimal import Decimal as D
from fractions import Fraction as F
import unittest
from research.studies.t11_reproduction.indicators import SimpleAverage,WilderRSI

class TestT11Indicators(unittest.TestCase):
    def test_wilder_seed_readiness_and_hand_computed_path(self):
        r=WilderRSI(3)
        for x in [100,101,100]:r.update(x)
        self.assertFalse(r.ready);self.assertEqual(r.current,D(50))
        self.assertAlmostEqual(float(r.update(102)),75);self.assertTrue(r.ready)
        self.assertAlmostEqual(float(r.update(102)),75)
        self.assertAlmostEqual(float(r.update(100)),float(F(600,17)))
    def test_flat_rsi_is100_instead_of_generic50(self):
        r=WilderRSI(10)
        for _ in range(11):self.assertEqual(r.update(100),100)
        self.assertTrue(r.ready);self.assertFalse(r.snapshot()['native_engine_parity'])
    def test_monotone_and_period_one(self):
        up=WilderRSI(2);down=WilderRSI(2);one=WilderRSI(1)
        for x in [100,101,102,103]:up.update(x);down.update(204-x)
        self.assertEqual(up.current,100);self.assertEqual(down.current,0)
        one.update(100);self.assertEqual(one.update(90),0);self.assertTrue(one.ready)
    def test_sma_partial_warmup_and_rolling_prefix(self):
        s=SimpleAverage(3)
        self.assertEqual(s.update(2),2);self.assertFalse(s.ready)
        s.update(4);self.assertEqual(s.update(6),4);self.assertTrue(s.ready)
        self.assertEqual(s.update(8),6)
    def test_bad_input_cannot_advance_state(self):
        r=WilderRSI(2);r.update(100);before=r.snapshot()
        for x in ['NaN','Infinity',0,-1]:
            with self.assertRaises(ValueError):r.update(x)
            self.assertEqual(before,r.snapshot())
