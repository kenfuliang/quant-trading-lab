"""Invented input only. Never downloads, launches historical cases or opens brokers."""
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import pandas as pd
from research.studies.sector_gate import model,audit,signals
from research.studies.sector_selection import model as parent
from tests.test_sector_selection_model import synthetic_input

class TestSectorGate(unittest.TestCase):
    def test_staged_thresholds_and_reference_recurrence(self):
        from research.risk_gate import states
        vols=[.15]*5+[.45]+[.30]*5+[.15]*5+[.26]+[.40]+[.35]*5+[.34]*5+[.15]*5
        f=pd.DataFrame({'fast':2.,'slow':1.,'vol':vols})
        actual=signals.classify(f);expected=states(f.assign(dd=0))
        pd.testing.assert_frame_equal(actual,expected)
        self.assertEqual(actual.state.iloc[4],'green');self.assertEqual(actual.state.iloc[5],'red')
        self.assertEqual(actual.state.iloc[9],'red');self.assertEqual(actual.state.iloc[10],'yellow')
        self.assertEqual(actual.state.iloc[15],'green')
        self.assertTrue((actual.state.iloc[17:23]=='red').all())

    def test_causal_prefix_and_separate_math(self):
        close=pd.Series(100*np.exp(np.arange(330)*.001+.01*np.sin(np.arange(330))),index=pd.bdate_range('2016-01-04',periods=330))
        close.iloc[285:]=close.iloc[285:]*.70
        first=signals.timeline(close);changed=close.copy();changed.iloc[310:]*=1.4
        pd.testing.assert_frame_equal(first.iloc[:310],signals.timeline(changed).iloc[:310])
        own=audit.independent_gate(close.tolist())
        for i in range(201,len(close)):
            self.assertEqual(first.iloc[i].state,own[i-1]['state'])
            self.assertAlmostEqual(float(first.iloc[i].cap),float(own[i-1]['cap']))
            self.assertAlmostEqual(first.iloc[i].vol,own[i-1]['vol'])
        self.assertEqual(first.iloc[286].state,'red')

    def test_invented_accounts_controls_gate_cuts_and_reentry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bundle=synthetic_input(root)
            doc=json.loads(bundle.read_text());prices=Path(doc['files']['prices']['path']);rows=json.loads(prices.read_text())
            for r in rows:
                if r['symbol']=='SPY':
                    # One invented shock followed by quiet recovery, to exercise cash and cap transitions.
                    shock=.7 if r['session']>='2017-02-10' else 1
                    for k in ('o','h','l','c'):r[k]=str(float(r[k])*shock)
            prices.write_text(json.dumps(rows));frames,acts=model.load_inputs(bundle)
            for policy in model.POLICIES:
                out=root/policy;model.save_case(out,frames,acts,policy,5,end='2017-04-28')
                proof=audit.replay(bundle,out,policy,5,end='2017-04-28');self.assertEqual(proof['status'],'passed')
                if policy!='gate':
                    other=root/(policy+'-parent');parent.save_case(other,frames,acts,policy,5,end='2017-04-28')
                    for name in ('ledger.csv','trades.csv','contributions.csv','summary.json'):self.assertEqual((out/name).read_bytes(),(other/name).read_bytes())
            gate=pd.read_csv(root/'gate/gate-decisions.csv');ledger=pd.read_csv(root/'gate/ledger.csv').set_index('date')
            self.assertTrue({'red','yellow','green'}.issubset(set(gate.state)))
            for day in gate.loc[gate.state=='red','date']:self.assertEqual(ledger.loc[day,list(model.SYMBOLS)].sum(),0)
            decisions=json.loads((root/'gate/selections.json').read_text());self.assertTrue(any(not d['monthly_selection'] for d in decisions))
            selection=None
            for d in decisions:
                if d['monthly_selection']:selection=d['picks']
                else:self.assertEqual(d['picks'],selection)
            # Audit must reject a corrupted state even when ledger and trades remain intact.
            gate.loc[0,'cap']=.123;gate.to_csv(root/'gate/gate-decisions.csv',index=False)
            with self.assertRaises(AssertionError):audit.replay(bundle,root/'gate','gate',5,end='2017-04-28')

class TestSectorGateDecision(unittest.TestCase):
    def test_growth_or_duration_tradeoff_cannot_pass_headline_only(self):
        from research.studies.sector_gate.review import decision
        base={'calmar':.5,'cagr_pct':10.,'max_drawdown_pct':20.,'uw_sessions':100,'uw_days':140}
        s={f'{p}-{b}':dict(base) for b in (5,10) for p in ('gate','vol','hold')}
        for b in (5,10):s[f'gate-{b}'].update(calmar=.6,cagr_pct=9.,max_drawdown_pct=15.,uw_sessions=120)
        d=decision(s);self.assertFalse(d['fixed_target_passed'])
        self.assertFalse(d['contexts']['5']['checks']['cagr_not_lower'])
        self.assertFalse(d['contexts']['5']['checks']['underwater_sessions_not_longer'])
        for b in (5,10):s[f'gate-{b}'].update(cagr_pct=11.,uw_sessions=90,uw_days=130)
        self.assertTrue(decision(s)['fixed_target_passed'])
