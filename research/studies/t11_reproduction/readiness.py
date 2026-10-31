"""Read registered saved files/AST only. Does not execute a strategy or request data."""
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from research.studies.t11_reproduction.reference import load_cells,compare_path

ROOT=Path(__file__).resolve().parents[3]
REQUIRED=tuple(sorted({'SPY','IOO','TQQQ','VTV','XLF','XLK','KMLM','PSQ','BND','QQQ','IEF','TLT','AGG','SH',
 'UVXY','BIL','BTAL','SPXL','TECL','SOXL','TECS','SOXS','SQQQ','QLD'}))


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect(root=ROOT):
    root=Path(root);plan_path=root/'research/plans/qc504-t11-gate-v1.json';old=json.loads(plan_path.read_text())
    cells=[];sources={};subscribed=None;paths={}
    for case in ('t11','gated_t11'):
        source=root/f'.local/qc504-t11-gate-v1/{case}-source.py'
        if digest(source)!=old['source_hashes'][case]:raise ValueError('Frozen original strategy changed.')
        tree=ast.parse(source.read_text())
        sources[case]={'path':str(source.relative_to(root)),'sha256':digest(source),'methods':{}}
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='QuadEnsemble')
        for node in cls.body:
            if isinstance(node,ast.FunctionDef) and (node.name.startswith('_t11') or node.name.startswith('_fund') or node.name.startswith('_gate')):
                sources[case]['methods'][node.name]=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
        for node in ast.walk(tree):
            if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='all_tickers' for t in node.targets):
                current=sorted(set(ast.literal_eval(node.value)))
                if subscribed is not None and subscribed!=current:raise ValueError('Reference subscription universes differ.')
                subscribed=current
        cp=root/f'.local/qc504-t11-gate-v1/{case}-summary-cells.json';records=load_cells(cp)
        overall=next(r for r in records if r.get('kind')=='overall')
        annual=[r for r in records if r.get('kind')=='annual']
        if len(annual)!=6 or {str(r['year']) for r in annual}!=set(map(str,range(2020,2026))):raise ValueError('Incomplete legacy annual summary.')
        cells.append({'case':case,'path':str(cp.relative_to(root)),'sha256':digest(cp),'overall':overall,'annual':annual})
        paths[case]=compare_path(overall,None)
    bundle_path=root/'data/qualified/alpaca-sector-etfs-2016-2025-v1-issuer-v2/inputs.json'
    bundle=json.loads(bundle_path.read_text());entry=bundle['files']['prices'];prices=root/entry['path']
    if digest(prices)!=entry['sha256']:raise ValueError('Qualified price bytes changed.')
    records=json.loads(prices.read_text());symbols=sorted({r['symbol'] for r in records})
    common=sorted(set(symbols)&set(REQUIRED));missing=sorted(set(REQUIRED)-set(symbols))
    return {'schema':'t11-reproduction-readiness-v1','observed_utc':datetime.now(timezone.utc).isoformat(),
        'status':'preparation_verified_financial_execution_ineligible','financial_runs':0,'new_downloads':0,
        'parent_plan':{'path':str(plan_path.relative_to(root)),'sha256':digest(plan_path)},
        'source_inspection':'static AST only; no third-party source executed, copied into tracked code or redistributed',
        'sources':sources,'saved_reference':cells,'daily_path_status':paths,
        'universe':{'decision_required':REQUIRED,'decision_required_count':len(REQUIRED),'source_subscribed':subscribed,'source_subscribed_count':len(subscribed),
            'qualified_common_symbols':common,'missing_decision_symbols':missing,'raw_gate_seed_2004_2019_qualified':False},
        'blockers':['No local original daily decision/order/NAV reference package; saved summaries cannot identify a unique path.',
            'Only SPY/XLK/XLF among24required decision symbols have scoped qualified local inputs; no qualified2004gate seed.',
            'Raw/adjusted normalization, reverse splits/cash-in-lieu and native fee/margin/staged-MOO parity not implemented.',
            'Legacy engine18209 differs from observed current cloud18215; no matching engine pin verified.',
            'Source modification/use and redistribution rights require scoped review; existing third-party source stays private.'],
        'next_gate':'Official built-in result/order exports and permitted data/engine route; no raw vendor export or optimization before parity.',
        'independent_alpha':False,'broker_operations':0,'financial_adapter_enabled':False}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
    result=inspect()
    with Path(args.output).open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'status':result['status'],'financial_runs':0,'missing_decision_symbols':len(result['universe']['missing_decision_symbols'])}))
