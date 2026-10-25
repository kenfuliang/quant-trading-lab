"""Calendar-year comparisons derived from validated, initially anchored equity."""
import json
from pathlib import Path

import numpy as np
import pandas as pd


def calmar(return_pct, drawdown_pct):
    """Undefined when no drawdown was observed; never manufacture infinity."""
    return float(return_pct / abs(drawdown_pct)) if abs(drawdown_pct) > 0 else float('nan')


def sharpe(returns):
    """Daily simple returns; sample stdev, 252 sessions and zero risk-free rate."""
    values = np.asarray(returns, dtype=float)
    if len(values) < 2 or not np.isfinite(values).all():
        return float('nan')
    deviation = values.std(ddof=1)
    if np.isclose(deviation, 0, rtol=0, atol=1e-15):
        return float('nan')
    return float(values.mean() / deviation * np.sqrt(252))


def score_ranks(values):
    """Competition ranks descending; exact ties share rank, undefined unranked."""
    return pd.Series(values, dtype=float).rank(ascending=False, method='min', na_option='keep')


def annual_metrics(curve):
    """Exclude the synthetic first anchor; reset each year's high-water mark."""
    equity = curve['equity_usd']
    if (len(equity) < 2 or equity.index.hasnans or equity.index.has_duplicates
            or not equity.index.is_monotonic_increasing
            or not np.isfinite(equity).all() or (equity <= 0).any()):
        raise ValueError('Annual comparison requires positive ordered anchored equity.')
    rows = []
    for year, observations in equity.iloc[1:].groupby(equity.index[1:].year):
        first = equity.index.get_loc(observations.index[0])
        opening = float(equity.iloc[first - 1])
        values = np.r_[opening, observations.to_numpy()]
        rows.append({'year': int(year), 'sessions': len(observations),
                     'opening_equity_usd': opening, 'ending_equity_usd': float(values[-1]),
                     'annual_return_pct': (values[-1] / opening - 1) * 100,
                     'annual_max_drawdown_pct': float((values / np.maximum.accumulate(values) - 1).min() * 100)})
    result = pd.DataFrame(rows)
    result['annual_calmar'] = [calmar(r['annual_return_pct'], r['annual_max_drawdown_pct']) for r in rows]
    daily = equity.pct_change().iloc[1:]
    result['annual_sharpe_zero_rf'] = [sharpe(daily[daily.index.year == year]) for year in result.year]
    return result


def write_annual_comparison(loaded, destination, labels, summaries):
    """Keep financial evidence separate from a small sortable browser view."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    tables = {mode: annual_metrics(loaded[mode][0]) for mode in labels}
    comparison = pd.DataFrame(index=tables['trend'].year.to_numpy())
    comparison.index.name = 'year'
    score_rows = []
    for mode, table in tables.items():
        if not np.array_equal(comparison.index, table.year):
            raise ValueError('Annual comparison requires matched years.')
        for key in ('annual_return_pct', 'annual_max_drawdown_pct', 'annual_calmar', 'annual_sharpe_zero_rf'):
            comparison[f'{mode}_{key}'] = table[key].to_numpy()
        for row in table.to_dict('records'):
            score_rows.append({'period': str(row['year']), 'strategy': labels[mode], 'mode': mode,
                               'return_pct': row['annual_return_pct'], 'drawdown_pct': row['annual_max_drawdown_pct'],
                               'calmar': row['annual_calmar'], 'sharpe': row['annual_sharpe_zero_rf']})
        metrics = summaries[mode]
        score_rows.append({'period': 'Overall', 'strategy': labels[mode], 'mode': mode,
                           'return_pct': metrics['cagr_pct'], 'drawdown_pct': metrics['max_drawdown_pct'],
                           'calmar': calmar(metrics['cagr_pct'], metrics['max_drawdown_pct']),
                           'sharpe': metrics['sharpe_zero_rf']})
    scores = pd.DataFrame(score_rows)
    for key in ('calmar', 'sharpe'):
        scores[key + '_rank'] = scores.groupby('period')[key].transform(score_ranks)
    comparison['ema_return_advantage_pp'] = comparison.trend_annual_return_pct - comparison.buy_hold_annual_return_pct
    def winner(left, right):
        return np.where(~np.isfinite(left) | ~np.isfinite(right), 'N/A',
                        np.where(np.isclose(left, right, atol=1e-9, rtol=0), 'Tie', np.where(left > right, 'EMA', 'Buy and hold')))
    for label, key in [('higher_return', 'annual_return_pct'), ('smaller_drawdown', 'annual_max_drawdown_pct'),
                       ('higher_calmar', 'annual_calmar'), ('higher_sharpe', 'annual_sharpe_zero_rf')]:
        comparison[label] = winner(comparison['trend_' + key], comparison['buy_hold_' + key])
    comparison.to_csv(Path(destination) / 'annual-comparison.csv', index_label='year')
    scores.to_csv(Path(destination) / 'score-ranking.csv', index=False)
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=.08,
                        subplot_titles=('Calendar-year return (%)', 'Within-year maximum drawdown (%)',
                                        'Annual Calmar: annual return / absolute within-year drawdown', 'Annualized Sharpe: 0% risk-free'))
    for mode, color in [('trend', '#2272b4'), ('buy_hold', '#de7921')]:
        table = tables[mode]
        for row, key in enumerate(('annual_return_pct', 'annual_max_drawdown_pct', 'annual_calmar', 'annual_sharpe_zero_rf'), 1):
            fig.add_trace(go.Bar(x=table.year, y=table[key], name=labels[mode], legendgroup=mode,
                                showlegend=row == 1, marker_color=color,
                                hovertemplate='%{x}: %{y:.3f}<extra>' + labels[mode] + '</extra>'), row=row, col=1)
    fig.update_layout(barmode='group', height=1150, template='plotly_white', margin=dict(l=55, r=20, t=65, b=35))
    fig.update_xaxes(dtick=1)
    records = json.loads(scores.to_json(orient='records', double_precision=15))  # NaN -> JSON null
    payload = json.dumps(records, allow_nan=False).replace('<', '\u003c')
    template = Path(__file__).with_name('comparison.html').read_text()
    page = template.replace('<!--SCORE_DATA-->', payload).replace('<!--CHARTS-->', fig.to_html(full_html=False, include_plotlyjs=True))
    (Path(destination) / 'annual-comparison.html').write_text(page)
    for mode in labels:
        folder = Path(destination) / mode
        table = tables[mode].copy()
        ranked = scores[(scores['mode'] == mode) & (scores.period != 'Overall')].set_index('period')
        for key in ('calmar_rank', 'sharpe_rank'):
            table[key] = [ranked.loc[str(year), key] for year in table.year]
        table.to_csv(folder / 'annual.csv', index=False)
        (folder / 'annual-comparison.html').write_text(page.replace('href="../"', 'href="http://127.0.0.1:8765/"'))
        comparison.to_csv(folder / 'annual-comparison.csv', index_label='year')
        scores.to_csv(folder / 'score-ranking.csv', index=False)
    return comparison
