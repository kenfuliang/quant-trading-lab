"""Reserve one aggregate goal launch before UI dispatch. Never launches a run."""
import json,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/'.local/selection-completion-v1'
f=RAW/'attempts.json';d=json.loads(f.read_text());case=sys.argv[1];now=datetime.now(timezone.utc)
if d['status'] not in ('diagnosis-active','financial-active') or len(d['attempts'])>=d['max_total_attempts'] or now>=datetime.fromisoformat(d['deadline_utc']):raise SystemExit('Closed/cap/deadline prevents launch')
if case not in d['source_hashes']:raise SystemExit('Case source not frozen')
h=hashlib.sha256((RAW/f'{case}-source.py').read_bytes()).hexdigest()
if h!=d['source_hashes'][case]:raise SystemExit('Source identity mismatch')
retry='--retry' in sys.argv
kind='technical-retry' if retry else ('diagnostic' if case.endswith('_probe') else 'financial')
if not retry and any(a['case']==case for a in d['attempts']):raise SystemExit('Existing case requires explicit technical retry')
if retry:
 if sum(a.get('kind')=='technical-retry' for a in d['attempts'])>=3:raise SystemExit('Technical retry budget exhausted')
 if not any(a['case']==case and (a['status'].startswith('failed') or (a.get('kind')=='diagnostic' and a.get('evidence_scope')=='failed-incomplete-cohort-coverage')) for a in d['attempts']):raise SystemExit('Retry needs preserved failure')
elif kind=='diagnostic':
 if sum(a.get('kind')=='diagnostic' for a in d['attempts'])>=2:raise SystemExit('Diagnostic budget exhausted')
elif sum(a.get('kind')=='financial' for a in d['attempts'])>=9:raise SystemExit('Financial case budget exhausted')
if not case.endswith('_probe') and d['status']!='financial-active':raise SystemExit('Financial execution not yet qualified')
a=dict(kind=kind,attempt=len(d['attempts'])+1,case=case,status='reserved',source_sha256=h,reserved_utc=now.isoformat());d['attempts'].append(a);f.write_text(json.dumps(d,indent=2)+'\n');print(a)
