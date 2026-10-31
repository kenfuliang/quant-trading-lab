"""Read-only verification of saved aggregates, provenance and the bounded ledger."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.studies.checkpoint_20261031.capm_ablation import CASES, audit_records, decode_fragments, factorial_effects
ROOT=Path('.local/capm-ablation-v1')
OUT=Path('.local/performance/capm-ablation-v1')


def audit():
    plan=json.loads(Path('research/plans/capm-ablation-v1.json').read_text())
    budget=json.loads((ROOT/'budget.json').read_text())
    report=json.loads((OUT/'review.json').read_text())
    manifest=json.loads((OUT/'manifest.json').read_text())
    for row in manifest['files']:
        data=Path(row['path']).read_bytes()
        if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:
            raise ValueError('Manifest drift: '+row['path'])
    for path,digest in plan['input_hashes'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:
            raise ValueError('Frozen input drift: '+path)
    if len(budget['attempts'])>11 or budget['status']!='closed' or any(r['status']=='reserved' for r in budget['attempts']):
        raise ValueError('Open or excessive budget')
    counts={c:sum(r['case']==c for r in budget['attempts']) for c in CASES}
    if sum(max(0,n-1) for n in counts.values())>2:
        raise ValueError('Retry cap exceeded')
    if [r['id'] for r in budget['attempts']]!=list(range(1,len(budget['attempts'])+1)):
        raise ValueError('Noncontiguous attempts')
    for row in budget['attempts']:
        if not datetime.fromisoformat(plan['created_utc']) <= datetime.fromisoformat(row['reserved_utc']) <= datetime.fromisoformat(plan['deadline_utc']):
            raise ValueError('Reservation outside bounded window')
    results={}
    for c in CASES:
        completed=[r for r in budget['attempts'] if r['case']==c and r['status']=='completed']
        if len(completed)!=1:
            raise ValueError('Expected exactly one completed run: '+c)
        if completed[0]['source_sha256']!=plan['source_hashes'][c]:
            raise ValueError('Actual source hash drift: '+c)
        rows=decode_fragments(json.loads((ROOT/(c+'-fragments.json')).read_text()),c)
        checks=audit_records(rows,c)
        status=(ROOT/(c+'-visible-status.txt')).read_text()
        proof=json.loads((ROOT/(c+'-editor-verification.json')).read_text())
        if proof['source_sha256']!=plan['source_hashes'][c] or not proof['saved_and_reloaded_equal']:
            raise ValueError('Persisted editor source unverified: '+c)
        if 'v2.5.0.0.18209' not in status or ('Algorithm Id:('+completed[0]['backtest_id']+') completed') not in status or ('ABL_START|'+c+'|') not in status or checks['source_token'] not in status or 'Runtime Error' in status:
            raise ValueError('Actual run identity/completion failed: '+c)
        if rows!=report['results'][c] or rows!=json.loads((ROOT/(c+'-summary.json')).read_text()):
            raise ValueError('Packet/summary/report mismatch: '+c)
        results[c]=rows
    full=lambda c: next(r for r in results[c] if r['kind']=='full')
    if len({full(c)['audit']['calendar_hash'] for c in CASES})!=1:
        raise ValueError('Calendar mismatch')
    if len({full(c)['audit']['selection_hash'] for c in CASES if c.startswith('c')})!=1:
        raise ValueError('Selection mismatch')
    for c,old in [('c25_on','capm'),('s25','spy')]:
        prior=json.loads((Path('.local/capm-spy-v1')/(old+'-summary.json')).read_text())
        if any(a['metrics']!=b['metrics'] for a,b in zip(prior,results[c])) or len(prior)!=len(results[c]):
            raise ValueError('Prior control mismatch')
    if report['effects']!=factorial_effects(results) or not report['eligible']:
        raise ValueError('Contrast or qualification mismatch')
    browser=json.loads((OUT/'browser-audit.json').read_text())
    if {r['filter'] for r in browser['filters']}!={'all','zero','fees','stress'} or any(not r['all_cells_match'] or r['full_rows']!=(9 if r['filter']=='all' else 3) or r['annual_rows']!=(90 if r['filter']=='all' else 30) for r in browser['filters']):
        raise ValueError('Browser table verification incomplete')
    if {r['metric'] for r in browser['charts']}!={'ret','dd','sharpe','annual_calmar','uw_fraction','longest_uw','longest_uw_days'} or any(not r['all_values_match'] or r['points']!=30 for r in browser['charts']):
        raise ValueError('Browser chart verification incomplete')
    if {r['period'] for r in browser['contrasts']}!={'full',*[str(y) for y in range(2016,2026)]} or any(not r['all_values_match'] or r['rows']!=8 for r in browser['contrasts']) or not browser['completed_status_visible']:
        raise ValueError('Browser contrast/status verification incomplete')
    first=budget['attempts'][0]
    preserved=ROOT/'superseded/attempt1'
    if first['status']!='failed-before-first-close' or hashlib.sha256((preserved/'source.py').read_bytes()).hexdigest()!=first['source_sha256'] or hashlib.sha256((preserved/'plan.json').read_bytes()).hexdigest()!=plan['technical_amendments'][0]['old_plan_sha256']:
        raise ValueError('First failure/amendment not preserved')
    return dict(passed=True,cases=9,annual_rows=90,attempts=len(budget['attempts']),manifest_files=len(manifest['files']))

if __name__=='__main__':
    print(json.dumps(audit()))
