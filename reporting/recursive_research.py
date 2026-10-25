"""Dependency-free review of supplied research evidence; no financial computation."""
from html import escape
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit


STYLE = '''
:root{color-scheme:light;--ink:#182b36;--muted:#56636b;--line:#d9dfdf;--teal:#146d72;--bg:#f6f5f1}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,sans-serif}
main{max-width:1280px;margin:auto;padding:36px 28px 70px}header{border-top:5px solid var(--teal);padding:24px 0 16px}
h1{font-size:clamp(28px,4vw,44px);line-height:1.15;letter-spacing:-.03em;margin:8px 0 16px}h2{font-size:24px;margin:0 0 14px}h3{font-size:17px}
p{max-width:95ch}a{color:#075e83;text-underline-offset:3px}nav{display:flex;flex-wrap:wrap;gap:10px 20px;padding:16px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
section{margin-top:32px;padding:24px;background:#fff;border:1px solid var(--line);border-radius:8px}.meta,.note{color:var(--muted);font-size:13px}.warning{border-left:4px solid #a66d16;background:#fff8e7;padding:12px 16px;max-width:none}
.flow{display:flex;align-items:center;flex-wrap:wrap;gap:9px}.flow span{padding:8px 12px;border:1px solid var(--line);background:#f0f6f5;border-radius:4px}.flow b{color:var(--teal)}
.scroll{overflow:auto}table{border-collapse:collapse;min-width:560px;width:100%;font-size:13px}th{text-align:left;font-size:12px;color:var(--muted);background:#f3f6f5;white-space:nowrap}td,th{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}td{overflow-wrap:anywhere;max-width:480px}td:first-child,th:first-child{min-width:130px}#temporal td:nth-child(2),#financial td:nth-child(3){min-width:180px}td.number{text-align:right;font-variant-numeric:tabular-nums}td.unknown{color:#85621f;font-style:italic}tbody tr:hover{background:#f7faf9}#risk-gates-table th:nth-child(2){background:#e3f2e8;color:#245b38}#risk-gates-table th:nth-child(3){background:#fff2cd;color:#745200}#risk-gates-table th:nth-child(4){background:#fbe2df;color:#8c2c25}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:18px 0}.card{padding:14px 16px;background:white;border:1px solid var(--line);border-radius:6px}.card strong{display:block;font-size:26px;color:var(--teal)}.card span{color:var(--muted);font-size:13px}svg{display:block;width:100%;max-width:900px;height:auto}select{font:inherit;padding:6px 12px;margin:0 0 14px 8px}li{margin:6px 0}details{margin:14px 0}code{font-family:ui-monospace,monospace;font-size:12px}footer{padding-top:24px;color:var(--muted);font-size:12px}
@media(max-width:640px){main{padding:18px 12px}section{padding:16px}td,th{padding:8px}.flow{font-size:12px}}
'''
SCRIPT = '''
const yearSelect=document.getElementById('year-filter');
if(yearSelect){yearSelect.addEventListener('change',()=>{
 document.querySelectorAll('#annual-table tbody tr').forEach(row=>{
  row.hidden=yearSelect.value!=='all'&&row.dataset.year!==yearSelect.value;
 });
});}
'''


