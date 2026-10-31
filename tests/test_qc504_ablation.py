import ast
import unittest
from scripts.prepare_qc504_ablation import adapt,CASES

FIXTURE='''AUDIT_CASE='cost25'
class Example:
    QUARTER=.25
    def _t10_weights(self): return {'A':self.QUARTER}
    def _t11_weights(self): return {'B':self.QUARTER}
    def _s2_weights(self): return {'C':self.QUARTER}
    def _s3_weights(self): return {'D':self.QUARTER}
    def _rebalance(self): return self._s2_weights()
'''
class AblationTests(unittest.TestCase):
    def test_full_budget_and_only_selected_signal(self):
        for case in CASES:
            scope={};exec(adapt(FIXTURE,case),scope);x=scope['Example']()
            weights={c:getattr(x,'_'+c+'_weights')() for c in CASES[1:]}
            self.assertEqual(sum(sum(w.values()) for w in weights.values()),1)
            self.assertEqual([c for c,w in weights.items() if w],list(CASES[1:]) if case=='ensemble' else [case])
            self.assertEqual(scope['AUDIT_CASE'],case)
    def test_order_policy_unchanged(self):
        original=next(n for n in ast.walk(ast.parse(FIXTURE)) if isinstance(n,ast.FunctionDef) and n.name=='_rebalance')
        for case in CASES:
            transformed=next(n for n in ast.walk(ast.parse(adapt(FIXTURE,case))) if isinstance(n,ast.FunctionDef) and n.name=='_rebalance')
            self.assertEqual(ast.dump(original),ast.dump(transformed))

class FragmentTests(unittest.TestCase):
    def fragments(self):
        import hashlib,json
        payload=json.dumps(dict(case='s2',study='qc504-ablation-v1',kind='overall',value=1.25),separators=(',',':'))
        parts=[payload[i:i+20] for i in range(0,len(payload),20)];digest=hashlib.sha256(payload.encode()).hexdigest()[:12]
        return [f'2025-12-31 QCA|s2|1|{i}|{len(parts)}|{digest}|{part}' for i,part in enumerate(parts)]
    def test_reassemble_out_of_order_duplicates(self):
        from scripts.parse_qc504_fragments import decode
        import json
        f=self.fragments();self.assertEqual(json.loads(decode(list(reversed(f))+f,'s2')[0])['value'],1.25)
    def test_missing_and_corrupted_parts_fail_closed(self):
        from scripts.parse_qc504_fragments import decode
        f=self.fragments()
        with self.assertRaisesRegex(ValueError,'Missing fragment'):decode(f[:-1],'s2')
        f[-1]+='...'
        with self.assertRaisesRegex(ValueError,'Digest mismatch'):decode(f,'s2')
