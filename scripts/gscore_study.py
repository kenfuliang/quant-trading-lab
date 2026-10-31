"""Coordinator for one fixed G-Score study; no API credentials or network access."""
from pathlib import Path
from datetime import datetime,timedelta,timezone
import argparse
import hashlib
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research.gscore_study import STUDY,CASES,build_source,decode_fragments,audit_records
ROOT=Path('.local')/STUDY
PLAN=Path('research/plans')/(STUDY+'.json')


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['freeze','reserve','record','close']);ap.add_argument('--project',type=int);ap.add_argument('--case',choices=CASES);ap.add_argument('--status');ap.add_argument('--backtest');a=ap.parse_args();now=datetime.now(timezone.utc)
    if a.action=='freeze':
        if PLAN.exists() or (ROOT/'budget.json').exists():raise ValueError('Preserve existing study')
        ROOT.mkdir(parents=True,exist_ok=True);hashes={}
        for c in CASES:
            s=build_source(c);(ROOT/(c+'-source.py')).write_text(s);hashes[c]=hashlib.sha256(s.encode()).hexdigest()
        inputs=['research/gscore_study.py','scripts/gscore_study.py','research/quantconnect/sources/g_score_legacy_original.py','research/quantconnect/sources/LICENSE-QuantConnect.txt','research/quantconnect/capm_study.py','research/quantconnect/sector_metrics.py','research/capm_review.py']
        p=dict(study=STUDY,status='frozen-before-hosted-execution',created_utc=now.isoformat(),deadline_utc=(now+timedelta(minutes=90)).isoformat(),project_id=a.project,cases=CASES,financial_cases=['gscore','eligible','spy'],max_total_attempts=6,technical_retry_slots=2,source_hashes=hashes,input_hashes={f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in inputs},source=dict(tutorial_id='QC-T-15267',package='g-score-legacy',repository='santoshlite/StrategyLibraryQC',revision='6b406477afce2a12724dbf1031a99fbc1e1fee4d',path='G-Score Investing.py',rights='Explicit Apache2.0 file header only; not repository-wide grant or exact current hosted-source identity.'),hypothesis='Seven-factor G-score selection adds net growth and risk-adjusted value beyond SPY and the same annually selected eligible low-book/market technology cohort.',context=dict(financial_window=['2016-01-01','2025-12-31'],causal_roa_seed=['2013-01-01','2015-12-31'],capital_usd=300000,target_gross=.98,cash_buffer_setting=.01,selection='Unchanged source technology/full-field filters, bottom all-market book-to-market quartile, ratios and medians, twelve quarterly snapshot ROA variance and G-score>=5 of7. No current-member list, ranking optimization or score-threshold search.',candidate='Long equal-weight source-score>=5 names, annual April rebalance; first invest April2016; no price stop/market gate/shorting.',control='eligible: equal-weight source technology low-book/market/full-field cohort before G-score threshold, same April rebalance and target gross. spy: one98% SPY purchase at9:45 first2016session; no rebalancing.',execution='Adaptation: native minute subscriptions; annual target changes, sell reductions at9:35 and buy increases at9:45 after settled sells; retain target/held subscriptions. This replaces legacy ConstantAlpha/EqualWeighting/ImmediateExecution framework semantics, which may cause additional rebalancing. No claim of exact source-framework reproduction.',cost='Native IB fee model plus fixed5bp per fill; native spread/fill model retained. Assumption, not measured live cost. No extra cost grid.',financing='Prior-close6% debit ACT/360, zero credit; native per-security interest disabled; no final liquidation.',data='Free hosted Morningstar fundamentals, US equity bars, mappings/actions. Original reported figures with provider filing-date/older approximate45day lag conventions, not independently verified filing replay. Raw bars/fundamentals/dense NAV stay hosted; own aggregates/counts/hashes only.',state='No ObjectStore read/write or pickle. Build ROA snapshots causally from2013quarter callbacks in each case; zero pre2016orders. Preserve source negatives, missing/zero filters and normalized R&D/Capex/SG&A proxies.',metrics='Same full/annual return, closing DD, sample daily zeroRF Sharpe sqrt252, fullCAGR/absDD and annualreturn/absDD Calmar; UWfraction, longest sessions/calendar days and terminal censoring. Mean/max gross, fills/notional, fees/funding and selection hashes.'),primary_estimand='G-score full net CAGR minus matching SPY CAGR; eligible-cohort excess CAGR and all risk/temporal measures are joint diagnostics.',decision_rule='Retain for further validation only if G-score CAGR>SPY, Calmar>=SPY, longestUW<=SPY and CAGR>eligible cohort. Otherwise do not call it an improvement. DDabove30% flags reassessment; no automatic promotion, annual-doubling or hard-loss-bound claim.',probe_gate='One order-free2013-2025 probe;52quarter callbacks,10nonempty annual eligible/selected cohorts, source token, zero fills/rejects, eligible minute-history availability. Then financial runs only. Require same selected/cohort hashes across all4cases.',history='Viewed2016-2025development history and public source; no protected unseen split, fitting, threshold optimization or trained RL advantage.',stops=['Six attempts total including probe and failures, at most2technical retries,90minute deadline; no budget carry-over.','No financial case before probe gate; stop/flag missing fields, unavailable free data, wrong source/build/case, rejected/pending orders, nonpositiveNAV, calendar/accounting/hash failure or version drift.','No paid resources, installs, new services, MLflow import, broker/account operations, orders, commits/publication or agents.'],negative_baseline=dict(study='capm-ablation-v1',manifest_path='.local/performance/capm-ablation-v1/manifest.json',manifest_sha256=hashlib.sha256(Path('.local/performance/capm-ablation-v1/manifest.json').read_bytes()).hexdigest(),disposition='Preserve as negative baseline; no changes or reruns. Different new execution/cost context prevents combining old CAPM results in one leaderboard.'))
        save(PLAN,p);save(ROOT/'budget.json',dict(study=STUDY,status='active',attempts=[]));print(json.dumps(dict(plan=str(PLAN),deadline=p['deadline_utc'])));return
    p=json.loads(PLAN.read_text());b=json.loads((ROOT/'budget.json').read_text())
    if a.action=='reserve':
        if not a.case or b['status']!='active' or now>datetime.fromisoformat(p['deadline_utc']) or len(b['attempts'])>=6:raise ValueError('Case/closed/deadline/attempt limit')
        if b['attempts'] and b['attempts'][-1]['status']=='reserved':raise ValueError('Record prior attempt')
        repeats=sum(max(0,sum(r['case']==c for r in b['attempts'])-1) for c in CASES)
        if any(r['case']==a.case for r in b['attempts']) and repeats>=2:raise ValueError('Technical retry limit')
        if a.case!='probe' and not (ROOT/'probe-gate.json').exists():raise ValueError('Probe gate missing')
        for f,d in p['input_hashes'].items():
            if hashlib.sha256(Path(f).read_bytes()).hexdigest()!=d:raise ValueError('Input drift:'+f)
        d=hashlib.sha256((ROOT/(a.case+'-source.py')).read_bytes()).hexdigest()
        if d!=p['source_hashes'][a.case]:raise ValueError('Source drift')
        b['attempts'].append(dict(id=len(b['attempts'])+1,case=a.case,status='reserved',source_sha256=d,reserved_utc=now.isoformat()))
    elif a.action=='record':
        row=b['attempts'][-1]
        if row['case']!=a.case or row['status']!='reserved':raise ValueError('Attempt identity')
        if a.status=='completed':
            rows=decode_fragments(json.loads((ROOT/(a.case+'-fragments.json')).read_text()),a.case);check=audit_records(rows,a.case);save(ROOT/(a.case+'-summary.json'),rows);save(ROOT/(a.case+'-audit.json'),check)
            if a.case=='probe':save(ROOT/'probe-gate.json',check)
            else:
                gate=json.loads((ROOT/'probe-gate.json').read_text())
                if any(gate[k]!=check[k] for k in ['score_hash','eligible_hash']):raise ValueError('Probe selection parity')
        row.update(status=a.status,backtest_id=a.backtest,recorded_utc=now.isoformat())
    else:
        if b['attempts'] and b['attempts'][-1]['status']=='reserved':raise ValueError('Record pending attempt')
        b.update(status='closed',closed_utc=now.isoformat())
    save(ROOT/'budget.json',b);print(json.dumps(b['attempts'][-1] if a.action!='close' else dict(closed=True,attempts=len(b['attempts']))))

if __name__=='__main__':main()
