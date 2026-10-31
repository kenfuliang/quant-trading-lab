#!/usr/bin/env python3
"""Audit the two saved official exports; no simulations, credentials or network."""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pandas as pd
from reporting.temporal import analyze_temporal
from research.studies.t11_reproduction.exports import inspect_export, annual_calmar_rounding_bound
from research.studies.t11_reproduction.reference import load_cells

CASES={'t11':('Calm Fluorescent Yellow Manatee','ae7d527233c8cec348ee4da07c9fe0eb'),
       'gated_t11':('Hipster Blue Owlet','96cee07260398f6cdb20c92b08bc50e5')}


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,obj):path.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')


def main():
    base=ROOT/'.local/t11-reference-v2'
    out=base/'export-review-v2'
    if out.exists():raise SystemExit('Review exists; preserve evidence and use a separately versioned review.')
    out.mkdir(mode=0o700)
    manifest={'created_utc':datetime.now(timezone.utc).isoformat(),'status':'started','new_financial_runs':0,
              'broker_orders':0,'files':{},'inputs':{},'code':{}}
    try:
        calendar=ROOT/'data/qualified/alpaca-sector-etfs-2016-2025-v1-issuer-v2/calendar.csv'
        if digest(calendar)!='b879d9287d1c61a5774f79d1c47a1767e88ed7358b6e29b83ce563ea89c22b49':raise ValueError('Frozen calendar changed.')
        sessions=[r['session'] for r in csv.DictReader(calendar.open()) if '2020-01-01'<=r['session']<='2025-12-31']
        manifest['inputs'][str(calendar.relative_to(ROOT))]=digest(calendar)
        for path in ['scripts/review_t11_reference_exports.py','research/studies/t11_reproduction/exports.py',
                     'research/studies/t11_reproduction/reference.py','reporting/temporal.py','tests/test_t11_exports.py']:
            manifest['code'][path]=digest(ROOT/path)
        result={}
        for case,(name,backtest_id) in CASES.items():
            raw=base/'exports'/f'{case}.json'
            source=Path('/Users/kenfuliang/Downloads')/(name+'.json')
            if source.read_bytes()!=raw.read_bytes():raise ValueError('Preserved export differs from supplied original.')
            ref_path=ROOT/f'.local/qc504-t11-gate-v1/{case}-summary-cells.json'
            references=load_cells(ref_path)
            reference=next(r for r in references if r.get('kind')=='overall')
            document=json.loads(raw.read_bytes())
            audit,rows=inspect_export(document,name=name,backtest_id=backtest_id,sessions=sessions,reference=reference)
            yearly={r['year']:r for r in references if r.get('kind')=='annual'}
            annual_checks={}
            precision_checks={}
            previous_opening=10000.
            for annual in audit['annual_legacy']:
                checks={}
                for key in ['n','end','ret','dd','sharpe','annual_calmar','uw','longest_uw','censored','return_sum','return_square_sum']:
                    a,b=annual[key],yearly[annual['year']][key]
                    tolerance=.01 if key=='end' else 1e-8
                    if key=='annual_calmar':
                        subset=[r for r in rows if r['session'].startswith(annual['year'])]
                        bound=annual_calmar_rounding_bound(subset,previous_opening,exact_opening=annual['year']=='2020')
                        precision_checks[annual['year']]={'strict_1e8_pass':abs(a-b)<=1e-8,'absolute_difference':abs(a-b),'propagated_rounding_bound':bound}
                        tolerance=max(tolerance,bound) if bound is not None else tolerance
                    checks[key]=a==b if isinstance(a,(bool,int)) or a is None else abs(a-b)<=tolerance
                annual_checks[annual['year']]=checks
                previous_opening=annual['end']
            audit['annual_reference_checks']=annual_checks
            audit['annual_calmar_precision']=precision_checks
            audit['annual_calmar_comparison']='quantization-compatible, not exact; v1 strict failures preserved'
            audit['all_annual_checks_passed']=all(all(x.values()) for x in annual_checks.values())
            anchored=pd.Series([10000.]+[r['nav_usd'] for r in rows],index=pd.to_datetime(['2019-12-31']+sessions))
            temporal,_=analyze_temporal(anchored,initial_capital=10000.)
            audit['temporal_v1_2']=temporal
            audit['export_sha256']=digest(raw)
            audit['official_statistics']=document['statistics']
            write(out/f'{case}-audit.json',audit)
            write(out/f'{case}-candidate-close-path.json',rows)
            if not audit['legacy_aggregate_comparison']['aggregate_match'] or not audit['all_annual_checks_passed']:
                raise ValueError('Compatibility mismatch; preserve and diagnose without tuning.')
            manifest['inputs'][str(raw.relative_to(ROOT))]=digest(raw)
            manifest['inputs'][str(ref_path.relative_to(ROOT))]=digest(ref_path)
            write(out/f'{case}-audit.json',audit)
            write(out/f'{case}-candidate-close-path.json',rows)
            result[case]=audit
        write(out/'comparison.json',result)
        manifest['status']='exports_and_aggregate_compatibility_verified_local_execution_still_blocked'
        print(json.dumps({case:{'metrics':r['metrics_legacy'],
                               'longest_episode_v1_2':r['temporal_v1_2']['longest_underwater_episode'],
                               'annual':[{k:a[k] for k in ['year','calendar_year_return','dd','sharpe','annual_calmar']} for a in r['annual_legacy']],
                               'annual_checks':r['all_annual_checks_passed'],'order_status_codes':r['status_code_counts']} for case,r in result.items()},indent=2))
    except Exception as exc:
        manifest['status']='failed_preserved'
        manifest['error_type']=type(exc).__name__
        raise
    finally:
        for path in out.glob('*.json'):
            if path.name!='manifest.json':manifest['files'][path.name]=digest(path)
        write(out/'manifest.json',manifest)


if __name__=='__main__':main()
