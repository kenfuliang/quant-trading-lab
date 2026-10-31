#!/usr/bin/env python3
"""Prepare private cloud cases; no network, upload or financial execution."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.local/t11-universe-cloud-v11'


def replace_method(source, name, replacement):
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'QuadEnsemble')
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    lines = source.splitlines(keepends=True)
    return ''.join(lines[:node.lineno-1]) + replacement.rstrip() + '\n\n' + ''.join(lines[node.end_lineno:])


UPDATE = '''
    def _universe_update(self, data):
        session = data.bars[self._syms['SPY']].time.date()
        next_day = self.securities[self._syms['SPY']].exchange.hours.get_next_trading_day(self.time).date()
        rank_now = self._u_proposal is None or next_day.month != session.month
        if not rank_now:
            return
        histories = {}
        for ticker in UNIVERSE:
            bars = list(self.history[TradeBar](self._syms[ticker], self.time - timedelta(days=430), self.time, Resolution.DAILY,
                        data_normalization_mode=DataNormalizationMode.TOTAL_RETURN))
            histories[ticker] = [(b.time.date().isoformat(), b.end_time, b.close) for b in bars]
        dates, panel = align_histories(histories, cutoff=self.time,
                                      allowed_latest={session.isoformat()})
        decision = select(panel)
        self._u_proposal = dict(decision.weights)
        self._u_lagged_n += int(dates[-1] != session.isoformat())
        evidence = dict(session=session.isoformat(), dates=dates, panel=panel,
                        ranking=[vars(r) for r in decision.ranking], proposal=self._u_proposal)
        self._u_feature_hash.update(json.dumps(evidence, sort_keys=True, allow_nan=False).encode())
        self._u_rank_n += 1

    def _u_capture(self, data):
        self.plot('AuditNAV', 'NAV', float(self.portfolio.total_portfolio_value))
        self.plot('AuditCash', 'cash', float(self.portfolio.cash))
        self.plot('AuditInterest', 'debit', self._fund_interest)
        for ticker in UNIVERSE:
            self.plot('Audit' + ticker, 'shares', int(self.portfolio[self._syms[ticker]].quantity))
        code = int(self._gate.cap * 2) * 64
        for i, ticker in enumerate(UNIVERSE):
            code += (1 << i) if (self._u_proposal or {}).get(ticker, 0) else 0
        self.plot('AuditIntent', 'code', code)
'''

WEIGHTS = '''    def _t11_weights(self):
        if U_MODE == 'full':
            base = self._ungated_t11_weights()
        elif U_MODE == 'restricted':
            base = {s: w for s, w in self._ungated_t11_weights().items() if s.value in UNIVERSE}
        elif U_MODE in ('equal', 'half'):
            base = {self._syms[t]: w * (0.5 if U_MODE == 'half' else 1.) for t, w in EQUAL_FAMILY.items()}
        else:
            base = {self._syms[t]: w for t, w in (self._u_proposal or {}).items()}
        return {s: w * self._gate.cap for s, w in base.items() if w * self._gate.cap > 0}
'''

END = '''    def on_end_of_algorithm(self):
        records = [('overall', summarize(self._audit_curve))]
        records += [('Y' + r['year'], r) for r in annual(self._audit_curve)]
        records.append(('audit', dict(rejects=self._audit_rejects, fills=self._audit_fills,
            pending=len(self.transactions.get_open_orders()), financing=self._fund_interest,
            gate_seed=self._gate_seed_n, rank_n=self._u_rank_n, lagged_n=self._u_lagged_n,
            gate_hash=self._gate_hash.hexdigest(), feature_hash=self._u_feature_hash.hexdigest(),
            calendar_hash=self._audit_sessions.hexdigest(), debit_error=self._fund_max_post_debit_error)))
        payload = dict(records)
        payload['terminal_orders'] = [dict(id=o.id, symbol=o.symbol.value, type=str(o.type),
            status=str(o.status), quantity=float(o.quantity), time=str(o.time)) for o in self.transactions.get_open_orders()]
        line = json.dumps(payload, separators=(',', ':'), allow_nan=False)
        chunks = [line[i:i+100] for i in range(0, len(line), 100)]
        for i, chunk in enumerate(chunks):
            self.debug('UTXT|' + U_CASE + '|' + str(i) + '|' + str(len(chunks)) + '|' + chunk)
'''


def main():
    OUT.mkdir(exist_ok=True)
    if (OUT / 'frozen-plan.json').exists():
        raise SystemExit('Frozen plan exists; refuse to overwrite')
    parent_path = ROOT / '.local/t11-reference-v2/gated_t11-source.py'
    parent = parent_path.read_text()
    pure = (ROOT / 'research/studies/t11_universe/selection.py').read_text()
    metrics = (ROOT / 'research/studies/t11_universe/metrics.py').read_text()
    base = parent + '\n' + UPDATE + '\n'  # UPDATE remains inside QuadEnsemble.
    base = replace_method(base, '_t11_weights', WEIGHTS)
    base = replace_method(base, 'on_end_of_algorithm', END)
    base = base.replace("'UVIX']", "'UVIX', 'SOXX', 'VTI']", 1)
    needle = '        self._gate_initialize()\n'
    assert base.count(needle) == 1
    base = base.replace(needle, needle + '        self._u_proposal = None\n        self._u_rank_n = 0\n        self._u_lagged_n = 0\n        self._u_feature_hash = hashlib.sha256()\n')
    needle = '        self._funded_rebalance()\n'
    assert base.count(needle) == 1
    base = base.replace(needle, '        self._universe_update(data)\n' + needle)
    base = base.replace('        self._audit_record(data)\n', '        self._audit_record(data)\n        self._u_capture(data)\n', 1)
    # Old summary emitters are unreachable after the new end hook. Removing them
    # and presentation docstrings meets the free32k file limit without changing
    # any decision, fill, financing or gate method.
    tree = ast.parse(base)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'QuadEnsemble')
    removed = {'_audit_end', '_audit_emit'}
    cls.body = [n for n in cls.body if not (isinstance(n, ast.FunctionDef) and n.name in removed)]
    tree.body = [n for n in tree.body if not (isinstance(n, ast.FunctionDef) and n.name == 'summarize_path')]
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'GateCore':
            continue
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                node.body.pop(0)
    base = ast.unparse(tree) + '\n'
    cases = []
    for cost in (25, 50):
        for mode in ('full', 'restricted', 'equal', 'rs1', 'half'):
            case_id = mode + str(cost)
            code = base
            if cost == 50:
                assert code.count('ConstantSlippageModel(0.0025)') == 1
                assert code.count('price * 1.0025 + 0.01') == 1
                code = code.replace('ConstantSlippageModel(0.0025)', 'ConstantSlippageModel(0.005)')
                code = code.replace('price * 1.0025 + 0.01', 'price * 1.005 + 0.01')
            code = ('from datetime import timedelta\nU_MODE = ' + repr(mode) + '\nU_CASE = ' + repr(case_id) + '\n' +
                    pure + '\n' + metrics + '\n' + code)
            assert len(code) <= 32000, ('Free cloud file limit', len(code))
            compile(code, case_id, 'exec')
            tree = ast.parse(code)
            cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'QuadEnsemble')
            original = ast.parse(parent)
            old_cls = next(n for n in original.body if isinstance(n, ast.ClassDef) and n.name == 'QuadEnsemble')
            changed = {'initialize', 'on_data', 'on_end_of_algorithm', '_t11_weights'}
            if cost == 50:
                changed.add('_funded_rebalance')
            for old in old_cls.body:
                if isinstance(old, ast.FunctionDef) and old.name not in changed | removed:
                    new = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == old.name)
                    assert ast.dump(old) == ast.dump(new), old.name
            assert ast.dump(tree.body[next(i for i,n in enumerate(tree.body) if isinstance(n,ast.ClassDef) and n.name=='GateCore')]) == ast.dump(next(n for n in original.body if isinstance(n,ast.ClassDef) and n.name=='GateCore'))
            folder = OUT / case_id
            folder.mkdir(exist_ok=False)
            (folder / 'main.py').write_text(code)
            cases.append(dict(case_id=case_id, mode=mode, cost_bps=cost,
                source=str((folder/'main.py').relative_to(ROOT)), sha256=hashlib.sha256(code.encode()).hexdigest()))
    plan = dict(schema='t11-universe-cloud/v1', status='prepared_not_launched',
        created_utc=datetime.now(timezone.utc).isoformat(), project_id=38676621,
        design='research/plans/t11-long-equity-universe-v2.design.json',
        parent_source_sha256=hashlib.sha256(parent.encode()).hexdigest(),
        case_limit=10, financial_cases_used=0, retries=0, workers=1,
        launch_hours_after_readiness=3, cases=cases,
        capture='Short typed UR records, daily audit charts and official result export. Missing ledger/data snapshot means provisional evidence, never automatic adoption.',
        stop='Capture or integrity failure stops subsequent cases pending read-only recovery. Unknown submission counts as used.',
        accounting='Original staged native accounting retained. Independent ledger parity remains unverified; full daily-close summaries are provisional pending export/account reconciliation.',
        data='QC hosted histories; common causal six-ETF253-bar total-return feature checks at every monthly decision. Original native execution subscriptions and2004RAW gate seed unchanged. No local snapshot/redistribution claim.')
    (OUT/'frozen-plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    (OUT/'journal.json').write_text(json.dumps(dict(max_cases=10, used=0, attempts=[]), indent=2)+'\n')
    print('Prepared10private cases; source compile and unchanged-method AST checks passed. Zero launches.')


if __name__ == '__main__':
    main()
