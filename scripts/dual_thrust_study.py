"""Bounded fallback coordinator; aggregate task limits include the failed G-Score probe."""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import hashlib
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research.studies.checkpoint_20261031.dual_thrust_study import STUDY,CASES,build_source,decode_fragments,audit_records
ROOT=Path('.local')/STUDY;PLAN=Path('research/plans')/(STUDY+'.json')
PARENT=Path('.local/gscore-spy-v1/budget.json')


def save(p,v):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['freeze','reserve','record','close']);ap.add_argument('--case',choices=CASES);ap.add_argument('--status');ap.add_argument('--backtest');ap.add_argument('--project',type=int);a=ap.parse_args();now=datetime.now(timezone.utc)
    if a.action=='freeze':
        if PLAN.exists() or (ROOT/'budget.json').exists():raise ValueError('Preserve existing study')
        parent=json.loads(PARENT.read_text());initial=json.loads(Path('research/plans/gscore-spy-v1.json').read_text())
        if parent['status']!='closed' or len(parent['attempts'])!=1:raise ValueError('Parent not sealed at one failed probe')
        inputs=['research/dual_thrust_study.py','scripts/dual_thrust_study.py','research/quantconnect/sources/dual_thrust_fx_original.py','research/quantconnect/sources/LICENSE-JeSuisTM.txt','research/quantconnect/capm_study.py','research/quantconnect/sector_metrics.py','research/capm_review.py']
        ROOT.mkdir(parents=True,exist_ok=True);hashes={}
        for c in CASES:
            s=build_source(c);(ROOT/(c+'-source.py')).write_text(s);hashes[c]=hashlib.sha256(s.encode()).hexdigest()
        p=dict(study=STUDY,status='frozen-before-financial-runs',created_utc=now.isoformat(),deadline_utc=initial['deadline_utc'],expected_engine='2.5.0.0.18209',project_id=a.project,cases=CASES,max_total_attempts=5,technical_retry_slots=2,aggregate_task_max_attempts=6,parent_budget_path=str(PARENT),parent_budget_sha256=hashlib.sha256(PARENT.read_bytes()).hexdigest(),source_hashes=hashes,input_hashes={f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in inputs},fallback='G-score blocked after one zero-order probe by retired quarterly ROA and known legacy ratio-date look-ahead. No G-score financial outcome observed. Same aggregate6attempt ceiling and original90minute deadline; new candidate frozen before its outcomes.',source=dict(tutorial_id='QC-T-15258',package='dual-thrust-fx',repo='je-suis-tm/quant-trading',revision='611b73f2c3f577ac5b28aaa19ac8c43d3236c7a5',path='Dual Thrust backtest.py',license='Apache2.0 repository grant preserved with source.',defect='min2day rolling range includes the current session; signal_generation reads it at the session open. Causal adaptation lags to five fully completed prior sessions.'),context=dict(window=['2016-01-01','2025-12-31'],seed=['2015-12-21','2015-12-31'],capital_usd=300000,algorithm='SPY regular-session upper/lower=first observed minute open ±0.5*max(HH-LC,HC-LL) over previous5completed regular sessions only. Completed-minute close >upper targets+98%; <lower targets-98%; inside band retain direction. Execute prior decision at next minute; reset and liquidate5min before actual session close, including early closes.',control='spy: one98% purchase after first2016minute decision, nextminute fill, hold; intraday:98% long from same nextminute entry every session until5min before actual close. Same market-data clock/fees/financing, no forced terminal liquidation for hold.',cost='Native IB commissions + fixed5bp slippage per fill with native bid/ask/fills. Assumptions, not observed execution or capacity.',funding='6% ACT/360 on prior closing negative cash, zero credit; native per-security interest disabled. Short borrow at fixed3% ACT/365 accrued using previous-minute short notional and elapsed seconds; unrestricted simulated SPY availability assumed, not verified historical locates. No overnight short/dividend exposure permitted.',data='Existing free hosted SPY minute equity/quote/action feed; no fundamental or paid inputs, new downloads/installs/services. Seed is never traded. Only own metrics/counts/hashes exported; dense prices/NAV remain hosted.',metrics='Same full/annual return, closing DD, zeroRF sample daily Sharpe sqrt252, fullCAGR/absDD and annualreturn/absDD Calmar, UWfraction, longest sessions/calendar days and terminal censoring. Additional full minute-mark DD, mean/max minute gross and long/short minute counts because closing gross is zero for intraday cases.'),hypothesis='A causal symmetric opening-range breakout improves net growth/risk tradeoff beyond holding SPY and a same-session long control.',primary_estimand='Dual full net CAGR minus SPY CAGR; intraday-control excess CAGR and risk/temporal measures are joint diagnostics.',decision_rule='Retain only for further validation if dual CAGR>SPY, Calmar>=SPY, longestUW<=SPY and CAGR>intraday control; otherwise do not call it an improvement or retune. Intraday/closing DDabove30% flags reassessment; no promotion/annual-doubling claim.',data_gate='Prior CAPM free-SPY data probe/financial audits established hosted access. Fresh SPY control must pass native accounting/calendar plus2514five-prior-session readiness checks before candidate/control variants. All3range/calendar hashes and minute counts must match.',history='Viewed2016-2025development history; no fitting, unseen holdout, strategy/cost grid or trained RL advantage.',stops=['Aggregate6attempts includes closed G-score1; fallback at most5attempts for3cases+2technical retries, original deadline unchanged.','Reserve before launch; stop/flag source/build/version drift, wrong calendar/range, rejected/pending orders, nonpositiveNAV, any unplanned overnight position or accounting failures.','No paid resources, broker/account operations, live/paper orders, dependencies, new services, MLflow import, agents, commits or publication.'],negative_baseline=initial['negative_baseline'])
        save(PLAN,p);save(ROOT/'budget.json',dict(study=STUDY,status='active',attempts=[]));print(json.dumps(dict(plan=str(PLAN),deadline=p['deadline_utc'],aggregate_attempts_already_used=1)));return
    p=json.loads(PLAN.read_text());b=json.loads((ROOT/'budget.json').read_text());parent=json.loads(PARENT.read_text())
    if hashlib.sha256(PARENT.read_bytes()).hexdigest()!=p['parent_budget_sha256']:raise ValueError('Parent budget drift')
    if a.action=='reserve':
        if not a.case or b['status']!='active' or now>datetime.fromisoformat(p['deadline_utc']) or len(b['attempts'])>=5 or len(b['attempts'])+len(parent['attempts'])>=6:raise ValueError('Closed/time/aggregate attempt limit')
        if b['attempts'] and b['attempts'][-1]['status']=='reserved':raise ValueError('Record prior attempt')
        if a.case!='spy' and not (ROOT/'control-gate.json').exists():raise ValueError('SPY gate missing')
        repeats=sum(max(0,sum(x['case']==c for x in b['attempts'])-1) for c in CASES)
        if any(x['case']==a.case for x in b['attempts']) and repeats>=2:raise ValueError('Retry cap')
        for f,d in p['input_hashes'].items():
            if hashlib.sha256(Path(f).read_bytes()).hexdigest()!=d:raise ValueError('Frozen input drift')
        d=hashlib.sha256((ROOT/(a.case+'-source.py')).read_bytes()).hexdigest()
        if d!=p['source_hashes'][a.case]:raise ValueError('Source drift')
        b['attempts'].append(dict(id=len(b['attempts'])+1,case=a.case,status='reserved',source_sha256=d,reserved_utc=now.isoformat()))
    elif a.action=='record':
        row=b['attempts'][-1]
        if row['case']!=a.case or row['status']!='reserved':raise ValueError('Attempt identity')
        if a.status=='completed':
            rows=decode_fragments(json.loads((ROOT/(a.case+'-fragments.json')).read_text()),a.case);check=audit_records(rows,a.case);save(ROOT/(a.case+'-summary.json'),rows);save(ROOT/(a.case+'-audit.json'),check)
            if a.case=='spy':save(ROOT/'control-gate.json',check)
            else:
                gate=json.loads((ROOT/'control-gate.json').read_text())
                if any(gate[k]!=check[k] for k in ['calendar_hash','range_hash']):raise ValueError('Range/calendar parity')
        row.update(status=a.status,backtest_id=a.backtest,recorded_utc=now.isoformat())
    else:
        if b['attempts'] and b['attempts'][-1]['status']=='reserved':raise ValueError('Record pending attempt')
        b.update(status='closed',closed_utc=now.isoformat())
    save(ROOT/'budget.json',b);print(json.dumps(b['attempts'][-1] if a.action!='close' else dict(closed=True,aggregate_attempts=len(b['attempts'])+len(parent['attempts']))))

if __name__=='__main__':main()
