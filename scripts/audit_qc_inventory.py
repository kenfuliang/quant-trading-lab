"""Read-only audit of the sealed O00–O03 metadata inventory; no financial validation."""
import csv,json,hashlib
from datetime import datetime
from pathlib import Path
from build_qc_inventory import ROOT,RAW,DATA,OUT,source
from research.studies.checkpoint_20261031.qc_inventory import normalize_community,tutorial_article_observed

def read(p):return json.loads(p.read_text())
def audit():
 c=read(DATA/'catalog.json');h=read(DATA/'research-history.json');stats=c['stats']
 assert c['scope']['status']=='closed-scoped-inventory'
 assert datetime.fromisoformat(c['scope']['closed_utc'])<datetime.fromisoformat(c['scope']['deadline_utc'])
 assert c['scope']['limits']['financial_attempts']==0
 assert len(c['records'])==622 and len({r['id'] for r in c['records']})==622
 assert sum(r['source_kind']=='community' for r in c['records'])==540
 assert sum(r['source_kind']=='tutorial' for r in c['records'])==82
 assert all(r['families'] and r['families']!=['unresolved'] and not r['economic_mechanism_verified'] for r in c['records'])
 assert stats['classification_basis']=={'title':473,'public_description':64,'displayed_code_inspection':3,'official_index_description':82}
 for item in c['input_sources']:assert source(ROOT/item['path'])==item
 for item in c['processing_sources']:
  archived_code=RAW/'processing-evidence'/item['path']
  assert hashlib.sha256(archived_code.read_bytes()).hexdigest()==item['sha256']
 ui=read(RAW/'browser-audit.json');assert ui['ordered_ids_verified']==622 and ui['pages']==25 and ui['family_filters']==17 and ui['evidence_filters']==4 and ui['search_matches']==1
 checks=(RAW/'offline-checks.log').read_text();assert 'Ran 331 tests' in checks and '\nOK\n' in checks and 'No broken requirements found' in checks
 passes={n:read(RAW/f'{f}.json') for n,f in [('sharpe_desc','community-pages'),('sharpe_asc','community-pages-ascending'),('author_order','community-pages-author')]}
 rows,observations=normalize_community(passes);assert observations==1620 and len(rows)==540
 assert {r['id'] for r in rows}=={r['id'] for r in c['records'] if r['source_kind']=='community'}
 receipts=read(RAW/'tutorial-page-receipts.json');assert sum(tutorial_article_observed(r) for r in receipts)==81
 failed=[r for r in receipts if not tutorial_article_observed(r)];assert len(failed)==1 and failed[0]['final_url']=='https://www.quantconnect.com/404'
 assert len(h['studies'])==19 and all(r['receipt'] for r in h['studies']) and len(h['case_records'])==158
 assert len(h['local_ideas'])==100 and not h['parse_errors']
 assert len(h['prior_source_crosswalk'])==16 and all(r['current_catalog_match'] for r in h['prior_source_crosswalk'])
 frozen=ROOT/h['frozen_prior_evidence_root']
 def archived(item):return hashlib.sha256((frozen/item['path']).read_bytes()).hexdigest()==item['sha256']
 for row in h['files']:assert archived(row),row['path']
 for row in h['studies']:
  assert archived(row['receipt'])
  if row.get('comparison'):assert archived(row['comparison'])
 for row in h['latest_local_manifests']:assert archived(row['manifest'])
 for row in h['attempt_ledgers']:assert archived(row['source'])
 for name in ['catalog.json','research-history.json']:assert (DATA/name).read_bytes()==(OUT/name).read_bytes()
 with (OUT/'strategies.csv').open() as f:assert len(list(csv.DictReader(f)))==622
 manifest=read(OUT/'manifest.json');assert set(manifest)=={p.name for p in OUT.iterdir() if p.name!='manifest.json'}
 for name,digest in manifest.items():assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==digest,name
 return {'status':'passed-scoped-metadata-audit','community_ids':540,'tutorial_index_entries':82,'observed_tutorial_articles':81,'soft404':1,'community_observations':1620,'listing_pages_captured':324,'family_classified_records':622,'code_family_inspections':3,'study_groups':19,'selected_saved_case_rows':158,'preexisting_file_counts':h['file_counts'],'prior_source_refs_reconciled':16,'financial_attempts':0,'O03_remaining':'Detailed instrument/frequency/data contracts and source code equivalence unverified','artifact_count':len(manifest)}
if __name__=='__main__':print(json.dumps(audit(),indent=2))
