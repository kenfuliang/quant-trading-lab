"""Read-only final bounded-study audit; writes one aggregate acceptance receipt."""
import hashlib,json,re,csv
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/'.local/selection-completion-v1';OUT=ROOT/'.local/performance/selection-completion-v1'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def audit():
 ledger=json.loads((RAW/'attempts.json').read_text());plan=json.loads((ROOT/'research/plans/selection-completion-v1.json').read_text());d=json.loads((OUT/'comparison.json').read_text());validation=json.loads((RAW/'final-validation.json').read_text())
 assert ledger['status']=='closed' and len(ledger['attempts'])<=14
 assert sum(a['kind']=='financial' for a in ledger['attempts'])==9
 assert sum(a['kind']=='diagnostic' for a in ledger['attempts'])==2
 assert sum(a['kind']=='technical-retry' for a in ledger['attempts'])<=3
 assert all(a['status']=='completed-verified' or a['status'].startswith('failed-') for a in ledger['attempts'])
 assert datetime.fromisoformat(ledger['closed_utc'])<=datetime.fromisoformat(ledger['deadline_utc'])
 assert all(datetime.fromisoformat(ledger['created_utc'])<=datetime.fromisoformat(a['reserved_utc'])<=datetime.fromisoformat(ledger['deadline_utc']) for a in ledger['attempts'])
 cases=set(plan['case_mapping']);assert cases=={a['case'] for a in ledger['attempts'] if a['status']=='completed-verified' and not a['case'].endswith('_probe')}
 for c,h in plan['source_hashes'].items():assert digest(RAW/f'{c}-source.py')==h
 for a in ledger['attempts']:
  if a['case']=='asset_probe' and a['status'].startswith('failed-'):source=RAW/'asset_probe-truncated-source.py'
  elif a['case']=='stock_probe' and a['kind']=='diagnostic':source=RAW/'stock_probe-lowvol-source.py'
  elif a['case']=='ew_stock' and a['status'].startswith('failed-'):source=RAW/'ew_stock-pre-repair-source.py'
  else:source=RAW/(a['case']+'-source.py')
  assert digest(source)==a['source_sha256']
  if a['status'].startswith('failed-'):
   source=RAW/('asset_probe-truncated-source.py' if a['case']=='asset_probe' else a['case']+'-pre-repair-source.py')
   assert digest(source)==a['source_sha256']
   fail=RAW/('asset_probe-truncated-terminal-fragments.json' if a['case']=='asset_probe' else a['case']+'-failed-terminal.json');assert fail.exists()
 diagnosis=json.loads((RAW/'diagnosis.json').read_text())
 for key in ['asset','stock','momentum']:
  r=diagnosis[key];assert r['windows']==72 and all(r[k]==0 for k in ['future','invalid','unordered','orders'])
 assert diagnosis['momentum']['remaining_ineligible'][0][:3]==['2021-09-01','SNOW',243]
 for key,h in diagnosis['summary_sha256'].items():
  file='stock_probe-summary-cells.json' if key=='stock_probe-momentum' else key+'-summary-cells.json'
  assert digest(RAW/file)==h
 assert len(d['runs'])==10 and len(d['annual'])==60 and len(d['decisions'])==3
 assert d['evidence']['calendar_check']['sessions']==1508
 assert len({r['calendar_hash'] for r in d['runs']})==1
 assert all(r['rejects']==r['other_fills']==r['pending_orders']==0 for r in d['runs'])
 assert all(not r[k] for r in d['runs'] if not r['cached'] for k in ['feature_future','feature_invalid','feature_unordered'])
 assert validation['make_check_exit']==0 and validation['tests_passed']>=314
 assert validation['make_check_log_sha256']==digest(RAW/'final-check.log')
 assert validation['browser']['years']==['2020','2021','2022','2023','2024','2025'] and validation['browser']['rows_per_year']==10
 assert validation['browser']['rank_metrics']==['calmar','sharpe','cagr']
 snapshot=RAW/'browser-verified-comparison.json';assert digest(snapshot)==validation['browser']['verified_snapshot_sha256']
 viewed=json.loads(snapshot.read_text())
 for key in ['names','runs','annual','decisions']:assert viewed[key]==d[key]
 with (OUT/'annual.csv').open() as fp:csv_rows=list(csv.DictReader(fp))
 assert len(csv_rows)==60
 source={(r['case'],r['year']):r for r in d['annual']}
 for r in csv_rows:
  original=source[(r['case'],r['year'])]
  for key in ['ret','dd','sharpe','annual_calmar','global_uw','n','longest_uw','financing_usd','end']:assert float(r[key])==original[key]
 restore=validation['source_restoration'];assert restore['clipboard_matches'] and restore['sha256']==digest(ROOT/'.local/qc504-funded-v1/ensemble-source.py')
 for p,h in json.loads((OUT/'manifest.json').read_text()).items():assert digest(OUT/p)==h
 for name,expected in plan['baseline'].items():
  folder=ROOT/'.local/performance'/name;assert digest(folder/'manifest.json')==expected['manifest_sha256']
  for p,h in json.loads((folder/'manifest.json').read_text()).items():assert digest(folder/p)==h
 goal=(ROOT/'docs/tasks/2026-10-26-selection-research-goal.md').read_text();assert '- [ ]' not in goal
 review=ROOT/'docs/tasks/2026-10-26-selection-completion.md';text=review.read_text()
 for term in ['ETF momentum','Stock momentum','Low-volatility stocks','Lessons','not independent'] :assert term in text
 paths=['README.md','docs/research-development.md','docs/operations/performance.md','research/plans/selection-completion-v1.json','research/plans/selection-completion-v1.design.json','research/quantconnect/selection_completion_policy.py','research/quantconnect/selection_subscription_retention.py','research/quantconnect/selection_readiness_probe.py','research/quantconnect/selection_stock_probe.py','research/quantconnect/qc504_funded_policy.py','research/quantconnect/sector_metrics.py','research/us_etf_calendar.py','scripts/prepare_selection_completion.py','scripts/prepare_selection_completion_probe.py','scripts/selection_completion_budget.py','scripts/parse_selection_completion_fragments.py','scripts/record_selection_completion.py','scripts/build_selection_completion.py','scripts/audit_selection_completion.py','tests/test_selection_completion.py','tests/test_selection_readiness_probe.py','docs/tasks/2026-10-26-selection-research-goal.md','docs/tasks/2026-10-26-selection-completion.md','docs/tasks/2026-10-26-research-lessons.md']
 receipt=dict(status='complete-with-declared-research-limitations',checked_utc=datetime.now(timezone.utc).isoformat(),requirements=dict(readiness_diagnosis='verified metadata-only probes; early-close repair and legitimate IPO exclusions',frozen_sources='all9sources hashed;2technical repairs preserved, no optimization',matched_comparison='9freshcases plus cachedT11; matched feature/membership hashes and exactSPY parity',metrics='6annual periods; CAGR/Sharpe/Calmar/NAV arithmetic; calendar and temporal consistency checks',interpretation='3decision cards, annual/control and concentration analysis, limitations and consolidated lessons',scope='free hosted/local only;14maximum counted attempts; no broker/deployment/publication',validation='makecheck,browserselectors,source restoration and manifest checks'),attempts=len(ledger['attempts']),deadline_utc=ledger['deadline_utc'],code_and_doc_sha256={p:digest(ROOT/p) for p in paths},raw_evidence_sha256={p.name:digest(p) for p in RAW.iterdir() if p.is_file() and p.suffix=='.json' and p.name not in ['acceptance.json','continuation.json']},output_manifest_sha256=digest(OUT/'manifest.json'),validation=validation,limits=d['evidence']['limits'])
 (RAW/'acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n');(ROOT/'docs/tasks/evidence/2026-10-26-selection-completion-acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt['status'],receipt['attempts'])
if __name__=='__main__':audit()
