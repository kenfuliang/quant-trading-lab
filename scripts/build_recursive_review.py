#!/usr/bin/env python3
"""Build the scoped 2026-10-25 review from saved evidence; no simulations/services."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from reporting.temporal import analyze_temporal
from reporting.recursive_research import render
from research.spy_backtest import load_data

spec = importlib.util.spec_from_file_location('review_metrics', ROOT / 'scripts/recursive_research_review.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)
EVIDENCE = ROOT / 'docs/tasks/evidence'
LOCAL = ROOT / '.local/recursive-research'


def read(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Preserve the review snapshot; choose a new output directory.')
    args.output.mkdir(parents=True)
    records = []
    for cycle, context in [(2, 'Q2 · 5bp per side'), (3, 'Q3 · 10bp per side')]:
        receipt = read(EVIDENCE / f'2026-10-25-recursive-cycle{cycle}.json')
        score = read(EVIDENCE / f'2026-10-25-recursive-cycle{cycle}-scores.json')
        directory = ROOT / receipt['input_directory']
        assert review.digest(directory / 'manifest.json') == receipt['manifest_sha256']
        review.verify_artifacts(directory)
        for name, item in receipt['cases'].items():
            for filename, sha in item['artifact_hashes'].items():
                assert review.digest(directory / name / filename) == sha
            label={'ema-control':'EMA','rsi-control':'RSI2','mix-equal':'50% EMA / 50% RSI2',
                   'mix-trend-heavy':'75% EMA / 25% RSI2'}[name]
            records.append(dict(candidate_id=name, label=label, context=context,
                metrics=item['overall'], annual=item['annual'], directory=directory/name,
                pareto=name in score['pareto']['front'], eligibility='development arithmetic only'))
    suite = ROOT / 'reports/strategy-suite/97fc0717512bee9e'
    manifest = read(suite / 'manifest.json')
    for name, label in [('s031_1x','Volatility target'), ('s032_1x','EMA + volatility target'),
                        ('s033_1x','Three-state SPY drawdown gate'), ('s034_1x','CPPI fixed initial-capital floor')]:
        item = review.inspect(suite/name)
        for filename, sha in item['artifact_hashes'].items():
            assert manifest['artifact_hashes'][name+'/'+filename] == sha
        records.append(dict(candidate_id=name, label=label, context='Existing risk references · 5bp',
            metrics=item['overall'], annual=item['annual'], directory=suite/name,
            pareto=None, eligibility='read-only development reference'))
    hold_dir = ROOT / 'reports/leverage/3aba31cfafe4da76'
    hold_manifest = read(hold_dir/'manifest.json')
    name='base_6pct_buy_hold_1x'; item=review.inspect(hold_dir/name)
    for filename, sha in item['artifact_hashes'].items():
        assert hold_manifest['artifact_hashes'][name+'/'+filename] == sha
    records.append(dict(candidate_id='buy-hold',label='Always-long daily sizing reference',
        context='Existing risk references · 5bp',metrics=item['overall'],annual=item['annual'],
        directory=hold_dir/name,pareto=None,eligibility='read-only development reference'))
    source = ROOT/'reports/spy/20261024-235746-728801/source-data.json'
    assert hold_manifest['source_sha256']==manifest['source_sha256']==review.digest(source)
    assert hold_manifest['model']==manifest['model']==read(ROOT/'research/plans/recursive-portfolio-v2.json')['financing_model']
    raw, _, _ = load_data(source)
    dates = pd.to_datetime(raw.index)
    anchor = dates[dates < pd.Timestamp('2005-01-03')][-1]
    temporal_rows=[]; temporal_receipt={}; candidates=[]; annual=[]
    figure = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=.06,
        subplot_titles=('Portfolio equity (USD)', 'Full-path drawdown (%)',
                        'Rolling 63 / 252 observed-session cumulative return (%)',
                        'Rolling 252-session Sharpe · zero risk-free rate'))
    plot_labels=[]
    wanted={'ema-control','mix-equal','mix-trend-heavy','s032_1x','s033_1x','buy-hold'}
    for record in records:
        identifier=record['candidate_id']; context=record['context']; key=context+'/'+identifier
        curve=pd.read_csv(record['directory']/'ledger.csv',parse_dates=['date']).set_index('date')
        assert len(curve)==5283 and curve.index.equals(dates[(dates>=pd.Timestamp('2005-01-03'))])
        equity=pd.concat([pd.Series([300000.],index=pd.DatetimeIndex([anchor])),curve.equity_usd])
        summary,table=analyze_temporal(equity,initial_capital=300000.)
        assert abs(summary['max_drawdown']*100-record['metrics']['drawdown_pct'])<=1e-9
        folder=args.output/'temporal';folder.mkdir(exist_ok=True)
        safe=context.split(' · ')[0].replace(' ','-')+'-'+identifier
        table.to_csv(folder/(safe+'.csv'),index_label='date')
        temporal_receipt[key]={'summary':summary,'ledger_sha256':review.digest(record['directory']/'ledger.csv'),
                               'table_sha256':review.digest(folder/(safe+'.csv'))}
        temporal_rows.append({'context':context,'candidate':record['label'],
            'max_drawdown_pct':summary['max_drawdown']*100,
            'longest_underwater_sessions':summary['longest_underwater_duration_sessions'],
            'longest_underwater_calendar_days':summary['longest_underwater_duration_calendar_days'],
            'longest_right_censored':summary['longest_underwater_right_censored'],
            'worst_21_session_return_pct':summary['worst_returns']['21']['return']*100,
            'worst_63_session_return_pct':summary['worst_returns']['63']['return']*100,
            'historical_daily_ES95_loss_pct':summary['historical_daily_es95']['loss_magnitude']*100})
        m=record['metrics']
        candidates.append({'context':context,'candidate_id':identifier,'label':record['label'],
            **{k:m[k] for k in ['return_pct','drawdown_pct','calmar','sharpe','commission_usd','slippage_usd','financing_usd','mean_close_exposure']},
            'eligibility':record['eligibility'],'pareto':record['pareto']})
        annual.extend({'context':context,'candidate_id':identifier,**r} for r in record['annual'])
        if identifier in wanted and '10bp' not in context:
            group=len(plot_labels);plot_labels.append(record['label'])
            for row, column, multiplier, suffix in [(1,'equity_usd',1,''),(2,'drawdown',100,''),
                    (3,'return_63',100,'63 sessions'),(3,'return_252',100,'252 sessions'),(4,'sharpe_252',1,'')]:
                figure.add_trace(go.Scatter(x=table.index,y=table[column]*multiplier,
                    name=suffix or record['label'],visible=group==0,mode='lines',showlegend=row==3,
                    connectgaps=False,line=dict(width=1.4),hovertemplate='%{x|%Y-%m-%d}<br>%{y:.3f}<extra>%{fullData.name}</extra>'),row=row,col=1)
    buttons=[]
    for group,label in enumerate(plot_labels):
        buttons.append(dict(label=label,method='update',args=[{'visible':[i//5==group for i in range(len(figure.data))]},
            {'title.text':'Viewed SPY development paths · '+label}]))
    figure.update_layout(height=1050,title=dict(text='Viewed SPY development paths · '+plot_labels[0],x=.055,y=.99,yanchor='top'),
        updatemenus=[dict(buttons=buttons,x=0,y=1.065,xanchor='left')],margin=dict(t=150),
        template='plotly_white',legend=dict(orientation='h'),hovermode='x unified')
    figure.write_html(args.output/'temporal.html',include_plotlyjs=True,full_html=True)
    (args.output/'temporal-metrics.json').write_text(json.dumps(temporal_receipt,indent=2,allow_nan=False)+'\n')
    priors=read(EVIDENCE/'2026-10-25-recursive-research-priors.json')
    state=read(LOCAL/'state.json');snapshot=read(LOCAL/'journal/snapshot.json')
    attempts=snapshot['state']['attempts']
    recorded_compute=sum(a['outcome']['actual_resource_units'] for a in attempts.values() if a['outcome'])
    # Text is a curated synthesis; financial measurements above come from pinned receipts.
    bundle={'schema_version':1,'title':'Research review: evidence, risk and the next decision',
      'generated_at':datetime.now(timezone.utc).isoformat(),'review_at':'2026-10-25 12:14 PM America/Los_Angeles',
      'status':'Bounded pilot complete; review and next prerequisites', 'temporal_url':'temporal.html',
      'summary':['8 new audited financial cases; two controls reproduce exactly. No clear strategy improvement established.',
                 'Smaller drawdown can coexist with lower growth and longer underwater periods. Temporal metrics now accompany headline ratios.',
                 'Frozen history ends 2025-12-31. This page does not assign a current market green/yellow/red state.'],
      'goals':[{'layer':'Investment aspiration','objective':'USD300000 → USD600000 in one year; approximately30% drawdown reassessment reference','status':'Feasibility not established; investment budgets remain open'},
               {'layer':'Research process','objective':'Bounded, reproducible decisions; retain failures; explore or pause when marginal information is weak','status':'Prototype exercised; no trained RL or demonstrated scheduler advantage'},
               {'layer':'Operations','objective':'Verified data/configuration, recovery, health, risk and reconciliation before separately scoped paper operation','status':'Native M1–M5 prerequisites remain'}],
      'inventory':[{'capability':a,'state':b,'boundary':c} for a,b,c in [
          ('NautilusTrader + Python runtime','Implemented/pinned','Native config/catalog baseline still requires behavior proof'),
          ('SPY accounting and research reports','Saved and independently reconciled','Simplified model; viewed development data'),
          ('100 strategy ideas / 22 adaptations / 88 saved cases','Catalogue and supported suite available','78 ideas require missing inputs/instrument models'),
          ('MLflow and local comparison browser','Available','Views are not execution or evidence authority'),
          ('19 project skills','Installed workflows','Paired evaluation tied; instructions are not learned policies'),
          ('Scoring / bounded runner / decision journal','Implemented and adversarially tested','Caller evidence verification and coordinator global limits remain necessary'),
          ('Temporal diagnostics','Implemented temporal-v1.1','Descriptive observed-session statistics; no future loss bounds'),
          ('IBKR connection and execution','Blocked/unverified','No successful project broker connection or order evidence')]],
      'priors':[{'source':s['id'],'verified_scope':s['claim_check'],'reuse':s['reuse'],'blockers':'; '.join(s.get('blockers',[]))} for s in priors['sources']],
      'candidates':candidates,'annual':annual,'temporal':temporal_rows,
      'pareto':[{'context':'Q2 5bp','front':'EMA, RSI, equal mix, trend-heavy mix','interpretation':'Four return/drawdown tradeoffs; no mixture dominates controls'},
                {'context':'Q3 10bp','front':'EMA, equal mix, trend-heavy mix','interpretation':'RSI dominated by equal mix; Calmar ordering reverses versus5bp'},
                {'context':'Existing risk references','front':None,'interpretation':'Read-only references; not pooled into the preregistered Q2/Q3 frontier'}],
      'risk_gates':[{'gate':'Existing strategy33','green':'SPY drawdown <10%: factor1','yellow':'SPY drawdown10–20% inclusive: factor0.5','red':'SPY drawdown >20%: factor0','timing':'Previous close → next open','limit':'SPY price drawdown, not portfolio loss; no hysteresis'},
                   {'gate':'Proposed combined gate','green':'Normal predeclared budget','yellow':'Reduced cap','red':'Cash target at next opportunity','timing':'Lagged trend/volatility/drawdown; staged re-entry proposed','limit':'Specification only; not implemented or backtested'},
                   {'gate':'Operational eligibility','green':'Verified usable inputs/account state','yellow':'Named degraded state subject to policy','red':'Required evidence invalid/unknown: block action','timing':'Before action','limit':'Separate from prediction or market regime'}],
      'decisions':state['research_decisions']+[{'question':'Process evaluation','decision':'Priority vs breadth-first synthetic aggregate6vs6; skills54vs54. No demonstrated incremental benefit.'}],
      'budgets':{'new_financial_attempts_used':len(state['new_financial_attempts']),'financial_ceiling':state['new_financial_attempt_budget'],
                 'additional_attempts_authorized_by_this_report':0,'logical_decisions_recorded':len(attempts),
                 'compute_seconds_for_recorded_local_actions_only':recorded_compute,
                 'runtime_exclusions':'Model, source retrieval, human/agent analysis, validation and rendering excluded; not total research cost'},
      'prerequisites':[{'priority':i,'next':a,'acceptance':b} for i,a,b in [
          (1,'Native configuration/catalog baseline (M1)','Synthetic multi-instrument round-trip, timestamps/identity, invalid input and mode behavior'),
          (1,'Legacy direct-call audit guards','Versioned finite/coverage checks before unwrapped audit callers; current bounded path guarded'),
          (2,'Data and evidence independence','Rights, corporate actions, calendar checks, access history and future evaluation protocol'),
          (2,'Research-policy evidence','Matched states/budgets with independent outcomes; retain wins, losses and ties'),
          (2,'Optional risk gate experiment','Freeze state transitions, re-entry, costs and equal-risk/cash comparators; measure false alarms and missed rebounds'),
          (3,'Broader markets','Instrument-specific data/model contracts before stock/options/futures/FX claims'),
          (3,'Paper operation prerequisites','Risk budgets, native recovery/health and separately verified account/feed access')]],
      'limitations':['All financial results use already-viewed2005–2025 SPY history. No untouched-test or annual-doubling evidence.',
          'Full historical search count, effective independent trials and statistical superiority remain unknown.',
          'The journal records caller claims; it does not independently prove execution or authenticate evidence. Global financial budget was coordinator-enforced.',
          'Q1 scheduling was journaled after the predeclared read-only analysis; it is not blind allocator validation.',
          'Scenario costs are illustrative, not broker quotes. Zero cash interest and simplified execution can affect comparisons.',
          'Windows count observed sessions. Independent exchange-calendar completeness remains unverified; missing observations cannot be made into calendar months.',
          'A shorter drawdown or green state does not guarantee protection against gaps, rapid reversals or margin changes.',
          'No extra statistical/RL framework, paid data/API, broker operation, commit or publication was used.'],
      'evidence':[{'label':'Interactive temporal paths','url':'temporal.html'},{'label':'Temporal metrics JSON','url':'temporal-metrics.json'},
          {'label':'Research decision event log','url':'evidence/research-events.jsonl'},
          {'label':'Primary-source review','url':'evidence/2026-10-25-recursive-research-priors.md'},
          {'label':'Executive review','url':'evidence/2026-10-25-recursive-research-review.md'},
          {'label':'Risk-gate research','url':'evidence/2026-10-25-risk-gate-research.md'},
          {'label':'Expansion prerequisites','url':'evidence/2026-10-25-research-expansion-prerequisites.md'}]}
    # Copy public, redacted evidence only. Links inside copied Markdown retain their
    # source meaning in the repository; this browser view is a convenient text copy.
    evidence_out=args.output/'evidence';evidence_out.mkdir()
    for filename in ['2026-10-25-recursive-research-priors.md','2026-10-25-recursive-research-review.md',
                     '2026-10-25-risk-gate-research.md','2026-10-25-research-expansion-prerequisites.md']:
        (evidence_out/filename).write_bytes((ROOT/'docs/tasks'/filename).read_bytes())
    (evidence_out/'research-events.jsonl').write_bytes((LOCAL/'journal/events.jsonl').read_bytes())
    (evidence_out/'research-journal-snapshot.json').write_bytes((LOCAL/'journal/snapshot.json').read_bytes())
    evidence_names=['recursive-cycle1','recursive-cycle2','recursive-cycle2-scores','recursive-cycle3',
                    'recursive-cycle3-scores','recursive-control-parity','recursive-research-priors',
                    'recursive-research-policy-evaluation','recursive-research-adversarial-review',
                    'temporal-review','risk-gate-research','research-expansion-prerequisites']
    evidence_inputs={}
    for name in evidence_names:
        path=EVIDENCE/('2026-10-25-'+name+'.json')
        evidence_inputs[str(path.relative_to(ROOT))]=review.digest(path)
        (evidence_out/path.name).write_bytes(path.read_bytes())
    render(bundle,args.output)
    artifact_hashes={str(p.relative_to(args.output)):review.digest(p) for p in args.output.rglob('*') if p.is_file()}
    receipt={'schema_version':1,'generated_at':bundle['generated_at'],'source_sha256':review.digest(source),
        'reviewer_code_sha256':review.digest(Path(__file__)),'temporal_method_sha256':review.digest(ROOT/'reporting/temporal.py'),
        'renderer_sha256':review.digest(ROOT/'reporting/recursive_research.py'),
        'independent_metrics_code_sha256':review.digest(ROOT/'scripts/recursive_research_review.py'),
        'input_evidence_hashes':evidence_inputs,
        'artifact_hashes':artifact_hashes,'cases':len(records),'annual_rows':len(annual),'new_financial_trials':0}
    (args.output/'manifest.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'output':str(args.output),'cases':len(records),'annual_rows':len(annual),'artifacts':len(artifact_hashes),'new_financial_trials':0}))


if __name__ == '__main__':
    main()
