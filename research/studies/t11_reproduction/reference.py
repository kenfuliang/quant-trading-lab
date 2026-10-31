"""Pure readers and metric checks; summaries alone cannot establish daily parity."""
import hashlib
import json
import math
from datetime import date
from pathlib import Path
import statistics


def load_cells(path):
    data=json.loads(Path(path).read_text());rows=[json.loads(x) if isinstance(x,str) else x for x in data]
    if not isinstance(rows,list) or any(not isinstance(x,dict) for x in rows):raise ValueError('Summary cells must be objects.')
    if len([r for r in rows if r.get('kind')=='overall'])!=1:raise ValueError('Exactly one overall record required.')
    years=[r.get('year') for r in rows if r.get('kind')=='annual']
    if len(years)!=len(set(years)):raise ValueError('Duplicate annual summary.')
    for r in rows:
        for k,v in r.items():
            if isinstance(v,float) and not math.isfinite(v):raise ValueError('Nonfinite saved reference.')
    return rows


def legacy_metrics(rows,opening=10000.,anchor='2019-12-31'):
    """Compatibility evaluator: old duration excludes recovery close; not canonical v1.2."""
    if not rows or opening<=0:raise ValueError('Positive anchored path required.')
    days=[r['session'] for r in rows];values=[float(r['nav_usd']) for r in rows]
    if days!=sorted(set(days)) or days[0]<=anchor or any(not math.isfinite(v) or v<=0 for v in values):raise ValueError('Invalid daily path.')
    peak=previous=float(opening);peak_date=date.fromisoformat(anchor);dd=0.;underwater=run=longest=longest_days=0;returns=[]
    for d,v in zip(days,values):
        d=date.fromisoformat(d);returns.append(v/previous-1);previous=v
        if v>=peak:peak=v;peak_date=d;run=0
        else:run+=1;underwater+=1;longest=max(longest,run);longest_days=max(longest_days,(d-peak_date).days)
        dd=min(dd,v/peak-1)
    years=(date.fromisoformat(days[-1])-date.fromisoformat(anchor)).days/365.25
    if years<=0:raise ValueError('Positive elapsed period required.')
    cagr=(values[-1]/opening)**(1/years)-1;sd=statistics.stdev(returns) if len(returns)>1 else 0
    return {'n':len(rows),'end':values[-1],'ret':values[-1]/opening-1,'cagr':cagr,'dd':dd,
        'calmar':cagr/abs(dd) if dd<0 else None,'sharpe':statistics.mean(returns)/sd*math.sqrt(252) if sd>1e-15 else None,
        'uw':underwater,'uw_fraction':underwater/len(rows),'longest_uw':longest,'longest_uw_days':longest_days,'censored':values[-1]<peak,
        'return_sum':sum(returns),'return_square_sum':sum(r*r for r in returns),
        'calendar_hash':hashlib.sha256(''.join(d+'\n' for d in days).encode()).hexdigest()}


def compare_path(reference,rows,*,account_audit_passed=False,policy_audit_passed=False):
    if rows is None:return {'status':'daily_reference_missing','daily_parity':False,'financial_runs':0}
    actual=legacy_metrics(rows);checks={}
    for key,value in actual.items():
        if key not in reference:continue
        expected=reference[key]
        if isinstance(value,(str,bool,int)) or value is None:checks[key]=value==expected
        else:
            tolerance=.01 if key=='end' else 1e-8
            checks[key]=expected is not None and math.isfinite(float(expected)) and abs(value-float(expected))<=tolerance
    required={'n','end','cagr','dd','calmar','sharpe','longest_uw','longest_uw_days','calendar_hash'}
    matched=required<=checks.keys() and all(checks.values())
    return {'status':'aggregate_compatibility_match' if matched else 'aggregate_mismatch','checks':checks,
        'aggregate_match':matched,'daily_parity':False,
        'full_reproduction_eligible':False,'account_audit_reported':bool(account_audit_passed),'policy_audit_reported':bool(policy_audit_passed),
        'limitation':'Aggregate compatibility does not identify the original daily path. Exact daily NAV/order/decision reference comparison remains separate.','financial_runs':0}
