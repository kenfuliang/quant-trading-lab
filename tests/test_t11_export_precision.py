"""Analytic rounding-bound checks on invented equity paths only."""
import unittest
from research.studies.t11_reproduction.exports import annual_calmar_rounding_bound


def ratio(values, opening):
    peak=opening;depth=0
    for v in values:peak=max(peak,v);depth=max(depth,1-v/peak)
    return (values[-1]/opening-1)/depth


class PrecisionTests(unittest.TestCase):
    def test_half_unit_perturbations_are_bounded(self):
        values=[12000.,9000.,13500.]
        rows=[{'nav_usd':x} for x in values]
        bound=annual_calmar_rounding_bound(rows,10000.)
        for sign in (-1,1):
            altered=[v+sign*(.00005 if i%2 else -.00005) for i,v in enumerate(values)]
            difference=abs(ratio(altered,10000.+sign*.00005)-ratio(values,10000.))
            self.assertLessEqual(difference,bound)

    def test_undefined_drawdown_not_infinite_good_score(self):
        self.assertIsNone(annual_calmar_rounding_bound([{'nav_usd':11000.}],10000.,exact_opening=True))

    def test_unresolvable_precision_is_rejected(self):
        with self.assertRaises(ValueError):annual_calmar_rounding_bound([{'nav_usd':.00001}],10000.)


if __name__=='__main__':unittest.main()
