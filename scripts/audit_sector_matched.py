"""Read-only final verification of the closed conditional sector study."""
import hashlib,json
from pathlib import Path
from datetime import datetime
from build_sector_matched import assemble,ROOT,RAW,OUT
from sector_matched_study import decode

def audit():
 result=assemble();plan=json.loads((ROOT/'research/plans/sector-matched-v1.json').read_text());ledger=json.loads((RAW/'attempts.json').read_text())
 assert ledger['status']==plan['stage']=='closed-complete-conditional'
 assert len(ledger['attempts'])==5 and ledger['unused_attempts']==1
 assert datetime.fromisoformat(ledger['closed_utc'])<datetime.fromisoformat(ledger['deadline_utc'])
 assert sum(a['status']=='completed-verified' for a in ledger['attempts'])==4
 assert sum(a['status']=='failed-save-size' for a in ledger['attempts'])==1
 for path,digest in plan['input_hashes'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
 registry=ROOT/plan['classification_registry'];assert hashlib.sha256(registry.read_bytes()).hexdigest()==plan['classification_registry_sha256']
 for case in ['probe','original','sector','matched']:
  packet=decode(json.loads((RAW/f'{case}-terminal-fragments.json').read_text()),case)
  assert packet==json.loads((RAW/f'{case}-packet.json').read_text())
  run=next(a['backtest_id'] for a in ledger['attempts'] if a['case']==case and a['status']=='completed-verified')
  engine=json.loads((RAW/f'{case}-engine-evidence.json').read_text());assert len(engine)==2 and all(run in s for s in engine)
 restoration=json.loads((RAW/'source-restoration.json').read_text());assert restoration['restored'] and restoration['bytes']==26210
 assert restoration['sha256']==hashlib.sha256((RAW/'original-project-source.py').read_bytes()).hexdigest()
 assert restoration['buildEvidence'] and all('Built project' in s or 'All files saved' in s for s in restoration['buildEvidence'])
 ui=json.loads((RAW/'browser-audit.json').read_text());assert ui['case_month_views']==216 and len(ui['years'])==6 and ui['contribution_rows_per_case']==57
 cleanup=json.loads((RAW/'browser-cleanup.json').read_text());assert cleanup['viewportReset'] and cleanup['visibility']=='background'
 checks=(RAW/'offline-checks.log').read_text();assert 'Ran 326 tests' in checks and '\nOK\n' in checks and 'No broken requirements found' in checks
 manifest=json.loads((OUT/'manifest.json').read_text());assert set(manifest)=={p.name for p in OUT.iterdir() if p.name!='manifest.json'}
 for name,digest in manifest.items():assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==digest,name
 assert (OUT/'comparison-preview.png').stat().st_size>10000
 return {'status':'passed-conditional-development','cases':3,'diagnostic':1,'counted_attempts':5,'financial_sessions_per_case':1508,'annual_rows':len(result['annual']),'selection_rows':len(result['monthly_selections']),'contribution_rows':len(result['contributions']),'artifact_count':len(manifest),'checks':'input/source/packet checksums, control parity, target hashes, accounting, annual/temporal arithmetic, browser views, source restoration, closed budget, offline tests','exact_historical_vendor_sector_status':'unavailable; dated research inference only'}
if __name__=='__main__':print(json.dumps(audit(),indent=2))
