"""Freeze three private adapters; no strategy source is redistributed."""
import ast,hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone,timedelta
ROOT=Path(__file__).resolve().parents[1];STUDY='qc504-t11-gate-v1';RAW=ROOT/'.local'/STUDY
CASES=('ensemble','t11','gated_t11')
def adapt(source,case):
    tree=ast.parse(source);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
    for n in ast.walk(tree):
        if isinstance(n,ast.Constant) and n.value=='qc504-funded-v1':n.value=STUDY
    next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='AUDIT_CASE' for t in n.targets)).value=ast.Constant(case)
    gate=next(n for n in ast.parse((ROOT/'research/quantconnect/sector_comparison.py').read_text()).body if isinstance(n,ast.ClassDef) and n.name=='GateCore')
    for n in ast.walk(gate):
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='dd' for t in n.targets):n.value=ast.Constant(0.)
    tree.body.insert(0,ast.parse('from collections import deque').body[0]);tree.body.insert(1,gate)
    hooks=ast.parse((ROOT/'research/quantconnect/t11_gate_policy.py').read_text())
    for n in hooks.body:
        if isinstance(n,ast.FunctionDef) and n.name!='gated_t11_weights':n.name='_'+n.name;cls.body.append(n)
    if case=='gated_t11':
        next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_t11_weights').name='_ungated_t11_weights'
        n=next(n for n in hooks.body if isinstance(n,ast.FunctionDef) and n.name=='gated_t11_weights');n.name='_t11_weights';cls.body.append(n)
    init=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='initialize');init.body+=ast.parse('self._gate_initialize()').body
    on=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='on_data');on.body.insert(1,ast.parse('self._gate_observe(data)').body[0])
    emit=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_audit_emit')
    emit.body=ast.parse("""
if payload.get('kind')=='overall':
    payload=dict(payload,gate_counts=self._gate_counts,gate_changes=self._gate_changes,gate_input_sha256=self._gate_hash.hexdigest(),gate_seed_n=self._gate_seed_n)
""").body+emit.body
    old={n.name:ast.dump(n) for n in ast.parse(source.replace('qc504-funded-v1',STUDY)).body if isinstance(n,ast.ClassDef) for n in n.body if isinstance(n,ast.FunctionDef)}
    for n in cls.body:
        if isinstance(n,ast.FunctionDef) and n.name in old and n.name not in ('initialize','on_data','_audit_emit','_t11_weights'):
            assert ast.dump(n)==old[n.name],n.name
    if case!='gated_t11':assert ast.dump(next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_t11_weights'))==old['_t11_weights']
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'
def prepare():
    RAW.mkdir(exist_ok=False);hashes={};inputs={}
    for case in CASES:
        p=ROOT/'.local/qc504-funded-v1'/f'{"t11" if case=="gated_t11" else case}-source.py'
        inputs[case]=hashlib.sha256(p.read_bytes()).hexdigest();out=RAW/f'{case}-source.py';out.write_text(adapt(p.read_text(),case));hashes[case]=hashlib.sha256(out.read_bytes()).hexdigest()
    p=json.loads((ROOT/'research/plans/qc504-funded-v1.json').read_text());now=datetime.now(timezone.utc)
    p.update(study_id=STUDY,created_utc=now.isoformat(),deadline_utc=(now+timedelta(minutes=45)).isoformat(),cases=list(CASES),max_financial_attempts=5,max_unique_cases=3,technical_repair_slots=2,source_hashes=hashes,input_hashes=inputs,baseline='Three fresh runs; ungated T11 and ensemble must reproduce funded-v1. No additional variants.',hypothesis='Apply the previously retained EMA/volatility-only gate to all T11 weights. Describe drawdown change toward30%, CAGR and terminal wealth retention, Sharpe/Calmar and underwater tradeoffs. No tuning or claim of pure timing alpha.',gate=dict(variant='retained EMA/volatility only; dd input fixed zero',input='RAW SPY close rounded cents; seed2004-01-02 to2019-12-31; completed current session RAW history only; existing T11 Adjusted subscription untouched',rules='EMA50/200 adjustFalse;20-return sample volatility sqrt252; red>=40%; yellow trend nonpositive orvol>=25%; red recovery5days vol<35%; green recovery5days positive trend andvol<20%',caps=dict(green=1,yellow=.5,red=0,unassessed=0),timing='Close observer before unchanged funded MOO controller; cap changes alter weight intent; reductions first and buys staged. Not instant liquidation, no guarantee of30% loss bound.'),metrics='Existing identical full/annual returns, DD, Sharpe, Calmar, UW fraction/session/calendar duration and censored status; gate color counts/input hash; actual rejection, financing reconciliation and control parity',stops=['Five attempts or45minutes; at most2 technical-only retries','No financial threshold or signal tuning','Stop on identity, nonfiniteNAV or future/missinggate data; preserve failures'],sample='All inspected development history. Not untouched OOS. No half-exposure control, therefore no timing-alpha inference.')
    (ROOT/'research/plans'/f'{STUDY}.json').write_text(json.dumps(p,indent=2)+'\n')
    (RAW/'attempts.json').write_text(json.dumps(dict(study_id=STUDY,git_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),deadline_utc=p['deadline_utc'],status='active',attempts=[]),indent=2)+'\n')
    print(p['deadline_utc'],hashes)
if __name__=='__main__':prepare()
