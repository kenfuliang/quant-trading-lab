"""Reserve/record one frozen six-attempt licensed pairs study; never launches hosted jobs."""
from pathlib import Path
from datetime import datetime,timedelta,timezone
import argparse
import hashlib
import json
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research.studies.checkpoint_20261031.pairs_study import STUDY,CASES,build_source,decode_fragments,audit_records
ROOT=Path('.local')/STUDY
PLAN=Path('research/plans')/(STUDY+'.json')


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['freeze','reserve','record','close']);ap.add_argument('--case',choices=CASES);ap.add_argument('--status');ap.add_argument('--backtest');ap.add_argument('--project',type=int);a=ap.parse_args();now=datetime.now(timezone.utc)
    if a.action=='freeze':
        if PLAN.exists() or (ROOT/'budget.json').exists():raise ValueError('Preserve existing study')
        if not a.project:raise ValueError('Isolated project ID required')
        inputs=['research/pairs_study.py','scripts/pairs_study.py','research/quantconnect/sources/stock_pairs_original.py','research/quantconnect/sources/LICENSE-JeSuisTM.txt','research/quantconnect/capm_study.py','research/quantconnect/sector_metrics.py','research/capm_review.py','requirements.lock.txt']
        ROOT.mkdir(parents=True,exist_ok=True);hashes={}
        for c in CASES:
            s=build_source(c);(ROOT/(c+'-source.py')).write_text(s);hashes[c]=hashlib.sha256(s.encode()).hexdigest()
        negative=[]
        for study in ['capm-ablation-v1','dual-thrust-spy-v1']:
            manifest=Path('.local/performance')/study/'manifest.json'
            negative.append(dict(study=study,manifest_path=str(manifest),manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest()))
        plan=dict(study=STUDY,status='frozen-before-probe-and-financial-runs',created_utc=now.isoformat(),deadline_utc=(now+timedelta(minutes=90)).isoformat(),max_total_attempts=6,technical_retry_slots=2,cases=CASES,project_id=a.project,expected_engine='2.5.0.0.18209',source_hashes=hashes,input_hashes={f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in inputs},git=dict(cwd=str(Path.cwd()),branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip(),sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True),negative_baselines=negative,
          source=dict(tutorial_id='QC-T-15300',package='stock-pairs',repo='je-suis-tm/quant-trading',revision='611b73f2c3f577ac5b28aaa19ac8c43d3236c7a5',path='Pair trading backtest.py',license='Apache-2.0 repository grant; original bytes and accompanying license preserved',relation='Independent mechanism alternative; declared causal NVDA/AMD adaptation, not exact hosted tutorial or original 2013-2014 reproduction'),
          context=dict(window=['2016-01-01','2025-12-31'],capital_usd=300000,training='For every close use exactly250 strictly prior aligned sessions from300daily-history requests; SCALED_RAW normalizes only actions known by current decision time. Current close is excluded from fitting; used only for residual scoring. No pre-2016 trades or NAV; 2015 history seeds features.',
          signal='Regress AMD(Y) on NVDA(X) in price levels plus constant. Cointegration-specific statsmodels.coint, trend c, maxlag5, AIC; require p<.05, beta>0 and negative lag-residual coefficient in the source-inspired error-correction regression. Compute current dimensionless residual z using prior-sample mean/sample SD. Flat enters longX/shortY at z>=1, inverse at z<=-1. Retain direction until zero crossing or gate fails, then cash. Daily refitting/rebalancing; no parameter grid or maximum holding stop.',
          execution='After close t queue percentage weights for next session9:32; raw current prices determine native quantities. Hedge shares ratio beta translated into dollar weights using decision prices; absolute target weights sum.98. Native ordered reductions/increases; final-close queued signal is unexecuted, no forced terminal liquidation. Holdings may drift beyond targets.',
          controls='spy:98% SPY purchase once at Jan5,2016 9:32 after first shared Jan4 close; pairhold:49%NVDA+49%AMD at that same time, no rebalance. All cases subscribe to all3symbols and fit the same features to audit parity. Pairhold diagnoses long-asset opportunity cost, not a net/beta/exposure-matched control.',
          costs='Native IB commissions + fixed5bp/fill and native quote/fill defaults. Native raw-mode splits and dividend cash credits/debits, including short dividends. Funding6%ACT/360 prior-closing-negativecash,zero credit,native interest disabled. Short borrow3%ACT/365 on previous-event short notional times elapsed seconds including overnight/weekends; native historical availability/locates assumed, not verified. Taxes/locate/recall/capacity not modeled.',
          data='Free hosted US equities/security-master history and minute bars. RAW execution avoids future full-history normalization; SCALED_RAW fit data uses known actions. Existing account access must pass a zero-order probe over all2514sessions and both NVDA splits. Only own aggregates/counts/hashes exported, no raw market paths.',
          metrics='Full/annual return, closing DD, sample-daily zeroRF Sharpe sqrt252, full calendar-CAGR/absDD and annual return/absDD Calmar, UWfraction/longest sessions/calendar days/terminal censoring. Additional minute-mark DD, mean/max gross, mean net, short minute count, eligible-day fraction, dividends/borrow/fees and daily native book residual.'),
          risks=['Original full-sample max-price sizing is future aware; source ADF residual p-value uses inappropriate ordinary unit-root reference after estimated regression; trigger bands mix z and price SD, holding state resets daily. All repaired as declared mechanism adaptation.','The source-selected NVDA/AMD pair is an ex-post surviving pair and already discussed in2018; 2016-2025is viewed development history, not untouched selection validation.','Cointegration gate assumes I(1), has rolling multiple-testing/relationship-breakdown risks and is not a stable-profits certificate. No broad pair search or inference of causality from PnL.'],
          hypothesis='A causal cointegration-gated pair offers useful positive net risk-adjusted performance versus SPY after realistic stated friction assumptions.',primary_estimand='Full Calmar(pairs)-Calmar(SPY), conditional on positive pair CAGR; growth and temporal criteria are separately fixed diagnostics.',
          decision_rule=dict(growth='Retain for independent validation only if CAGR>SPY,Calmar>=SPY,longestUW<=SPY.',risk_alternative='Retain as a risk-research alternative only if CAGR>0,Sharpe>=SPY,DD<SPY,longestUW<=SPY. If neither screen passes, stop this fixed adaptation; no retuning on viewed history.',drawdown='Closing or minute DD>30% flags reassessment, not hard loss bound.'),
          gates=['Free zero-order probe:10annual checkpoints,250strict-prior aligned history observations each day,2514ready sessions,raw normalization,actual dependencies/nativeIBmodel,zero orders,>=2NVDA splits and>=30NVDA/SPY dividend events.','Fresh SPY must reconcile before two other finance cases. All4fit hashes and3financial calendars/minute counts must match. Native daily/lifetime book residual<=USD2; fee/lastmarkresidual<=USD.01; no invalid/pending orders/nonpositive NAV.'],
          stops=['Reserve before every launch;<=6total attempts,<=2technical retries;deadline90minutes. Failures count; source/build/engine drift stops dependent runs until explicit archived technical amendment.','No financial run if input gate blocked. No results-driven asset/parameter/cost search, paid resources, dependencies, new services, MLflow import, agents, broker/account/order operations, commits or publication.'])
        save(PLAN,plan);save(ROOT/'budget.json',dict(study=STUDY,status='active',attempts=[]));print(json.dumps(dict(plan=str(PLAN),deadline=plan['deadline_utc'])));return
    p=json.loads(PLAN.read_text());b=json.loads((ROOT/'budget.json').read_text())
    if a.action=='reserve':
        if not a.case or b['status']!='active' or now>datetime.fromisoformat(p['deadline_utc']) or len(b['attempts'])>=p['max_total_attempts']:raise ValueError('Closed/expired budget')
        if b['attempts'] and b['attempts'][-1]['status']=='reserved':raise ValueError('Prior attempt unrecorded')
        if a.case!='probe' and not (ROOT/'input-gate.json').exists():raise ValueError('Input gate missing')
        if a.case not in ['probe','spy'] and not (ROOT/'control-gate.json').exists():raise ValueError('Fresh SPY gate missing')
        repeats=sum(max(0,sum(x['case']==c for x in b['attempts'])-1) for c in CASES)
        if any(x['case']==a.case for x in b['attempts']) and repeats>=2:raise ValueError('Retry cap')
        for f,d in p['input_hashes'].items():
            if hashlib.sha256(Path(f).read_bytes()).hexdigest()!=d:raise ValueError('Frozen input drift:'+f)
        d=hashlib.sha256((ROOT/(a.case+'-source.py')).read_bytes()).hexdigest()
        if d!=p['source_hashes'][a.case]:raise ValueError('Source drift')
        b['attempts'].append(dict(id=len(b['attempts'])+1,case=a.case,status='reserved',source_sha256=d,reserved_utc=now.isoformat()))
    elif a.action=='record':
        row=b['attempts'][-1]
        if row['case']!=a.case or row['status']!='reserved':raise ValueError('Attempt identity')
        if a.status=='completed':
            rows=decode_fragments(json.loads((ROOT/(a.case+'-fragments.json')).read_text()),a.case);check=audit_records(rows,a.case)
            if a.case!='probe':
                gate=json.loads((ROOT/'input-gate.json').read_text())
                if gate['fit_hash']!=check['fit_hash']:raise ValueError('Probe/financial fit parity')
            save(ROOT/(a.case+'-summary.json'),rows);save(ROOT/(a.case+'-audit.json'),check)
            if a.case=='probe':save(ROOT/'input-gate.json',check)
            elif a.case=='spy':save(ROOT/'control-gate.json',check)
        row.update(status=a.status,backtest_id=a.backtest,recorded_utc=now.isoformat())
    else:
        if any(x['status']=='reserved' for x in b['attempts']):raise ValueError('Pending attempt')
        b.update(status='closed',closed_utc=now.isoformat())
    save(ROOT/'budget.json',b);print(json.dumps(b['attempts'][-1] if a.action!='close' else dict(closed=True,attempts=len(b['attempts']))))


if __name__=='__main__':main()
