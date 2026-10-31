"""Reserve a declared funded-study case; never launch a backtest."""
import hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/'.local/qc-breadth-v1'
p=json.loads((ROOT/'research/plans/qc-breadth-v1.json').read_text());f=RAW/'attempts.json';d=json.loads(f.read_text());case=sys.argv[1];now=datetime.now(timezone.utc)
if case not in p['cases'] or len(d['attempts'])>=p['max_financial_attempts'] or now>=datetime.fromisoformat(p['deadline_utc']) or d['status']!='active':raise SystemExit('Case/cap/deadline/closed study prevents launch')
if case!='access':
    access_path=RAW/'access-result.json'
    if not access_path.exists():raise SystemExit('Access probe evidence required')
    access=json.loads(access_path.read_text())
    if access.get('etf_full_history')!=5 or access.get('stock_full_history',0)<5 or access.get('orders')!=0:raise SystemExit('Access check failed')
h=hashlib.sha256((RAW/f'{case}-source.py').read_bytes()).hexdigest()
if h!=p['source_hashes'][case]:raise SystemExit('Source hash mismatch')
d['attempts'].append(dict(attempt=len(d['attempts'])+1,case=case,status='reserved',reserved_utc=now.isoformat(),source_sha256=h));f.write_text(json.dumps(d,indent=2)+'\n');print(d['attempts'][-1])
