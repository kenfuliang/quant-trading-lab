import ast
import hashlib
import json
import math
import unittest
import numpy as np
from research.pairs_study import fit_pair,next_direction,pair_weights,build_source,decode_fragments,audit_records,SOURCE,SOURCE_SHA,CASES


class StockPairsTests(unittest.TestCase):
    def test_prior_fit_is_invariant_to_current_observation(self):
        x=np.linspace(10,100,250);y=5+2*x+np.tile([1.,-1.],125)
        seen=[]
        def coint(y,x,**kwargs):
            seen.append((y.copy(),x.copy(),kwargs));return (-4.,.01,[-4.,-3.,-2.])
        a=fit_pair(x,y,110,250,coint);b=fit_pair(x,y,200,10,coint)
        for k in ['alpha','beta','sigma','p','correction','eligible']:self.assertEqual(a[k],b[k])
        self.assertNotEqual(a['z'],b['z'])
        self.assertTrue(a['eligible'])
        self.assertEqual(seen[0][2],dict(trend='c',maxlag=5,autolag='aic'))
        np.testing.assert_equal(seen[0][0],y)
        with self.assertRaises(ValueError):fit_pair(x[:249],y[:249],110,250,coint)

    def test_state_persists_until_zero_crossing_or_failed_gate(self):
        m=lambda z,eligible=True:dict(z=z,eligible=eligible)
        self.assertEqual(next_direction(m(1.1),0),1)
        self.assertEqual(next_direction(m(-1.1),0),-1)
        self.assertEqual(next_direction(m(.2),1),1)
        self.assertEqual(next_direction(m(-.2),1),0)
        self.assertEqual(next_direction(m(-.2),-1),-1)
        self.assertEqual(next_direction(m(.2),-1),0)
        self.assertEqual(next_direction(m(2,False),1),0)

    def test_consistent_split_unit_changes_preserve_signal_and_dollar_weights(self):
        x=np.linspace(10,100,250);y=5+2*x+np.tile([1.,-1.],125)
        coint=lambda *a,**k:(-4.,.01,[-4.,-3.,-2.])
        a=fit_pair(x,y,110,230,coint)
        b=fit_pair(x/10,y/4,11,230/4,coint)
        self.assertAlmostEqual(a['z'],b['z'],places=10)
        wa=pair_weights(a,1,110,230);wb=pair_weights(b,1,11,230/4)
        np.testing.assert_allclose(wa,wb,atol=1e-12)

    def test_hedge_sizing_uses_known_prices_and_gross_budget(self):
        w=pair_weights(dict(beta=2.),1,50.,100.)
        self.assertEqual(w,[.49,-.49])
        self.assertAlmostEqual(sum(map(abs,w)),.98)
        self.assertEqual(pair_weights(dict(beta=2.),-1,50.,100.),[-.49,.49])
        self.assertEqual(pair_weights(dict(beta=2.),0,50.,100.),[0.,0.])

    def test_temporal_and_raw_action_boundaries(self):
        source=build_source('pairs');ast.parse(source)
        self.assertIn('t.date() < self.time.date()',source)
        self.assertIn('DataNormalizationMode.SCALED_RAW',source)
        self.assertIn('timedelta(days=600)',source)
        self.assertEqual(source.count('data_normalization_mode=DataNormalizationMode.RAW'),3)
        self.assertIn('day > self._signal_day',source)
        self.assertIn('opening + timedelta(minutes=2)',source)
        self.assertIn('self._prior_short_notional * 0.03',source)
        self.assertIn('self.utc_time - self._prior_time',source)
        self.assertIn('+ self._interest + self._borrow',source)
        self.assertIn('float(h.total_dividends)',source)

    def test_original_is_preserved_and_never_imported(self):
        self.assertEqual(hashlib.sha256(SOURCE.read_bytes()).hexdigest(),SOURCE_SHA)
        for c in CASES:
            s=build_source(c);ast.parse(s);self.assertLess(len(s),32000)
            self.assertNotIn('import yfinance',s);self.assertNotIn('max(data[',s)
            self.assertIn('ConstantSlippageModel(0.0005)',s)

    def test_packet_integrity(self):
        r=dict(study='stock-pairs-spy-v1',case='pairs',kind='full');raw=json.dumps(r,separators=(',',':'))
        line='PRS|pairs|0|0|1|'+hashlib.sha256(raw.encode()).hexdigest()[:12]+'|'+raw
        self.assertEqual(decode_fragments([line],'pairs'),[r])
        for bad in [line+'x',line.replace('|0|1|','|0|2|')]:
            with self.assertRaises(ValueError):decode_fragments([bad],'pairs')

    def test_input_gate_accepts_raw_enum_case_but_rejects_orders_and_future_history(self):
        from copy import deepcopy
        tree=ast.parse(build_source('probe'))
        token=next(n.value.value for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='SOURCE_TOKEN')
        row=dict(source_token=token,ready_days=2514,fit_hash='fixture',fills=0,rejects=0,normalization=['RAW'],models=['InteractiveBrokersFeeModel'],years=[dict(year=y,prior_count=250,history_aligned=True,prior_last=str(y-1)+'-12-31',decision=str(y)+'-01-04') for y in range(2016,2026)],split_counts={'NVDA':2},dividend_counts={'SPY':40,'NVDA':41})
        self.assertTrue(audit_records([row],'probe')['passed'])
        for key,value in [('normalization',['ADJUSTED']),('fills',1)]:
            bad=deepcopy(row);bad[key]=value
            with self.assertRaises(ValueError):audit_records([bad],'probe')
        bad=deepcopy(row);bad['years'][0]['prior_last']=bad['years'][0]['decision']
        with self.assertRaises(ValueError):audit_records([bad],'probe')
