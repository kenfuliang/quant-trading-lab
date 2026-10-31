"""Read saved artifacts only; no simulator, downloads, tracking writes or services."""
import csv
import html
import json
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from research.studies.sector_gate.model import CASES,write_json


def decision(summaries):
    contexts={};tol=1e-9
    for bps in (5,10):
        g=summaries[f'gate-{bps}'];v=summaries[f'vol-{bps}'];h=summaries[f'hold-{bps}']
        checks={'calmar_gain_at_least_10pct':g['calmar']>=1.1*v['calmar'],
            'cagr_not_lower':g['cagr_pct']+tol>=v['cagr_pct'],
            'drawdown_not_deeper':g['max_drawdown_pct']<=v['max_drawdown_pct']+tol,
            'underwater_sessions_not_longer':g['uw_sessions']<=v['uw_sessions'],
            'underwater_days_not_longer':g['uw_days']<=v['uw_days']}
        better=[h['calmar']>g['calmar'],h['cagr_pct']>g['cagr_pct'],h['max_drawdown_pct']<g['max_drawdown_pct'],h['uw_sessions']<g['uw_sessions'],h['uw_days']<g['uw_days']]
        no_worse=[h['calmar']>=g['calmar'],h['cagr_pct']>=g['cagr_pct'],h['max_drawdown_pct']<=g['max_drawdown_pct'],h['uw_sessions']<=g['uw_sessions'],h['uw_days']<=g['uw_days']]
        checks['not_spy_dominated']=not(all(no_worse) and any(better))
        contexts[str(bps)]={'checks':checks,'passed':all(checks.values()),'relative_calmar_gain':g['calmar']/v['calmar']-1}
    passed=all(c['passed'] for c in contexts.values())
    return {'contexts':contexts,'fixed_target_passed':passed,'disposition':'development_screen_passed_only' if passed else 'reject_fixed_target',
        'automatic_promotion':False,'independent_alpha_established':False}


def render(root,destination):
    root=Path(root);dest=Path(destination);dest.mkdir(parents=True,exist_ok=False)
    summaries={c:json.loads((root/'cases'/c/'summary.json').read_text()) for c in CASES}
    rows=[{'case':c,**summaries[c]} for c in CASES];pd.DataFrame(rows).to_csv(dest/'comparison.csv',index=False)
    annual=pd.concat([pd.read_csv(root/'cases'/c/'annual.csv').assign(case=c) for c in CASES],ignore_index=True)
    annual.to_csv(dest/'annual-comparison.csv',index=False);d=decision(summaries);write_json(dest/'decision.json',d)
    fig=go.Figure()
    for c in CASES:
        data=pd.read_csv(root/'cases'/c/'ledger.csv')
        fig.add_scatter(x=data.date,y=data.equity_usd,name=c)
    fig.update_layout(title='Saved, audited development results — six fixed cases',xaxis_title='Date',yaxis_title='USD equity',template='plotly_white')
    summary=pd.DataFrame(rows)[['case','calmar','cagr_pct','max_drawdown_pct','sharpe','uw_sessions','uw_days','trades','fees_usd','slippage_usd','mean_gross_exposure']]
    text='''<!doctype html><html><head><meta charset="utf-8"><title>Sector momentum risk gate</title><style>body{font:15px system-ui;margin:30px;max-width:1400px}table{border-collapse:collapse;font-size:13px}th,td{padding:7px;border:1px solid #ddd}th{background:#eee}pre{white-space:pre-wrap}.scroll{overflow:auto}</style></head><body><h1>Sector momentum + traffic-light risk gate</h1><p>Private, free/local, restated development history. 2017-02-01–2025-12-31; 2017 partial. Same USD300,000, costs, dividends and splits. No leverage, native-engine parity, holdout or live-readiness claim.</p>'''
    text+='<h2>Headline comparison</h2><div class="scroll">'+summary.to_html(index=False,float_format=lambda x:f'{x:.6f}')+'</div>'
    text+=fig.to_html(full_html=False,include_plotlyjs=True)
    text+='<h2>Frozen decision</h2><pre>'+html.escape(json.dumps(d,indent=2))+'</pre>'
    text+='<h2>Year-by-year metrics</h2><p>Annual drawdown is signed negative; annual Calmar uses simple calendar-year return, not CAGR. Underwater duration includes recovery; censored episodes are retained in each temporal.json.</p><div class="scroll">'+annual.to_html(index=False,float_format=lambda x:f'{x:.4f}')+'</div>'
    text+='<p>Source: frozen gate-v1 plan and sealed cases in .local/sector-gate-v1/financial. Evidence and report are local only.</p></body></html>'
    (dest/'index.html').write_text(text)
    return d
