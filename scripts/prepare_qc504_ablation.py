"""Prepare private full-budget sleeve adapters and freeze a bounded hosted plan."""
import ast
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'.local/qc504-ablation-v1'
CASES=('ensemble','t10','t11','s2','s3')

def adapt(source, case):
    if case not in CASES:raise ValueError('Unknown case')
    tree=ast.parse(source)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='AUDIT_CASE' for t in node.targets):node.value=ast.Constant(case)
    if case!='ensemble':
        for node in cls.body:
            if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='QUARTER' for t in node.targets):node.value=ast.Constant(1.)
            if isinstance(node,ast.FunctionDef) and node.name in ['_'+c+'_weights' for c in CASES[1:] if c!=case]:node.body=ast.parse('return {}').body
    # New experiment identity, identical existing observers/metrics and order policy.
    for node in ast.walk(tree):
        if isinstance(node,ast.Constant) and node.value=='qc504-v1':node.value='qc504-ablation-v1'
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

def prepare():
    RAW.mkdir(parents=True,exist_ok=False)
    source=(ROOT/'.local/qc504-v1/cost25-source.py').read_text()
    frozen=datetime.now(timezone.utc)
    hashes={}
    for case in CASES:
        p=RAW/f'{case}-source.py';p.write_text(adapt(source,case));hashes[case]=hashlib.sha256(p.read_bytes()).hexdigest()
    plan=dict(study_id='qc504-ablation-v1',status='frozen-before-runs',created_utc=frozen.isoformat(),deadline_utc=(frozen+timedelta(minutes=40)).isoformat(),cases=list(CASES),max_financial_attempts=6,max_successful_cases=5,technical_repair_slots=1,start='2020-01-01',end='2025-12-31',capital_usd=10000,slippage_per_fill=.0025,fees_and_financing='Original IB margin/fee defaults; no added funding model. Financing not qualified.',allocation='Standalone selected sleeve QUARTER=1.0; other weight methods return empty. Ensemble unchanged QUARTER=.25. Same full portfolio budget; embedded exposure varies.',order_policy='Original close-price whole-share sizing and next-open MOO, trade on signal-label change; no cash buffer or rejection repair.',source='Original private clone #504 v1.1.0; frozen previous cost25 adapter',source_hashes=hashes,input_hash=hashlib.sha256(source.encode()).hexdigest(),metrics='Annual/full returns, closing DD, zero-RF daily sample Sharpe sqrt252, Calmar, carried-peak underwater fraction, longest sessions/calendar days and censoring; exposure/cash/fees/rejects.',hypothesis='Ensemble improves downside-adjusted performance or recovery relative to best-return standalone; reject a universal superiority claim if any sleeve dominates across metrics. No unseen alpha test.',ranking='Report raw metrics/Pareto tradeoffs; order-rejected cases conditional, missing evidence unranked. No tuned parameters after viewing.',stops=['Six total financial attempts or40-minute deadline','source/case identity mismatch','nonfinite/nonpositive NAV','missing result retained; technical-only retry within cap'],exports='Aggregate summary metrics/P&L only; no raw/daily market data; private source retained, no publication/broker/order actions')
    (ROOT/'research/plans/qc504-ablation-v1.json').write_text(json.dumps(plan,indent=2)+'\n')
    (RAW/'attempts.json').write_text(json.dumps(dict(study_id=plan['study_id'],deadline_utc=plan['deadline_utc'],attempts=[],status='active'),indent=2)+'\n')
    print(json.dumps(dict(deadline=plan['deadline_utc'],hashes=hashes),indent=2))
if __name__=='__main__':prepare()
