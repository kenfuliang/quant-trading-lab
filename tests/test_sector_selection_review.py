"""Prospective scientific decision tests on invented metric records."""
import copy
import unittest
from research.studies.sector_selection.review import decision

def fixtures():
    out=[]
    for cost in (5,10):
        for policy in ('vol','raw','equal','hold'):
            candidate=policy=='vol'
            out.append({'policy':policy,'cost_bps':cost,'calmar':.625 if candidate else .5,
                        'cagr_pct':10.,'max_drawdown_pct':16 if candidate else 20,
                        'uw_sessions':80 if candidate else 100,'uw_days':120 if candidate else 150})
    return out

class TestSectorReview(unittest.TestCase):
    def test_requires_both_costs_and_all_guards(self):
        self.assertEqual(decision(fixtures())['decision'],'retain_for_further_validation')
        bad=fixtures();bad[4]['cagr_pct']=9
        self.assertEqual(decision(bad)['decision'],'reject_fixed_target')
        self.assertFalse(decision(bad)['both_costs']['10']['guards']['cagr_not_lower'])

    def test_simpler_control_domination_rejects(self):
        data=fixtures();data[2].update(calmar=.8,cagr_pct=11,max_drawdown_pct=13.75,uw_sessions=70,uw_days=100)
        self.assertFalse(decision(data)['both_costs']['5']['guards']['not_simpler_control_dominated'])

    def test_missing_calmar_never_manufactures_pass(self):
        data=fixtures();data[0]['calmar']=None
        self.assertEqual(decision(data)['decision'],'reject_fixed_target')
