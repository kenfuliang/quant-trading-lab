"""Fixed local adapter: reserve before launch, seal once, cached restarts read-only.

Generic RSI registry is unchanged. Synthetic lifecycle probes share a six-launch
controller; real cases share one exact eight-case plan and one writer.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from research.research_controller import ResearchController
from research.studies.sector_gate.model import CASES,write_json

ROOT=Path(__file__).resolve().parents[3]
FINANCIAL_ROOT=ROOT/'.local/sector-gate-v1/financial'
PROOF_ROOT=ROOT/'.local/sector-gate-v1/qualification'
DEADLINE='2026-10-29T02:00:00+00:00'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def objhash(x):return hashlib.sha256(canonical(x).encode()).hexdigest()

def atomic(path,data):
    path=Path(path);temporary=path.with_name(path.name+'.tmp')
    with temporary.open('w') as f:f.write(json.dumps(data,indent=2,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
    os.replace(temporary,path)

def verify_manifest(root):
    root=Path(root);manifest=json.loads((root/'manifest.json').read_text())
    files={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p!=root/'manifest.json'}
    if files!=set(manifest['files']):raise ValueError('Unexpected/missing sealed artifact.')
    for name,digest in manifest['files'].items():
        if sha(root/name)!=digest:raise ValueError('Sealed artifact changed: '+name)
    return manifest

def seal(root,identity):
    root=Path(root)
    files={str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file() and p!=root/'manifest.json'}
    write_json(root/'manifest.json',{'identity':identity,'sealed_utc':now(),'files':files})

def verify_plan(path):
    plan=json.loads(Path(path).read_text());mode=plan['mode']
    if plan['python']!=sys.executable:raise ValueError('Interpreter identity changed.')
    if sha(sys.executable)!=plan['python_sha256']:raise ValueError('Interpreter bytes changed.')
    for name,digest in plan['sources'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Frozen runtime source changed: '+name)
    if mode=='financial':
        if Path(plan['output_root']).resolve()!=FINANCIAL_ROOT or Path(plan['journal_root']).resolve()!=FINANCIAL_ROOT/'journal':raise ValueError('Unregistered financial root.')
        if plan['program_id']!='sector-gate-v1-20261028' or plan['cases']!=list(CASES):raise ValueError('Unregistered cases or program.')
        if (plan['attempt_cap'],plan['case_seconds'],plan['aggregate_seconds'],plan['deadline'])!=(6,300,1800,DEADLINE):raise ValueError('Financial bounds changed.')
        if plan['workers']!=1 or plan['automatic_retries']!=0:raise ValueError('Concurrency/retry bounds changed.')
        if plan['start']!='2017-02-01' or plan['end']!='2025-12-31':raise ValueError('Financial dates changed.')
        for item in plan['input_files'].values():
            if sha(ROOT/item['path'])!=item['sha256']:raise ValueError('Frozen input evidence changed.')
        bundle=json.loads((ROOT/plan['bundle']).read_text());sources=json.loads((ROOT/plan['input_source_manifest']).read_text())
        for item in bundle['files'].values():
            if sha(ROOT/item['path'])!=item['sha256']:raise ValueError('Qualified input changed.')
        for name,digest in bundle['code'].items():
            if sha(ROOT/name)!=digest:raise ValueError('Qualified action model changed.')
        for name,digest in sources['files'].items():
            if sha(ROOT/name)!=digest:raise ValueError('Qualified source changed.')
        for r in bundle['split_reviews'].values():
            if sha(r['source_path'])!=r['source_sha256']:raise ValueError('Issuer split form changed.')
        proof=json.loads((ROOT/plan['qualification']).read_text())
        if proof['status']!='passed' or proof['financial_runs']!=0 or proof['code_sources']!=plan['sources']:raise ValueError('Execution qualification missing/mismatched.')
    elif mode=='synthetic':
        if plan['program_id'] not in ('proof-a','proof-b','proof-failure','proof-timeout'):raise ValueError('Unregistered synthetic fixture.')
        if plan['cases']!=['fixture'] or plan['attempt_cap']!=6 or plan['aggregate_seconds']!=120:raise ValueError('Synthetic bounds changed.')
        if Path(plan['journal_root']).resolve()!=PROOF_ROOT/'shared-journal':raise ValueError('Synthetic shared budget missing.')
        if not Path(plan['output_root']).resolve().is_relative_to(PROOF_ROOT):raise ValueError('Synthetic output outside proof root.')
    else:raise ValueError('Unsupported execution mode.')
    return plan

def reservation_guard(plan_path,case,attempt):
    plan=verify_plan(plan_path)
    snapshot=json.loads((Path(plan['journal_root'])/'snapshot.json').read_text());events=(Path(plan['journal_root'])/'events.jsonl').read_text().splitlines()
    head='0'*64
    for i,line in enumerate(events,1):
        row=json.loads(line);body={k:row[k] for k in ('sequence','previous_hash','event')}
        if row['sequence']!=i or row['previous_hash']!=head or row['event_hash']!=objhash(body):raise ValueError('Invalid reservation journal chain.')
        head=row['event_hash']
    if snapshot['sequence']!=len(events) or snapshot['head_hash']!=head:raise ValueError('Reservation snapshot stale.')
    state=snapshot['state'];record=state['attempts'].get(attempt)
    spec={'plan_sha256':sha(plan_path),'case':case,'program':plan['program_id']}
    if not record or record['status']!='reserved' or record['action']['observation_spec']!=spec:raise ValueError('Live exact-case reservation required.')
    if case not in plan['cases'] or datetime.now(timezone.utc)>=datetime.fromisoformat(plan['deadline']):raise ValueError('Case not eligible or deadline elapsed.')
    return plan

def child(plan_path,case,attempt):
    plan=reservation_guard(plan_path,case,attempt);output=Path(plan['output_root'])/'cases'/case
    print(json.dumps({'child_started_utc':now(),'case':case,'mode':plan['mode']}),flush=True)
    if plan['mode']=='synthetic':
        from research.sector_corporate_actions import ActionLedger
        output.mkdir(parents=True,exist_ok=False);write_json(output/'partial.json',{'synthetic_fixture':True})
        if plan['program_id']=='proof-timeout':time.sleep(2)
        if plan['program_id']=='proof-failure':raise RuntimeError('Intentional synthetic capture failure.')
        ledger=ActionLedger([],capital='1000',symbols=('SPY',));ledger.before_open('2020-01-02');ledger.fill('SPY',3,'100');nav=ledger.close('2020-01-02',{'SPY':100})
        if str(nav)!='999':raise AssertionError('Synthetic account mismatch.')
        write_json(output/'result.json',{'synthetic_fixture':True,'nav':str(nav),'financial_slots':0})
    else:
        from research.studies.sector_gate.model import load_inputs,save_case
        from research.studies.sector_gate.audit import replay
        policy,bps=case.split('-');frames,actions=load_inputs(ROOT/plan['bundle'])
        save_case(output,frames,actions,policy,int(bps))
        proof=replay(ROOT/plan['bundle'],output,policy,int(bps))
        write_json(output/'independent-audit.json',proof)
    write_json(output/'child-completion.json',{'case':case,'mode':plan['mode'],'completed_utc':now(),'plan_sha256':sha(plan_path),'reservation':attempt})
    seal(output,{'case':case,'plan_sha256':sha(plan_path)})
    print(json.dumps({'child_completed_utc':now(),'case':case}),flush=True)


def execute(plan_path):
    plan_path=Path(plan_path).resolve();plan=verify_plan(plan_path);root=Path(plan['output_root']);identity=sha(plan_path)
    if (root/'manifest.json').exists():
        manifest=verify_manifest(root)
        if manifest['identity']['plan_sha256']!=identity:raise ValueError('Cached plan identity differs.')
        receipt=json.loads((root/'final-receipt.json').read_text())
        if receipt['status']!='completed':raise ValueError('Failed program closed; automatic retry forbidden.')
        return {'status':'cached_verified','new_launches':0,'financial_slots':0}
    if root.exists():raise ValueError('Unsealed/ambiguous output; reconcile manually, never relaunch.')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(plan['deadline']):raise ValueError('Deadline elapsed; no launch.')
    root.mkdir(parents=True,exist_ok=False);(root/'captures').mkdir();(root/'source-snapshot').mkdir()
    shutil.copyfile(plan_path,root/'frozen-plan.json')
    for name in plan['sources']:
        target=root/'source-snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    context={'score_version':'sector-gate-capture-v1','frozen_identity':identity} if plan['mode']=='financial' else plan['shared_context']
    budget={'max_attempts':plan['attempt_cap'],'max_resource_units':plan['attempt_cap'],'resource_unit':'financial_case' if plan['mode']=='financial' else 'synthetic_child','max_active_branches':1}
    records=[];status='completed';wall=0.
    with ResearchController(plan['journal_root'],context=context,budget=budget) as controller:
        if any(x['status']=='reserved' for x in controller.state['attempts'].values()):raise ValueError('Outstanding ambiguous reservation; no relaunch.')
        if plan['mode']=='financial' and controller.usage()['attempts']:raise ValueError('Existing financial attempts cannot restart.')
        q=plan['program_id'];controller.register_question('question-'+q,q,{'scope':q,'plan_sha256':identity,'estimand':'Fixed sector comparison' if plan['mode']=='financial' else 'Synthetic capture lifecycle'})
        controller.register_branch('branch-'+q,branch_id=q,question_id=q,mechanism='fixed-account-capture')
        for case in plan['cases']:
            remaining=min(plan['aggregate_seconds']-wall,(datetime.fromisoformat(plan['deadline'])-datetime.now(timezone.utc)).total_seconds())
            if remaining<=0:raise ValueError('Aggregate deadline exhausted before reservation.')
            if plan['mode']=='synthetic':
                prior=sum(x['outcome'].get('wall_seconds',0) for x in controller.state['attempts'].values() if x.get('outcome'))
                remaining=min(remaining,120-prior)
                if remaining<=0:raise ValueError('Synthetic aggregate wall exhausted.')
            action={'id':q+'-'+case,'branch_id':q,'question_id':q,'context_id':controller.context_id,
                'observation_key':case,'observation_spec':{'plan_sha256':identity,'case':case,'program':q},'class':2,'decision_value':1,
                'shared_questions':[],'cost_upper_bound':1,'evidence':[identity],
                'witness':[{'observation':'captured and audited outcome','decision':'record acceptance or rejection'}]}
            reserved=controller.select('reserve-'+q+'-'+case,action);attempt=reserved['attempt_id']
            record={'case':case,'attempt_id':attempt,'reserved_utc':now(),'status':'reserved','plan_sha256':identity}
            records.append(record);atomic(root/'capture.json',records)
            command=[sys.executable,'-m','research.studies.sector_gate.capture','--child',str(plan_path),case,attempt]
            record['command']=command;record['launch_intent_utc']=now();atomic(root/'capture.json',records)
            start=time.monotonic();process=None
            try:
                with (root/'captures'/f'{case}.stdout').open('xb') as stdout,(root/'captures'/f'{case}.stderr').open('xb') as stderr:
                    process=subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr)
                    record.update(pid=process.pid,started_utc=now());atomic(root/'capture.json',records)
                    try:code=process.wait(timeout=min(plan['case_seconds'],remaining))
                    except subprocess.TimeoutExpired:
                        process.kill();process.wait(timeout=5);code=process.returncode;record['timed_out']=True
                if code==0:verify_manifest(root/'cases'/case)
            except Exception as error:
                if process and process.poll() is None:process.kill();process.wait(timeout=5)
                code=process.returncode if process else None;record['capture_error_type']=type(error).__name__
                if code==0:code=1
            elapsed=time.monotonic()-start;wall+=elapsed
            success=code==0 and not record.get('capture_error_type') and elapsed<=min(plan['case_seconds'],remaining)+.1
            record.update(status='completed' if success else 'failed',exited_utc=now(),exit_code=code,wall_seconds=elapsed,
                financial_slots=1 if plan['mode']=='financial' else 0)
            atomic(root/'capture.json',records)
            controller.record('record-'+q+'-'+case,attempt,{'status':record['status'],'summary':'Child captured and sealed' if success else 'Child/capture failed; stop, no retry',
                'evidence':[str(root/'captures'/f'{case}.stdout'),str(root/'captures'/f'{case}.stderr')],
                'actual_resource_units':1,'wall_seconds':elapsed,'inspection_trace':['reserved before Popen','captured stdout/stderr and return','verified child artifact manifest' if success else 'preserved failed/partial artifacts'],
                'observation_kind':'fresh_simulation' if plan['mode']=='financial' else 'synthetic_fixture','resolutions':[]})
            if not success:status='failed';break
        controller.set_branch('retire-'+q,branch_id=q,status='retired',reason='fixed program closed '+status,evidence=[str(root/'capture.json')])
        usage=controller.usage();shutil.copytree(Path(plan['journal_root']),root/'journal-asof')
    write_json(root/'final-receipt.json',{'status':status,'program_id':plan['program_id'],'mode':plan['mode'],'plan_sha256':identity,
        'completed_utc':now(),'records':records,'journal_usage_asof':usage,'wall_seconds':wall,
        'financial_slots':sum(r['financial_slots'] for r in records),'automatic_retries':0})
    seal(root,{'plan_sha256':identity,'program_id':plan['program_id']})
    return {'status':status,'new_launches':len(records),'financial_slots':sum(r['financial_slots'] for r in records)}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--child',nargs=3);parser.add_argument('--execute');args=parser.parse_args()
    if args.child:child(*args.child)
    elif args.execute:
        result=execute(args.execute);print(json.dumps(result));raise SystemExit(0 if result['status'] in ('completed','cached_verified') else 1)
    else:parser.error('explicit fixed plan required')
