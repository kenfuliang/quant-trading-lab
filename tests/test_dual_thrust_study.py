import ast
import hashlib
import json
import unittest
from research.dual_thrust_study import thresholds,build_source,decode_fragments,SOURCE,SOURCE_SHA,CASES


class DualThrustTests(unittest.TestCase):
    def test_flat_at_close_strategy_observes_fee_model_on_fill(self):
        from types import SimpleNamespace as NS
        source=ast.parse(build_source('intraday'))
        callback=next(n for n in ast.walk(source) if isinstance(n,ast.FunctionDef) and n.name=='on_order_event')
        module=ast.fix_missing_locations(ast.Module(body=[callback],type_ignores=[]))
        statuses=NS(INVALID=0,CANCELED=1,FILLED=2,PARTIALLY_FILLED=3)
        ns={'OrderStatus':statuses};exec(compile(module,'<fill-audit-regression>','exec'),ns)
        class InteractiveBrokersFeeModel:
            pass
        class TestSymbol(str):
            @property
            def id(self):
                return self
        state=NS(_fees=0.,_rejects=0,_fills=0,_notional=0.,_spy_fills=0,_spy='SPY',_traded=set(),_fee_models=set(),securities={'SPY':NS(fee_model=InteractiveBrokersFeeModel())})
        event=NS(symbol=TestSymbol('SPY'),status=2,fill_quantity=1,fill_price=100,order_fee=NS(value=NS(amount=1.)))
        ns['on_order_event'](state,event)
        self.assertEqual(state._fee_models,{'InteractiveBrokersFeeModel'})
        self.assertEqual((state._fees,state._fills,state._notional),(1.,1,100.))

    def test_completed_range_hand_calculation(self):
        # HH=110, LC=96, HC=105, LL=90: range15, thresholds107.5/92.5.
        rows=[dict(high=110-i,low=90+i,close=96+i*2.25) for i in range(5)]
        self.assertEqual(thresholds(rows,100),(107.5,92.5))
        with self.assertRaises(ValueError):thresholds(rows[:4],100)
        with self.assertRaises(ValueError):thresholds([dict(high=1,low=4,close=3)]*5,100)

    def test_current_session_not_in_window_and_next_minute_execution(self):
        tree=ast.parse(build_source('dual'));on=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='on_data')
        source=ast.unparse(on)
        self.assertIn("date.fromisoformat(s['day']) >= day",source)
        self.assertLess(source.index('thresholds('),source.index('self._sessions.append('))
        self.assertLess(source.index('self.set_holdings(self._spy, 0.98 * self._pending_direction)'),source.index("elif float(bar.close) > self._upper:"))
        self.assertIn('self.time < self._cutoff',source)
        self.assertIn("raise ValueError('Not flat at close')",source)

    def test_preserved_original_not_executed(self):
        self.assertEqual(hashlib.sha256(SOURCE.read_bytes()).hexdigest(),SOURCE_SHA)
        for c in CASES:
            s=build_source(c);ast.parse(s);self.assertNotIn('os.chdir',s);self.assertNotIn('read_csv',s)
            self.assertIn('ConstantSlippageModel(0.0005)',s)
            self.assertIn('self._prior_short_notional * 0.03',s)
            self.assertIn('+ self._interest + self._borrow',s)
            self.assertLess(len(s),32000)

    def test_packet_fidelity(self):
        payload=dict(study='dual-thrust-spy-v1',case='dual',kind='full');raw=json.dumps(payload,separators=(',',':'));line='DTH|dual|0|0|1|'+hashlib.sha256(raw.encode()).hexdigest()[:12]+'|'+raw
        self.assertEqual(decode_fragments([line],'dual'),[payload])
        for bad in [line+'x',line.replace('|0|1|','|0|2|')]:
            with self.assertRaises(ValueError):decode_fragments([bad],'dual')
