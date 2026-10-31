"""Reserve a declared hosted trial before browser launch; does not execute it."""
import json,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=json.loads((ROOT/'research/plans/qc504-ablation-v1.json').read_text())
f=ROOT/'.local/qc504-ablation-v1/attempts.json';d=json.loads(f.read_text());case=sys.argv[1]
now=datetime.now(timezone.utc)
if case not in p['cases'] or len(d['attempts'])>=p['max_financial_attempts'] or now>=datetime.fromisoformat(p['deadline_utc']):raise SystemExit('Trial not eligible: case/cap/deadline')
d['attempts'].append(dict(attempt=len(d['attempts'])+1,case=case,status='reserved',reserved_utc=now.isoformat(),source_sha256=p['source_hashes'][case]));f.write_text(json.dumps(d,indent=2)+'\n');print(d['attempts'][-1])
