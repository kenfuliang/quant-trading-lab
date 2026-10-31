import hashlib
import json
import unittest
from research.quantconnect.stock_risk_policy import sector_weights
from scripts.stock_risk_evidence import decode


class StockRiskTests(unittest.TestCase):
    def test_concentrated_sector_proportional_cash_residual(self):
        weights = dict(A=.2,B=.2,C=.2,D=.2,E=.2)
        result = sector_weights(weights, dict(A=1,B=1,C=1,D=2,E=3))
        self.assertAlmostEqual(sum(result[s] for s in ('A','B','C')), .4)
        self.assertAlmostEqual(sum(result.values()), .8)
        self.assertAlmostEqual(.9 * sum(result[s] for s in ('A','B','C')), .36)
        self.assertAlmostEqual(.9 * .5 * sum(result[s] for s in ('A','B','C')), .18)

    def test_missing_sector_stays_cash_and_no_replacement(self):
        self.assertEqual(sector_weights(dict(A=.2,B=.2),dict(A=0,B=3)),dict(B=.2))
        self.assertEqual(sector_weights({},{}),{})

    def test_diverse_weights_unchanged(self):
        weights = dict(A=.2,B=.2,C=.2,D=.2,E=.2)
        self.assertEqual(sector_weights(weights,dict(A=1,B=1,C=2,D=2,E=3)),weights)

    def test_packet_roundtrip_missing_corruption(self):
        data = dict(case='original',study='stock-risk-v1',months=[['2020-01-02', 'green']])
        encoded = json.dumps(data)
        digest = hashlib.sha256(encoded.encode()).hexdigest()[:12]
        chunks = [encoded[i:i+30] for i in range(0,len(encoded),30)]
        messages = [f'RSG|original|{i}|{len(chunks)}|{digest}|{c}' for i,c in enumerate(chunks)]
        self.assertEqual(decode(messages,'original'),data)
        for broken in (messages[:-1], messages[:-1]+[messages[-1][:-1]], messages+[messages[0]+'x']):
            with self.assertRaises(ValueError):decode(broken,'original')

    def test_trailing_identifier_space_is_preserved(self):
        # innerText trims a fragment ending inside a security name. Read exact
        # DOM textContent; do not patch a failed checksum by guessing whitespace.
        plain=json.dumps(dict(study='stock-risk-v1',case='original',security='NFLX R735'))
        cut=plain.index('NFLX ')+5
        chunks=[plain[:cut],plain[cut:]]
        digest=hashlib.sha256(plain.encode()).hexdigest()[:12]
        messages=[f'RSG|original|{i}|2|{digest}|{c}' for i,c in enumerate(chunks)]
        self.assertEqual(decode(messages,'original')['security'],'NFLX R735')
        with self.assertRaises(ValueError):decode([m.rstrip() for m in messages],'original')

    def test_controls_keep_financial_and_feature_functions(self):
        import ast
        from scripts.prepare_stock_risk import generate, ROOT
        for case in ('original','spy'):
            source = ROOT/'.local/selection-completion-v1'/('spy-source.py' if case=='spy' else 'stock-source.py')
            if not source.exists():
                continue
            old = ast.parse(source.read_text())
            new = ast.parse(generate(case))
            def methods(tree):
                cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SelectionComparison')
                return {n.name:ast.dump(n) for n in cls.body if isinstance(n,ast.FunctionDef)}
            a,b=methods(old),methods(new)
            for name in ('_refresh_weights','_funded_rebalance','configure_security','_fund_accrue'):
                self.assertEqual(a[name],b[name],name)
