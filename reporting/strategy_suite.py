"""Render audited exploratory strategy suites; never simulate or invent missing results."""
import json
from pathlib import Path
import re
import shutil

import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[1]


def catalogue_entries(catalogue):
    if isinstance(catalogue, list):
        return catalogue
    for key in ('strategies', 'entries', 'catalogue'):
        if isinstance(catalogue.get(key), list):
            return catalogue[key]
    raise ValueError('Catalogue must contain a list of strategy entries')


def render(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest['status'] != 'completed':
        raise ValueError('Completed suite required')
    scores = pd.read_csv(directory / 'scores.csv')
    required = {'period', 'case', 'strategy_id', 'calmar', 'sharpe', 'return_pct', 'drawdown_pct', 'exposure'}
    if not required.issubset(scores.columns):
        raise ValueError('Missing comparison columns')
    if scores.duplicated(['period', 'case']).any():
        raise ValueError('Duplicate period/case scores')
    trial_catalogue=json.loads((directory / 'catalogue.json').read_text())
    review_path=ROOT/'research/strategy_catalogue.json'
    review=json.loads(review_path.read_text()) if review_path.exists() else trial_catalogue
    entries = catalogue_entries(review)
    out = ROOT / '.local/performance/strategy-suite' / manifest['fingerprint'][:16]
    out.mkdir(parents=True, exist_ok=True)
    for name in ('scores.csv', 'manifest.json', 'catalogue.json', 'assumptions.md'):
        if (directory / name).exists():
            shutil.copy2(directory / name, out / name)
    (out/'catalogue-review.json').write_text(json.dumps(review,indent=2))
    # Serialize pandas missing values as JSON null, not JavaScript NaN or fake zero.
    records = json.loads(scores.to_json(orient='records', double_precision=15))
    cases = [{k: case[k] for k in ('key', 'strategy_id', 'name', 'leverage')} for case in manifest['cases']]
    payload = {'scores': records, 'catalogue': entries, 'cases': cases, 'fingerprint': manifest['fingerprint']}
    plotly = go.Figure().to_html(full_html=False, include_plotlyjs=True)
    template = Path(__file__).with_suffix('.html').read_text()
    page = template.replace('<!--PLOTLY-->', plotly).replace('<!--DATA-->', json.dumps(payload, allow_nan=False).replace('<', '\\u003c'))
    registry = out / 'mlflow-runs.json'
    if registry.exists():
        eid = json.loads(registry.read_text())['experiment_id']
        page = page.replace('<!--MLFLOW-->', f'<a href="http://127.0.0.1:5050/#/experiments/{eid}/runs?workflowType=machine_learning">Open suite in MLflow</a> · ')
    else:
        page = page.replace('<!--MLFLOW-->', '')
    (out / 'index.html').write_text(page)
    latest = {'directory': str(out), 'source': str(directory), 'url': f'http://127.0.0.1:8765/strategy-suite/{manifest["fingerprint"][:16]}/index.html'}
    (ROOT / '.local/performance/strategy-suite-latest.json').write_text(json.dumps(latest))
    home = ROOT / '.local/performance/index.html'
    if home.exists():
        html = re.sub(r'<p id="strategy-suite-link">.*?</p>', '', home.read_text())
        link = f'<p id="strategy-suite-link"><a href="strategy-suite/{manifest["fingerprint"][:16]}/index.html">SPY strategy catalogue: audited comparisons and blocked candidates</a></p>'
        home.write_text(html.replace('</body>', link + '</body>'))
    return out
