"""Freeze/reserve/record a single nine-case hosted factorial, coordinator only."""
from pathlib import Path
import argparse
import ast
from datetime import datetime, timezone, timedelta
import hashlib
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research.capm_ablation import STUDY, CASES, COSTS, build_source,decode_fragments,audit_records
ROOT=Path('.local')/STUDY
PLAN=Path('research/plans')/(STUDY+'.json')


def save(p,value):
    p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(p)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['freeze','reserve','record','close']);ap.add_argument('--case',choices=list(CASES));ap.add_argument('--status');ap.add_argument('--backtest');ap.add_argument('--project',type=int);a=ap.parse_args();now=datetime.now(timezone.utc)
    if a.action=='freeze':
        if PLAN.exists() or (ROOT/'budget.json').exists():raise ValueError('Preserve existing study')
        ROOT.mkdir(parents=True,exist_ok=True);hashes={}
        for case in CASES:
            source=build_source(case);(ROOT/(case+'-source.py')).write_text(source);hashes[case]=hashlib.sha256(source.encode()).hexdigest()
        inputs=['research/quantconnect/capm_study.py','research/quantconnect/sector_metrics.py','research/quantconnect/sources/capm_framework_original.py','research/capm_ablation.py','research/capm_review.py']
        plan=dict(study_id=STUDY,status='frozen-before-financial-runs',created_utc=now.isoformat(),deadline_utc=(now+timedelta(minutes=90)).isoformat(),project_id=a.project,cases={k:dict(strategy=v[0],cost_mode=v[1],stop_enabled=v[2]) for k,v in CASES.items()},cost_levels=COSTS,primary_cases=9,max_total_attempts=11,technical_retry_slots=2,source_hashes=hashes,input_hashes={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in inputs},context=dict(start='2016-01-01',end='2025-12-31',capital_usd=300000,cash_buffer=.01,universe='Unchanged29 legacy source symbols and manually subscribed SPY; same reverse regression21bar/top2 monthly and source framework except declared stop factor.',execution='Native minute ImmediateExecution/equal-weight source models; SPY entry-only. Same native minimum-order policy. Default normalization and native bid/ask fills retained.',financing='Unchanged6% debit ACT/360 on previous closing cash; zero credit; disable native per-security interest.',costs='zero: ConstantFeeModel(0),0 added slippage; fees: nativeIB commissions,0 added slippage; stress: nativeIB commissions,25bp added slippage. Native quote spreads remain in every level; zero is not a frictionless market.',risk='Only CAPM per-security1% source model versus NullRiskManagementModel. SPY no stop at every level.',metrics='Same full/annual returns, closing drawdown, zeroRF sample daily Sharpe sqrt252, fullCAGR/absDD and annualreturn/absDD Calmar; UWfraction, longest sessions/calendar days and terminal censoring. Annual peaks reset; full peak carries.',data='Reuse free hosted US equity/quote/action data, same observed enginev18209; aggregate outputs only, no dense market/NAV export.'),hypotheses=['Stop effect differs by cost level; the large prior loss may reflect repeated re-entry and costs.','No-stop may reduce turnover but expose larger price losses; no presumption of better risk.'],contrasts='Stop-on minus off at each level; commissions effect fees-minus-zero; added-slippage effect stress-minus-fees; interaction(stop effect at stress)-(stop effect at zero), full and annual. These are total closed-loop policy effects, not same-trade fee subtraction.',primary_estimand='Full-period CAGR contrasts and total-cost×stop interaction; DD/Calmar/Sharpe/UW/exposure/turnover are joint diagnostics. No threshold or winner-based tuning.',controls='Nine fresh cases, no cache reuse. c25_on ands25 must reproduce prior audited11 metric records before qualification. Six CAPM monthly selection hashes must match.',history='Viewed development history, no untouched OOS, no trained advantage or promotion.',stops=['11attempts including failures,90minute deadline,at most2technical retries; no widening or threshold changes.','First c25_on must pass dependency/native-book/configuration checks and reproduce earlier metrics before other cases.','Stop/flag missing periods, wrong source token/case/model,nonpositiveNAV,accounting failures,calendar/selection differences,paid access or version drift.','Preserve failed attempts. No paid data/services/broker operations/real orders/dependency installations/commits/publication.'])
        save(PLAN,plan);save(ROOT/'budget.json',dict(study=STUDY,status='active',attempts=[]));print(json.dumps({'plan':str(PLAN),'deadline':plan['deadline_utc'],'source_count':len(hashes)}));return
    plan=json.loads(PLAN.read_text());ledger=json.loads((ROOT/'budget.json').read_text())
    if a.action=='reserve':
        if ledger['status']!='active' or now>datetime.fromisoformat(plan['deadline_utc']):raise ValueError('Closed/expired budget')
        if not a.case:raise ValueError('Case required')
        if ledger['attempts'] and ledger['attempts'][-1]['status']=='reserved':raise ValueError('Prior attempt not recorded')
        if len(ledger['attempts'])>=plan['max_total_attempts']:raise ValueError('Attempt cap')
        repeats=sum(max(0,sum(t['case']==c for t in ledger['attempts'])-1) for c in CASES)
        if any(t['case']==a.case for t in ledger['attempts']) and repeats>=plan['technical_retry_slots']:raise ValueError('Repair cap')
        if a.case!='c25_on' and not (ROOT/'control-gate.json').exists():raise ValueError('Reference gate missing')
        for p,digest in plan['input_hashes'].items():
            if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=digest:raise ValueError('Input drift:'+p)
        digest=hashlib.sha256((ROOT/(a.case+'-source.py')).read_bytes()).hexdigest()
        if digest!=plan['source_hashes'][a.case]:raise ValueError('Source drift')
        ledger['attempts'].append(dict(id=len(ledger['attempts'])+1,case=a.case,status='reserved',source_sha256=digest,reserved_utc=now.isoformat()))
    elif a.action=='record':
        row=ledger['attempts'][-1]
        if row['case']!=a.case or row['status']!='reserved':raise ValueError('Record identity/state')
        rows=None
        if a.status=='completed':
            rows=decode_fragments(json.loads((ROOT/(a.case+'-fragments.json')).read_text()),a.case)
            audit=audit_records(rows,a.case);save(ROOT/(a.case+'-summary.json'),rows);save(ROOT/(a.case+'-audit.json'),audit)
            if a.case in ['c25_on','s25']:
                parent='capm' if a.case=='c25_on' else 'spy'
                prior=json.loads((Path('.local/capm-spy-v1')/(parent+'-summary.json')).read_text())
                if any(x['metrics']!=y['metrics'] for x,y in zip(prior,rows)) or len(prior)!=len(rows):raise ValueError('Prior control did not reproduce')
                if a.case=='c25_on':save(ROOT/'control-gate.json',dict(passed=True,all11metricrecords_exactly_equal=True))
        row.update(status=a.status,backtest_id=a.backtest,recorded_utc=now.isoformat())
    else:
        if ledger['attempts'] and ledger['attempts'][-1]['status']=='reserved':raise ValueError('Record pending attempt first')
        ledger.update(status='closed',closed_utc=now.isoformat())
    save(ROOT/'budget.json',ledger);print(json.dumps(ledger['attempts'][-1] if a.action!='close' else {'closed':True,'attempts':len(ledger['attempts'])}))

if __name__=='__main__':main()
