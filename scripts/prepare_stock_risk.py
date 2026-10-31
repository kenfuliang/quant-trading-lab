"""Freeze five ablation adapters from preserved stock/SPY controls, without launch."""
import ast
import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = 'stock-risk-v1'
RAW = ROOT / '.local' / STUDY
CASES = {'original': (False, False), 'gate': (True, False),
         'sector': (False, True), 'combined': (True, True), 'spy': (False, False)}


def generate(case):
    gate_on, sector_on = CASES[case]
    source = ROOT / '.local/selection-completion-v1' / ('spy-source.py' if case == 'spy' else 'stock-source.py')
    tree = ast.parse(source.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and n.value == 'selection-completion-v1':
            n.value = STUDY
    next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'AUDIT_CASE' for t in n.targets)).value = ast.Constant(case)
    core = next(n for n in ast.parse((ROOT/'research/quantconnect/sector_comparison.py').read_text()).body if isinstance(n, ast.ClassDef) and n.name == 'GateCore')
    for n in ast.walk(core):
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'dd' for t in n.targets):
            n.value = ast.Constant(0.)
    tree.body[:0] = ast.parse(f'APPLY_GATE={gate_on!r}\nAPPLY_SECTOR={sector_on!r}').body + [core]
    policy = ast.parse((ROOT/'research/quantconnect/stock_risk_policy.py').read_text())
    functions = [n for n in policy.body if isinstance(n, ast.FunctionDef)]
    names = {n.name for n in functions}
    cls.body = [n for n in cls.body if not (isinstance(n, ast.FunctionDef) and n.name in names)]
    tree.body.insert(0, next(n for n in functions if n.name == 'sector_weights'))
    cls.body += [n for n in functions if n.name != 'sector_weights']
    hooks = ast.parse((ROOT/'research/quantconnect/t11_gate_policy.py').read_text())
    for n in hooks.body:
        if isinstance(n, ast.FunctionDef) and n.name in ('gate_initialize', 'gate_observe'):
            n.name = '_' + n.name
            cls.body.append(n)
    init = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'initialize')
    init.body += ast.parse('self._risk_initialize()').body
    selector = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'select_universe')
    selector.body.insert(-1, ast.parse("for f in large:\n    self._risk_sectors[f.symbol] = int(f.asset_classification.morningstar_sector_code)").body[0])
    # Keep pending/current targets subscribed, independently of feature eligibility.
    selector.body[-1] = ast.parse('return list(dict.fromkeys(self._selected + list(self._weights)))').body[0]
    on = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'on_data')
    on.body.insert(1, ast.parse('self._gate_observe(data)').body[0])
    index = next(i for i, n in enumerate(on.body) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute) and n.value.func.attr == '_refresh_weights')
    on.body.insert(index+1, ast.parse('self._risk_monthly(data)').body[0])
    on.body += ast.parse('self._risk_observe_exposure()').body
    emit = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_audit_emit')
    # Preserve existing finance/feature metadata; export full assets, not the old top/bottom four.
    cutoff = next(i for i, n in enumerate(emit.body) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'line' for t in n.targets))
    body = emit.body[:cutoff]
    body = [n for n in body if not (isinstance(n, ast.If) and "'assets'" in ast.unparse(n.test) and any(isinstance(x, ast.Name) and x.id == 'values' for x in ast.walk(n)))]
    emit.body = body + ast.parse('self._risk_records.append(payload)').body
    end = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_audit_end')
    end.body += ast.parse('self._risk_finish()').body
    return ast.unparse(ast.fix_missing_locations(tree)) + '\n'


def prepare():
    RAW.mkdir(exist_ok=False)
    hashes = {}
    for case in CASES:
        path = RAW / f'{case}-source.py'
        path.write_text(generate(case))
        hashes[case] = hashlib.sha256(path.read_bytes()).hexdigest()
    now = datetime.now(timezone.utc)
    plan = dict(study_id=STUDY, status='frozen', created_utc=now.isoformat(),
                deadline_utc=(now+timedelta(minutes=90)).isoformat(), cases=CASES,
                max_total_attempts=7, technical_retry_slots=2, source_hashes=hashes,
                dates=['2020-01-01','2025-12-31'], capital_usd=10000,
                costs='25bp constant slippage; native IB margin/fees; flat6% debit ACT/360; zero credit interest',
                timing='Monthly unchanged top-five ranking; sector scaling at monthly decisions; daily gate changes target intent; staged MOO reductions before buys; whole shares',
                sector='Historical Morningstar sector from monthly fundamental selection; pro-rata scale original top five to36% NAV target per sector before gate; no replacement/redistribution; unknown classification gets zero sector-treatment target. Drift and execution can exceed target.',
                gate='Retained SPY RAW EMA50/200 and20-return sample vol; red40%, yellow nonpositive trend or25%; recovery5closes below35% then5positive closes below20%; caps1/.5/0; drawdown component disabled',
                hypothesis='Describe separate/combined changes in loss depth, recovery duration, CAGR and terminal wealth; no hidden retention threshold and no tuning. A lower drawdown with lower return is a tradeoff.',
                metrics='Full/annual returns, DD, Sharpe0RF252sample, Calmar, UW sessions/calendar/fraction and censoring; average exposure, peak sector exposure, complete monthly chosen IDs/rank/sector/base and sector targets/pretrade held weights, all-stock native accounting PnL and fees',
                controls='Fresh original/SPY must reproduce selection-completion-v1 financial metrics and calendars; all stock cases match eligible-universe/feature hashes and monthly original selections; gate hashes match all five',
                evidence='1508session calendar; zero rejects/nonMOO/open orders/future/invalid/unordered; native stock PnL+financing residual <=10c; checksummed complete derived packet; no raw vendor export',
                limits=['Viewed development history, not independent OOS','No exposure-matched timing-alpha attribution','USD10000 fixture, not300000 qualification','Sector target cap is not hard continuous exposure cap','Native PnL check is not independent transaction ledger','No broker/account/orders/services/imports/paid data/agents/commits/publication'],
                stopping='Five fixed cases, at most two technical-only retries, seven launches or90minutes; preserve failures; no parameter/strategy repair after viewing results',
                git_sha=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip())
    dependencies=['.local/selection-completion-v1/stock-source.py','.local/selection-completion-v1/spy-source.py','research/quantconnect/sector_comparison.py','research/quantconnect/t11_gate_policy.py','research/quantconnect/stock_risk_policy.py','scripts/prepare_stock_risk.py']
    plan['input_hashes'] = {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in dependencies}
    (ROOT/'research/plans/stock-risk-v1.json').write_text(json.dumps(plan,indent=2)+'\n')
    (RAW/'attempts.json').write_text(json.dumps(dict(study_id=STUDY,status='active',deadline_utc=plan['deadline_utc'],source_hashes=hashes,attempts=[]),indent=2)+'\n')
    print('Frozen five cases; seven total launch ceiling; deadline', plan['deadline_utc'])


if __name__ == '__main__':
    prepare()
