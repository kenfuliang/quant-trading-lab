"""Close a reserved launch only with checksummed summaries and native completion."""
import hashlib,json,re,sys
from pathlib import Path
from parse_selection_completion_fragments import decode
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/'.local/selection-completion-v1'
case=sys.argv[1];lines=decode(json.loads((RAW/f'{case}-terminal-fragments.json').read_text()),case)
engine=json.loads((RAW/f'{case}-engine-evidence.json').read_text())
if len(engine)!=2 or 'LEAN Engine v2.5.0.0.18209' not in engine[0] or 'completed in' not in engine[1]:raise SystemExit('Native completion missing')
bt=re.search(r'Launching analysis for ([a-f0-9]{32}) ',engine[0])[1]
if bt not in engine[1]:raise SystemExit('Native run identity mismatch')
f=RAW/'attempts.json';j=json.loads(f.read_text());a=[a for a in j['attempts'] if a['case']==case and a['status']=='reserved']
if len(a)!=1 or hashlib.sha256((RAW/f'{case}-source.py').read_bytes()).hexdigest()!=a[0]['source_sha256']:raise SystemExit('Reservation/source identity mismatch')
rows=[json.loads(x) for x in lines]
if not case.endswith('_probe'):
 full=[r for r in rows if r.get('kind')=='overall']
 if len(full)!=1 or full[0]['n']!=1508 or any(full[0][k] for k in ['rejects','other_fills','pending_orders','feature_future','feature_invalid','feature_unordered']):raise SystemExit('Incomplete/failed financial evidence')
(RAW/f'{case}-summary-cells.json').write_text(json.dumps(lines,indent=2)+'\n')
a[0].update(status='completed-verified',backtest_id=bt);f.write_text(json.dumps(j,indent=2)+'\n');print(case,bt,len(lines),'checksummed records')
