"""Frozen disposition rules; saved-result rendering never runs a portfolio."""
import json
from pathlib import Path
import pandas as pd
from research.studies.sector_selection.model import write_json

TOL=1e-9

def dominates(a,b):
    if a['calmar'] is None or b['calmar'] is None:return False
    transformed=lambda x:[x['calmar'],x['cagr_pct'],-x['max_drawdown_pct'],-x['uw_sessions'],-x['uw_days']]
    av,bv=transformed(a),transformed(b)
    return all(x>=y-TOL for x,y in zip(av,bv)) and any(x>y+TOL for x,y in zip(av,bv))

def decision(summaries):
    by={(r['policy'],r['cost_bps']):r for r in summaries};out={}
    for cost in (5,10):
        candidate=by[('vol',cost)];incumbent=by[('raw',cost)]
        valid=candidate['calmar'] is not None and incumbent['calmar'] is not None and incumbent['calmar']>0
        lift=(candidate['calmar']/incumbent['calmar']-1) if valid else None
        tests={'calmar_lift_at_least_10pct':valid and lift>=.10,'cagr_not_lower':candidate['cagr_pct']>=incumbent['cagr_pct']-TOL,
               'drawdown_not_deeper':candidate['max_drawdown_pct']<=incumbent['max_drawdown_pct']+TOL,
               'underwater_sessions_not_longer':candidate['uw_sessions']<=incumbent['uw_sessions'],
               'underwater_days_not_longer':candidate['uw_days']<=incumbent['uw_days'],
               'not_simpler_control_dominated':valid and not any(dominates(by[(p,cost)],candidate) for p in ('equal','hold'))}
        out[str(cost)]={'relative_calmar_lift':lift,'guards':tests,'passed':all(tests.values())}
    return {'decision':'retain_for_further_validation' if all(x['passed'] for x in out.values()) else 'reject_fixed_target',
            'both_costs':out,'independent_alpha_established':False,'study_context':'issuer-v2 sector ledger,2017-02–2025,viewed development'}

def render(financial_root,destination):
    financial_root=Path(financial_root);destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    summaries=[];years=[]
    for cost in (5,10):
        for p in ('vol','raw','equal','hold'):
            path=financial_root/'cases'/f'{p}-{cost}';s=json.loads((path/'summary.json').read_text());summaries.append(s)
            annual=pd.read_csv(path/'annual.csv');annual['policy']=p;annual['cost_bps']=cost;years.append(annual)
    table=pd.DataFrame(summaries);table['calmar_rank_within_cost']=table.groupby('cost_bps').calmar.rank(ascending=False,method='min')
    table.to_csv(destination/'comparison.csv',index=False);annual=pd.concat(years,ignore_index=True);annual.to_csv(destination/'annual-comparison.csv',index=False)
    verdict=decision(summaries);write_json(destination/'decision.json',verdict)
    # Self-contained chart uses installed Plotly only; no server or network request.
    import plotly.graph_objects as go
    fig=go.Figure()
    for s in summaries:
        curve=pd.read_csv(financial_root/'cases'/f"{s['policy']}-{s['cost_bps']}"/'ledger.csv')
        fig.add_trace(go.Scatter(x=curve.date,y=curve.equity_usd,name=f"{s['policy']} {s['cost_bps']}bp"))
    fig.update_layout(title='Sector selection: same-context portfolio NAV',xaxis_title='Date',yaxis_title='USD')
    chart=fig.to_html(full_html=False,include_plotlyjs=True)
    html='<html><meta charset="utf-8"><title>Sector comparison issuer-v2</title><body><h1>Sector comparison issuer-v2</h1>'
    html+='<p>Viewed development; project ledger. 2017 is partial. No native/broker parity or independent alpha.</p><p>Disposition: '+verdict['decision']+'</p>'
    html+=table[['policy','cost_bps','calmar','calmar_rank_within_cost','cagr_pct','max_drawdown_pct','sharpe','uw_sessions','uw_days']].to_html(index=False)+chart
    html+='<h2>Annual and temporal results</h2>'+annual.to_html(index=False)+'</body></html>'
    (destination/'index.html').write_text(html)
    return summaries,verdict
