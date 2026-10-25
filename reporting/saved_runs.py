"""Render native Nautilus tearsheets from immutable saved portfolio evidence."""
import hashlib
import html
import json
from pathlib import Path
import shutil
from urllib.parse import urlencode

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / 'reports/spy/20261024-235746-728801'
OUTPUT = ROOT / '.local/performance'
LABELS = {'trend': 'SPY EMA 50-200', 'buy_hold': 'SPY Buy and hold'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_curve(path, initial, expected):
    curve = pd.read_csv(path, parse_dates=['date']).set_index('date')
    if curve.empty or curve.index.has_duplicates or not curve.index.is_monotonic_increasing:
        raise ValueError('Equity dates must be nonempty, unique and increasing.')
    equity = curve.equity.astype(float)
    if not np.isfinite(equity).all() or (equity <= 0).any() or not np.isfinite(initial) or initial <= 0:
        raise ValueError('Equity and starting capital must be finite and positive.')
    if len(equity) != expected['sessions'] or abs(equity.iloc[-1] - expected['ending_equity']) > .005:
        raise ValueError('Curve does not match saved summary.')
    anchored = pd.concat([pd.Series([initial], index=[equity.index[0] - pd.Timedelta(days=1)]), equity])
    returns = anchored.pct_change().fillna(0)
    drawdown = anchored / anchored.cummax() - 1
    if abs(drawdown.min() * 100 - expected['max_drawdown_pct']) > 1e-7:
        raise ValueError('Drawdown does not reconcile to saved summary.')
    if abs((anchored.iloc[-1] / initial - 1) * 100 - expected['total_return_pct']) > 1e-7:
        raise ValueError('Total return does not reconcile to saved summary.')
    return pd.DataFrame({'equity_usd': anchored, 'return_pct': returns * 100, 'drawdown_pct': drawdown * 100}), returns


def prepare(source=DEFAULT_SOURCE, output=OUTPUT):
    from nautilus_trader.analysis import (
        TearsheetConfig, TearsheetStatsTableChart, TearsheetEquityChart,
        TearsheetDrawdownChart, TearsheetMonthlyReturnsChart, TearsheetYearlyReturnsChart,
    )
    from nautilus_trader.analysis.tearsheet import create_tearsheet_from_stats
    source = Path(source).resolve()
    manifest = json.loads((source / 'manifest.json').read_text())
    summaries = json.loads((source / 'summary.json').read_text())
    if manifest['status'] != 'completed' or not all(manifest['audits'][m]['passed'] for m in LABELS):
        raise ValueError('Source must be completed and independently audited.')
    if digest(source / 'source-data.json') != manifest['source']['sha256']:
        raise ValueError('Source snapshot hash mismatch.')
    names = ['manifest.json', 'summary.json'] + [f'{m}_equity.csv' for m in LABELS]
    source_hashes = {n: digest(source / n) for n in names}
    fingerprint = hashlib.sha256(json.dumps({'files': source_hashes, 'report_contract': 1}, sort_keys=True).encode()).hexdigest()
    destination = Path(output) / fingerprint[:16]
    destination.mkdir(parents=True, exist_ok=True)
    initial = manifest['parameters']['initial_cash_usd']
    loaded = {m: read_curve(source / f'{m}_equity.csv', initial, summaries[m]) for m in LABELS}
    if not loaded['trend'][0].index.equals(loaded['buy_hold'][0].index):
        raise ValueError('Portfolios have different evaluation dates.')
    config = TearsheetConfig(charts=[TearsheetStatsTableChart(), TearsheetEquityChart(), TearsheetDrawdownChart(), TearsheetMonthlyReturnsChart(), TearsheetYearlyReturnsChart()], height=1800)
    notice = ('Historical simulation imported from saved results; no strategy rerun. '
              '2005–2025; USD 100,000 start; cash dividends without automatic reinvestment; '
              '5 bps per side and $1 per order; zero cash interest/taxes. '
              'An initial zero-return anchor precedes the first session for chart drawdown accuracy. '
              'Statistics below retain the audited source definitions; charts use saved portfolio returns. '
              'This is not a $300,000 leveraged scenario or a forecast.')
    runs = []
    for mode, label in LABELS.items():
        folder = destination / mode
        folder.mkdir(exist_ok=True)
        curve, returns = loaded[mode]
        curve.to_csv(folder / 'equity.csv', index_label='date')
        from reporting.annual import calmar
        metrics = dict(summaries[mode], calmar_full_period=calmar(summaries[mode]['cagr_pct'], summaries[mode]['max_drawdown_pct']))
        stats = {'Audited total return (%)': f"{metrics['total_return_pct']:.4f}%",
                 'Audited CAGR (%)': f"{metrics['cagr_pct']:.4f}%",
                 'Audited max daily-close drawdown (%)': f"{metrics['max_drawdown_pct']:.4f}%",
                 'Audited annualized volatility (%)': f"{metrics['annualized_volatility_pct']:.4f}%",
                 'Full-period Calmar (derived)': f"{metrics['calmar_full_period']:.6f}",
                 'Audited Sharpe (0% risk-free)': f"{metrics['sharpe_zero_rf']:.6f}"}
        rendered = create_tearsheet_from_stats(
            stats_pnls={'USD': {'Starting equity (USD)': initial, 'Ending equity (USD)': metrics['ending_equity']}},
            stats_returns=stats, stats_general={'Filled orders': metrics['filled_orders'], 'Sessions (excluding anchor)': metrics['sessions']},
            returns=returns, output_path=None, title=f'{label} — saved historical simulation', config=config,
            benchmark_returns=loaded['buy_hold'][1] if mode == 'trend' else None,
            benchmark_name='Buy and hold, cash dividends',
        )
        rendered = rendered.replace('<head>', '<head><title>' + html.escape(label) + ' — historical report</title>', 1)
        rendered = rendered.replace('<body>', '<body><p style="padding:16px;font-family:sans-serif;background:#fff4d6">' + html.escape(notice) + '</p>', 1)
        (folder / 'tearsheet.html').write_text(rendered)
        (folder / 'metrics.json').write_text(json.dumps(metrics, indent=2))
        (folder / 'assumptions.txt').write_text(notice)
        shutil.copy2(source / 'manifest.json', folder / 'source-manifest.json')
        runs.append({'mode': mode, 'name': label, 'folder': str(folder.resolve()), 'metrics': metrics})
    from reporting.annual import write_annual_comparison
    write_annual_comparison(loaded, destination, LABELS, summaries)
    bundle = {'fingerprint': fingerprint, 'source_run': source.name, 'source_hashes': source_hashes,
              'renderer_sha256': digest(Path(__file__)), 'score_contract': 1,
              'score_renderer_hashes': {name: digest(Path(__file__).with_name(name)) for name in ('annual.py', 'comparison.html')}, 'parameters': manifest['parameters'], 'source_engine': manifest['runtime']['nautilus_trader'],
              'source_data_sha256': manifest['source']['sha256'], 'runs': runs}
    (destination / 'bundle.json').write_text(json.dumps(bundle, indent=2))
    Path(output).mkdir(parents=True, exist_ok=True)
    (Path(output) / 'current.json').write_text(json.dumps({'bundle': str((destination / 'bundle.json').resolve())}))
    return destination / 'bundle.json'


def write_index(bundle_path, registry):
    bundle = json.loads(Path(bundle_path).read_text())
    links = ''.join(f'<li><a href="{bundle["fingerprint"][:16]}/{r["mode"]}/tearsheet.html">{html.escape(r["name"])} — native report</a></li>' for r in bundle['runs'])
    ids = [r['run_id'] for r in registry['runs']]
    comparison = html.escape('http://127.0.0.1:5050/#/compare-runs?' + urlencode({'runs': json.dumps(ids), 'experiments': json.dumps([registry['experiment_id']])}), quote=True)
    page = f'''<!doctype html><html><head><meta charset="utf-8"><title>Local strategy performance</title></head>
<body style="font:18px system-ui;max-width:900px;margin:60px auto;padding:20px"><h1>Local strategy performance</h1>
<p>Saved SPY historical simulations · 2005–2025 · $100,000 each · no strategy rerun.</p>
<p><a href="{bundle["fingerprint"][:16]}/annual-comparison.html">Rank strategies by Calmar and Sharpe · overall and annual</a> · <a href="{bundle["fingerprint"][:16]}/annual-comparison.csv">Annual CSV</a></p>
<ul>{links}</ul><p><a href="http://127.0.0.1:5050/#/experiments/{registry['experiment_id']}/runs?workflowType=machine_learning">MLflow strategy runs</a></p>
<p><a href="{comparison}">Compare both strategies in MLflow</a></p>
<p>Cash dividends; no automatic reinvestment. Illustrative trading costs. See each report for assumptions.</p>
<p>These results are not a $300,000 leveraged scenario or a forecast.</p></body></html>'''
    (Path(bundle_path).parents[1] / 'index.html').write_text(page)
