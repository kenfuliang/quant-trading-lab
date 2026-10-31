#!/usr/bin/env python3
"""Explicit epoch3 synthetic qualification / plan freeze; never starts a backtest.

--qualify launches exactly four bounded synthetic subprocess fixtures. --freeze
only validates identities and writes a new immutable registered financial plan.
Historical execution requires a separate explicit capture --execute command.
"""
import argparse
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research.studies.sector_rsi import capture as c


def code_sources():
    parent=json.loads((ROOT/'.local/sector-gate-v1/financial/frozen-plan.json').read_text())
    files=list(parent['sources'])
    files += ['research/studies/sector_rsi/'+n for n in
              ('__init__.py','model.py','signals.py','audit.py','capture.py','review.py')]
    files += ['tests/test_sector_rsi.py','tests/test_sector_rsi_capture.py','scripts/freeze_calmar_epoch3.py']
    return {name:c.sha(ROOT/name) for name in files}


def qualify():
    sources=code_sources();q=c.PROOF_ROOT
    if q.exists():raise ValueError('Qualification root already exists; inspect preserved output, never blindly restart.')
    q.mkdir(parents=True)
    cutoff=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat()
    outputs=[]
    for name in ('proof-a','proof-b','proof-failure','proof-timeout'):
        plan={'mode':'synthetic','python':sys.executable,'python_sha256':c.sha(sys.executable),
              'sources':sources,'program_id':name,'cases':['fixture'],'attempt_cap':6,
              'case_seconds':.8 if name=='proof-timeout' else 10,'aggregate_seconds':120,
              'deadline':cutoff,'journal_root':str(q/'shared-journal'),'output_root':str(q/name),
              'shared_context':{'score_version':'epoch3-synthetic-capture','identity':c.objhash(sources)}}
        path=q/(name+'.json');c.write_json(path,plan)
        result=c.execute(path)
        expected='failed' if name in ('proof-failure','proof-timeout') else 'completed'
        if result['status']!=expected:raise ValueError('Synthetic lifecycle expectation failed: '+name)
        result['program_id']=name;outputs.append(result)
        if expected=='completed':
            before={str(p):c.sha(p) for p in (q/name).rglob('*') if p.is_file()}
            if c.execute(path)['new_launches']!=0:raise ValueError('Cached check relaunched child')
            if before!={str(p):c.sha(p) for p in (q/name).rglob('*') if p.is_file()}:raise ValueError('Cached check mutated evidence')
        else:
            try:c.execute(path)
            except ValueError:pass
            else:raise ValueError('Failed probe allowed a retry')
    timeout=json.loads((q/'proof-timeout/final-receipt.json').read_text())
    if not timeout['records'][0].get('timed_out'):raise ValueError('Timeout was not observed')
    snapshot=json.loads((q/'shared-journal/snapshot.json').read_text())
    if len(snapshot['state']['attempts'])!=4:raise ValueError('Synthetic shared allowance mismatch')
    proof={'status':'passed','financial_runs':0,'code_sources':sources,'synthetic_launches':4,
           'synthetic_cap':6,'unused_synthetic_slots_retired':2,'programs':outputs,
           'completed_utc':c.now(),'failure_and_timeout_preserved':True,'cache_checks_read_only':True}
    c.write_json(q/'qualified.json',proof)
    return proof


def freeze(cycle):
    program=json.loads(c.PROGRAM.read_text())
    if datetime.now(timezone.utc)>=datetime.fromisoformat(program['deadline_utc']):raise ValueError('Epoch deadline expired')
    sources=code_sources();q=c.PROOF_ROOT/'qualified.json';proof=json.loads(q.read_text())
    if proof['status']!='passed' or proof['financial_runs']!=0 or proof['code_sources']!=sources:
        raise ValueError('Source-bound synthetic proof missing or changed')
    parent=json.loads((ROOT/'.local/sector-gate-v1/financial/frozen-plan.json').read_text())
    # Verify saved parent artifacts, without invoking the expired parent adapter.
    c.verify_manifest(ROOT/'.local/sector-gate-v1/financial')
    output=c.EPOCH_ROOT/cycle;output.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(ROOT/'docs/tasks/2026-10-30-calmar-epoch3.md',output/'protocol-before.md')
    shutil.copyfile(ROOT/'docs/leaderboard.md',output/'leaderboard-before.md')
    plan={'schema':'sector-rsi-epoch3-execution/v1','mode':'financial',
          'program_id':'calmar-epoch3-'+cycle,'python':sys.executable,'python_sha256':c.sha(sys.executable),
          'epoch_program_sha256':c.sha(c.PROGRAM),'sources':sources,
          'shared_context':{'score_version':'calmar-epoch3-v1','epoch_program_sha256':c.sha(c.PROGRAM)},
          'output_root':str(output/'financial'),'journal_root':str(c.FINANCIAL_JOURNAL),
          'cases':c.REGISTERED_CASES['calmar-epoch3-'+cycle],'attempt_cap':12,
          'case_seconds':300,'aggregate_seconds':1800,'deadline':c.DEADLINE,'workers':1,'automatic_retries':0,
          'start':'2017-02-01','end':'2025-12-31','bundle':parent['bundle'],
          'input_source_manifest':parent['input_source_manifest'],'qualification':str(q.relative_to(ROOT)),
          'input_files':{},'baseline_references':{},'frozen_utc':c.now(),
          'scientific_criteria':'10pct Calmar lift at both costs; no worse growth, drawdown or UW; no simpler-control domination; viewed development only',
          'stage_change':'correlation-aware target selection' if cycle=='c1' else 'fixed-sector breadth market conditions'}
    for name in (parent['bundle'],parent['input_source_manifest'],str(q.relative_to(ROOT)),
                 str((output/'protocol-before.md').relative_to(ROOT)),str((output/'leaderboard-before.md').relative_to(ROOT))):
        plan['input_files'][name]={'path':name,'sha256':c.sha(ROOT/name)}
    for b in (5,10):
        plan['baseline_references'][str(b)]={n:c.sha(ROOT/f'.local/sector-gate-v1/financial/cases/gate-{b}'/n)
            for n in ('ledger.csv','trades.csv','summary.json','selections.json','contributions.csv')}
    if cycle=='c2':
        previous=c.EPOCH_ROOT/'c1-review/decision.json'
        if json.loads(previous.read_text())['fixed_target_passed']:raise ValueError('Candidate already passed; stop epoch')
        plan['previous_cycle_review_sha256']=c.sha(previous)
    path=ROOT/f'research/plans/calmar-epoch3-{cycle}.frozen.json';c.write_json(path,plan);c.verify_plan(path)
    return {'status':'frozen_verified','path':str(path.relative_to(ROOT)),'sha256':c.sha(path),'cases':len(plan['cases'])}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--qualify',action='store_true');group.add_argument('--freeze',choices=('c1','c2'))
    args=parser.parse_args();result=qualify() if args.qualify else freeze(args.freeze)
    print(json.dumps({k:v for k,v in result.items() if k!='code_sources'}))