def clean(value):
    """Display nonfinite/missing values as unknown, never favorable numeric zero."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return value


def text(value):
    if value is None or value == '':
        return 'Unknown'
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    return str(value)


def safe_link(url):
    """Reject active-content schemes and browser-normalized protocol-relative URLs."""
    if not isinstance(url, str) or not url.strip() or any(ord(c) < 32 for c in url) or '\\' in url:
        return None
    value = url.strip()
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme.lower() not in ('', 'http', 'https') or value.startswith('//'):
        return None
    if parsed.scheme and not parsed.netloc:
        return None
    return value


def _rows(bundle, name):
    result = bundle.get(name, [])
    if result is None:
        return []
    if not isinstance(result, list) or any(not isinstance(x, dict) for x in result):
        raise ValueError(name + ' must be a list of objects.')
    return result


def _flatten(row):
    result = {k: v for k, v in row.items() if k not in ('metrics', 'annual')}
    if isinstance(row.get('metrics'), dict):
        for key, value in row['metrics'].items():
            result.setdefault(key, value)
    return result


def _table(rows, table_id=None, prefer=(), annual=False):
    if not rows:
        return '<p class="note">Unknown — no evidence supplied for this section.</p>'
    keys = list(dict.fromkeys(key for row in rows for key in row))
    keys = [k for k in prefer if k in keys] + [k for k in keys if k not in prefer]
    ident = f' id="{escape(table_id, quote=True)}"' if table_id else ''
    labels = {'return_pct': 'Return (%)' if annual else 'CAGR (%)', 'drawdown_pct':'Max DD (%)','max_drawdown_pct':'Max DD (%)',
              'commission_usd':'Commission ($)', 'slippage_usd':'Execution cost ($)',
              'financing_usd':'Financing ($)', 'mean_close_exposure':'Avg exposure (×)',
              'longest_underwater_sessions':'Longest underwater (sessions)',
              'longest_underwater_calendar_days':'Longest underwater (days)',
              'longest_right_censored':'Unrecovered at end?',
              'worst_21_session_return_pct':'Worst 21 sessions (%)',
              'worst_63_session_return_pct':'Worst 63 sessions (%)',
              'historical_daily_ES95_loss_pct':'Daily ES95 loss (%)'}
    head = ''.join('<th scope="col">' + escape(labels.get(k,k.replace('_', ' '))) + '</th>' for k in keys)
    body = []
    for row in rows:
        year = str(row.get('year', row.get('period', 'Unknown')))
        attr = ' data-year="' + escape(year, quote=True) + '"' if annual else ''
        cells = []
        for key in keys:
            value = row.get(key)
            missing = value is None or value == ''
            number = isinstance(value, (int, float)) and not isinstance(value, bool)
            css = 'unknown' if missing else 'number' if number else ''
            display = f'{value:,.3f}'.rstrip('0').rstrip('.') if number and not isinstance(value, int) else text(value)
            cells.append(f'<td class="{css}">{escape(display)}</td>')
        body.append('<tr' + attr + '>' + ''.join(cells) + '</tr>')
    return '<div class="scroll"><table' + ident + '><thead><tr>' + head + '</tr></thead><tbody>' + ''.join(body) + '</tbody></table></div>'


def _scatter(rows):
    valid = [r for r in rows if isinstance(r.get('return_pct'), (int, float)) and not isinstance(r.get('return_pct'), bool)
             and isinstance(r.get('drawdown_pct'), (int, float)) and not isinstance(r.get('drawdown_pct'), bool)
             and r['drawdown_pct'] <= 0]
    if not valid:
        return '<p class="note">Return/drawdown plot unavailable: both numeric measurements are required.</p>'
    xmax = max(1., max(abs(r['drawdown_pct']) for r in valid) * 1.12)
    ymin = min(0., min(r['return_pct'] for r in valid)); ymax = max(0., max(r['return_pct'] for r in valid))
    pad = max(1., (ymax - ymin) * .12); ymin -= pad; ymax += pad
    def x(v): return 75 + 680 * abs(v) / xmax
    def y(v): return 325 - 265 * (v - ymin) / (ymax - ymin)
    chart = ['<svg viewBox="0 0 860 400" role="img" aria-label="Supplied return versus drawdown observations"><title>Supplied return versus drawdown observations</title><desc>Drawdown magnitude increases to the right; return increases upward. This plot does not infer statistical superiority.</desc>']
    for i in range(5):
        xx = xmax * i / 4; yy = ymin + (ymax - ymin) * i / 4
        chart.append(f'<line x1="75" y1="{y(yy):.2f}" x2="755" y2="{y(yy):.2f}" stroke="#e0e5e5"/><text x="65" y="{y(yy)+4:.2f}" text-anchor="end" fill="#56636b" font-size="12">{yy:.1f}%</text>')
        chart.append(f'<text x="{x(xx):.2f}" y="348" text-anchor="middle" fill="#56636b" font-size="12">{xx:.1f}%</text>')
    chart.append('<path d="M75 60V325H755" fill="none" stroke="#89989e"/><text x="410" y="383" text-anchor="middle" font-size="13">Daily-close maximum drawdown magnitude</text><text x="22" y="195" transform="rotate(-90 22 195)" text-anchor="middle" font-size="13">Full-period CAGR</text>')
    for i, row in enumerate(valid):
        label = text(row.get('label', row.get('candidate_id', row.get('case_id'))))
        tip = f"{label}: CAGR {row['return_pct']:.3f}%; drawdown {row['drawdown_pct']:.3f}%"
        chart.append(f'<g><title>{escape(tip)}</title><circle cx="{x(row["drawdown_pct"]):.2f}" cy="{y(row["return_pct"]):.2f}" r="5" fill="#146d72"/><text x="{x(row["drawdown_pct"])+8:.2f}" y="{y(row["return_pct"])-7-(i%2)*9:.2f}" fill="#182b36" font-size="11">{escape(label)}</text></g>')
    return ''.join(chart) + '</svg>'


def render(bundle, output_dir):
    """Write index.html plus the supplied normalized bundle; no service side effects.

    Optional fields: title, generated_at, status, review_at, summary(list[str]),
    goals/inventory/prerequisites/priors/candidates/annual/pareto/decisions(list[dict]),
    budgets(dict), limitations(list[str]), evidence(list[{label,url}]). Candidates
    may contain metrics and annual subobjects. Absent sections remain explicit.
    """
    if not isinstance(bundle, dict) or bundle.get('schema_version', 1) != 1:
        raise ValueError('Expected review bundle schema version 1.')
    data = clean(bundle)
    sections = {name: _rows(data, name) for name in ('goals', 'inventory', 'prerequisites', 'priors', 'candidates', 'annual', 'pareto', 'decisions', 'temporal', 'risk_gates', 'evidence')}
    for name in ('summary', 'limitations'):
        if not isinstance(data.get(name, []), list) or any(not isinstance(x, str) for x in data.get(name, [])):
            raise ValueError(name + ' must be a list of text.')
    if not isinstance(data.get('budgets', {}), dict):
        raise ValueError('budgets must be an object.')
    title = escape(text(data.get('title', 'Recursive research review')))
    candidates = [_flatten(r) for r in sections['candidates']]
    annual = [_flatten(r) for r in sections['annual']]
    for candidate in sections['candidates']:
        if candidate.get('annual') is not None:
            if not isinstance(candidate['annual'], list) or any(not isinstance(r, dict) for r in candidate['annual']):
                raise ValueError('Candidate annual values must be objects.')
            for row in candidate['annual']:
                annual.append({'candidate_id': candidate.get('candidate_id', candidate.get('case_id', candidate.get('label'))), **_flatten(row)})
    parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>' + title + '</title><style>' + STYLE + '</style></head><body><main><header><p class="meta">LOCAL RESEARCH · SUPPLIED EVIDENCE REVIEW</p><h1>' + title + '</h1>']
    parts.append('<p class="meta">Status: ' + escape(text(data.get('status'))) + ' · Generated: ' + escape(text(data.get('generated_at'))) + ' · Review target: ' + escape(text(data.get('review_at'))) + '</p>')
    for line in data.get('summary', []):
        parts.append('<p>' + escape(line) + '</p>')
    parts.append('<p class="warning">Development evidence. A simulated improvement does not establish an unseen trading edge, a trained research policy, or paper/live readiness. Missing evidence remains Unknown.</p></header>')
    parts.append('<nav aria-label="Review sections">' + ''.join(f'<a href="#{anchor}">{label}</a>' for anchor, label in [('goals','Goals'),('inventory','What exists'),('priors','Prior research'),('financial','Financial results'),('annual','Year by year'),('temporal','Path and recovery'),('risk-gates','Risk gates'),('decisions','Research decisions'),('prerequisites','Next prerequisites'),('evidence','Evidence')]) + '</nav>')
    cards = [('Candidates supplied', len(candidates)), ('Annual observations supplied', len(annual)), ('Decision / evaluation records', len(sections['decisions']))]
    parts.append('<div class="cards">' + ''.join(f'<div class="card"><strong>{value}</strong><span>{label}</span></div>' for label, value in cards) + '</div>')
    parts.append('<section aria-labelledby="flow-heading"><h2 id="flow-heading">How research evolves</h2><div class="flow" role="img" aria-label="Evidence to fixed plan to bounded experiment to diagnosis to decision to retained history">' + '<b aria-hidden="true">→</b>'.join('<span>' + x + '</span>' for x in ('Evidence','Fixed plan','Bounded experiment','Diagnosis','Continue / explore / pause','Retained history')) + '</div><p class="note">Scores guide a declared decision. Validity, performance tradeoffs and research value are separate judgments.</p></section>')
    def section(anchor, heading, body):
        parts.append(f'<section id="{anchor}"><h2>{heading}</h2>{body}</section>')
    section('goals', 'Goal and research objective', _table(sections['goals']))
    section('inventory', 'What exists — status and verification', _table(sections['inventory']))
    section('priors', 'Prior research — claims, evidence and reuse', _table(sections['priors']))
    contexts = {}
    for row in candidates:
        context = text(row.get('context', 'Supplied comparison context'))
        contexts.setdefault(context, []).append(row)
    figures = ''.join('<h3>' + escape(context) + '</h3>' + _scatter(rows) for context, rows in contexts.items())
    section('financial', 'Financial candidates — full period', '<p class="note">Overall return_pct is CAGR; drawdown_pct is signed daily-close drawdown. Ratios and costs retain their supplied definitions. Compare only matched contexts. Plots are descriptive and do not calculate a Pareto verdict.</p>' + figures + _table(candidates, prefer=('context','candidate_id','case_id','label','return_pct','drawdown_pct','calmar','sharpe','eligibility','pareto')) + '<h3>Supplied Pareto assessment</h3>' + _table(sections['pareto']))
    years = sorted({text(row.get('year', row.get('period'))) for row in annual})
    selector = '<label for="year-filter">Period</label><select id="year-filter"><option value="all">All supplied periods</option>' + ''.join('<option value="' + escape(year, quote=True) + '">' + escape(year) + '</option>' for year in years) + '</select>' if annual else ''
    section('annual', 'Year-by-year observations', '<p class="note">Calendar-year return is distinct from full-period CAGR. Annual drawdown resets its high-water mark; it does not replace full-path drawdown.</p>' + selector + _table(annual, table_id='annual-table', annual=True, prefer=('context','year','period','candidate_id','case_id','return_pct','drawdown_pct','calmar','sharpe')))
    temporal_url = safe_link(data.get('temporal_url'))
    temporal_link = ('<p><a href="' + escape(temporal_url, quote=True) + '">Explore interactive equity, drawdown and rolling-return paths</a></p>') if temporal_url else ''
    section('temporal', 'Path, losses and recovery', temporal_link + '<p class="note">Rolling returns are cumulative, not annualized. Longest underwater duration differs from recovery of the deepest drawdown. Unrecovered episodes are censored. Historical daily ES95 is the mean of the worst ceil(5% × observed sessions) daily returns; it is not a future loss bound. Full-window coverage is required.</p>' + _table(sections['temporal']))
    section('risk-gates', 'Green / yellow / red — research interpretation', '<p class="note">Green means the normal declared research allocation, not safety or predicted profit. Rules act on available information at the stated next execution time. Market gates and operational data/account controls have separate responsibilities. No gate guarantees protection from gaps.</p>' + _table(sections['risk_gates'],table_id='risk-gates-table'))
    budgets = [{'resource': key, 'value': value} for key, value in data.get('budgets', {}).items()]
    section('decisions', 'Decisions, branches and resource budget', _table(sections['decisions']) + '<h3>Budget ledger supplied by coordinator</h3>' + _table(budgets))
    section('prerequisites', 'What needs to exist next', _table(sections['prerequisites']))
    limitations = '<ul>' + ''.join('<li>' + escape(line) + '</li>' for line in data.get('limitations', [])) + '</ul>' if data.get('limitations') else '<p class="note">Unknown — no limitations record supplied.</p>'
    section('limitations', 'Limitations and unresolved questions', limitations)
    links = []
    for row in sections['evidence']:
        label = escape(text(row.get('label', row.get('url'))))
        url = safe_link(row.get('url'))
        links.append('<li><a href="' + escape(url, quote=True) + '" rel="noopener noreferrer">' + label + '</a></li>' if url else '<li>' + label + ' <span class="note">(link unavailable or unsupported)</span></li>')
    section('evidence', 'Evidence and source records', '<p><a href="review-bundle.json">Download supplied review bundle</a></p>' + ('<ul>' + ''.join(links) + '</ul>' if links else '<p class="note">Unknown — no evidence links supplied.</p>'))
    parts.append('<footer>Rendered from a coordinator-supplied bundle. This page starts no services, runs no simulation and imports no financial results. Nonfinite measurements display as Unknown.</footer></main><script>' + SCRIPT + '</script></body></html>')
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'review-bundle.json').write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    destination = output / 'index.html'
    destination.write_text(''.join(parts))
    return destination


def _verified_review(performance_root, reference):
    root=Path(performance_root).resolve()
    directory=(root/reference['directory']).resolve()
    if directory==root or not directory.is_relative_to(root):
        raise ValueError('Review directory must be inside the local performance root.')
    manifest_path=directory/'manifest.json'
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest()!=reference['manifest_sha256']:
        raise ValueError('Review manifest identity changed.')
    manifest=json.loads(manifest_path.read_text())
    artifacts=manifest.get('artifact_hashes',{})
    if not {'index.html','temporal.html','review-bundle.json'} <= set(artifacts):
        raise ValueError('Review manifest lacks required browser artifacts.')
    for name,sha in artifacts.items():
        artifact=(directory/name).resolve()
        if not artifact.is_relative_to(directory) or not artifact.is_file():
            raise ValueError('Review artifact is missing or outside its snapshot.')
        if hashlib.sha256(artifact.read_bytes()).hexdigest()!=sha:
            raise ValueError('Review artifact identity changed: '+name)
    return directory


def restore_review_link(performance_root):
    """Restore one verified saved-review link after performance home regeneration."""
    root=Path(performance_root)
    reference=json.loads((root/'recursive-research-latest.json').read_text())
    directory=_verified_review(root,reference)
    home=root/'index.html'
    content=home.read_text()
    content=re.sub(r'<p id="recursive-research-link">.*?</p>','',content,flags=re.S)
    href=directory.relative_to(root.resolve()).as_posix()+'/index.html'
    link='<p id="recursive-research-link"><a href="'+escape(href,quote=True)+'">Recursive research review: goals, evidence and temporal risk</a></p>'
    if '</body>' not in content:
        raise ValueError('Performance home has no closing body element.')
    home.write_text(content.replace('</body>',link+'</body>'))
    return href


def register_local_review(performance_root, directory):
    """Register an already-built local snapshot; no server or MLflow operations."""
    root=Path(performance_root).resolve();directory=Path(directory).resolve()
    if directory==root or not directory.is_relative_to(root):
        raise ValueError('Review must be inside the local performance root.')
    reference={'directory':directory.relative_to(root).as_posix(),
               'manifest_sha256':hashlib.sha256((directory/'manifest.json').read_bytes()).hexdigest()}
    _verified_review(root,reference)
    temporary=root/'recursive-research-latest.tmp'
    temporary.write_text(json.dumps(reference,indent=2)+'\n')
    temporary.replace(root/'recursive-research-latest.json')
    return restore_review_link(root)
