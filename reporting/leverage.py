"""Render separate leveraged research results without modifying original reports."""
import json
from pathlib import Path
import shutil

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT=Path(__file__).resolve().parents[1]


def render(directory):
    directory=Path(directory)
    manifest=json.loads((directory/'manifest.json').read_text())
    scores=pd.read_csv(directory/'scores.csv',keep_default_na=True)
    out=ROOT/'.local/performance/leverage'/manifest['fingerprint'][:16]
    out.mkdir(parents=True,exist_ok=True)
    for name in ('scores.csv','manifest.json','assumptions.md'):
        shutil.copy2(directory/name,out/name)
    traces=[]
    for case in manifest['cases']:
        if case['scenario']!='base_6pct': continue
        history=pd.read_csv(Path(case['folder'])/'equity.csv')
        traces.append(go.Scatter(x=history.date,y=history.equity_usd,name=case['name']))
    equity=go.Figure(traces)
    equity.update_layout(title='Base scenario: portfolio equity after financing and trading costs',height=450,template='plotly_white',yaxis_title='USD')
    records=json.loads(scores.to_json(orient='records',double_precision=15))
    template=Path(__file__).with_name('leverage.html').read_text()
    page=template.replace('<!--DATA-->',json.dumps(records,allow_nan=False).replace('<','\\u003c'))
    page=page.replace('<!--PLOTLY-->',equity.to_html(full_html=False,include_plotlyjs=True))
    registry=out/'mlflow-runs.json'
    if registry.exists():
        eid=json.loads(registry.read_text())['experiment_id']
        page=page.replace('<h1>',f'<p><a href="http://127.0.0.1:5050/#/experiments/{eid}/runs?workflowType=machine_learning">Eight base runs in MLflow</a></p><h1>',1)
    (out/'index.html').write_text(page)
    (ROOT/'.local/performance/leverage-latest.json').write_text(json.dumps({'directory':str(out),'source':str(directory),'url':'http://127.0.0.1:8765/leverage/'+manifest['fingerprint'][:16]+'/index.html'}))
    home=ROOT/'.local/performance/index.html'
    link=f'<p><a href="leverage/{manifest["fingerprint"][:16]}/index.html">Leveraged SPY: 1×, 1.25×, 1.5× and 2× comparison</a></p>'
    if home.exists():
        text=home.read_text()
        import re
        text=re.sub(r'<p><a href="leverage/[^\"]+/index.html">Leveraged SPY:.*?</p>','',text)
        home.write_text(text.replace('</body>',link+'</body>'))
    return out
