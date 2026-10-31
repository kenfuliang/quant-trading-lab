"""Frozen epoch3 decision rules; saved-result reporting launches no simulations."""
import json
from pathlib import Path
import pandas as pd
from research.studies.sector_rsi.model import write_json
from research.studies.sector_rsi.capture import verify_manifest

TOL=1e-9


def dominates(a,b):
    if a['calmar'] is None or b['calmar'] is None:return False
    av=[a['calmar'],a['cagr_pct'],-a['max_drawdown_pct'],-a['uw_sessions'],-a['uw_days']]
    bv=[b['calmar'],b['cagr_pct'],-b['max_drawdown_pct'],-b['uw_sessions'],-b['uw_days']]
    return all(x>=y-TOL for x,y in zip(av,bv)) and any(x>y+TOL for x,y in zip(av,bv))


def decision(summaries,candidate,simpler):
    by={(r['policy'],r['cost_bps']):r for r in summaries};contexts={}
    for cost in (5,10):
        a,b,c=(by[(p,cost)] for p in (candidate,'gate',simpler))
        valid=a['calmar'] is not None and b['calmar'] is not None and b['calmar']>0
        lift=a['calmar']/b['calmar']-1 if valid else None
        checks={'calmar_lift_at_least_10pct':valid and lift>=.10,
                'cagr_not_lower':a['cagr_pct']>=b['cagr_pct']-TOL,
                'drawdown_not_deeper':a['max_drawdown_pct']<=b['max_drawdown_pct']+TOL,
                'underwater_sessions_not_longer':a['uw_sessions']<=b['uw_sessions'],
                'underwater_days_not_longer':a['uw_days']<=b['uw_days'],
                'not_simpler_control_dominated':not dominates(c,a)}
        contexts[str(cost)]={'relative_calmar_lift':lift,'checks':checks,'passed':all(checks.values())}
    return {'candidate':candidate,'incumbent':'gate','simpler_control':simpler,'contexts':contexts,
            'fixed_target_passed':all(c['passed'] for c in contexts.values()),
            'decision':'provisional_further_validation' if all(c['passed'] for c in contexts.values()) else 'reject_fixed_target',
            'independent_alpha_established':False,'operational_promotion':False}


def render(financial_root,destination,candidate,simpler):
    root=Path(financial_root);verify_manifest(root)
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    summaries=[];years=[]
    import plotly.graph_objects as go
    figure=go.Figure()
    for cost in (5,10):
        for policy in ('gate',simpler,candidate):
            case=root/'cases'/f'{policy}-{cost}';verify_manifest(case)
            summaries.append(json.loads((case/'summary.json').read_text()))
            annual=pd.read_csv(case/'annual.csv');annual['policy']=policy;annual['cost_bps']=cost;years.append(annual)
            ledger=pd.read_csv(case/'ledger.csv')
            figure.add_trace(go.Scatter(x=ledger.date,y=ledger.equity_usd,name=f'{policy} {cost}bp'))
    table=pd.DataFrame(summaries)
    table['calmar_rank_within_cost']=table.groupby('cost_bps').calmar.rank(ascending=False,method='min')
    table.to_csv(destination/'comparison.csv',index=False)
    annual=pd.concat(years,ignore_index=True);annual.to_csv(destination/'annual-comparison.csv',index=False)
    verdict=decision(summaries,candidate,simpler);write_json(destination/'decision.json',verdict)
    figure.update_layout(title='Epoch3 same-context portfolio NAV',xaxis_title='Date',yaxis_title='USD')
    body='<html><meta charset="utf-8"><title>Calmar epoch3</title><body><h1>Bounded sector RSI comparison</h1>'
    body+='<p>Already-viewed development; project ledger, not native/broker parity or independent alpha. 2017 is partial.</p>'
    body+=table[['policy','cost_bps','calmar','cagr_pct','max_drawdown_pct','sharpe','uw_sessions','uw_days']].to_html(index=False)
    body+='<p>Frozen disposition: '+verdict['decision']+'</p>'+figure.to_html(full_html=False,include_plotlyjs=True)
    body+='<h2>Annual return, drawdown, Sharpe, Calmar and time underwater</h2>'+annual.to_html(index=False)+'</body></html>'
    (destination/'index.html').write_text(body)
    return summaries,verdict
