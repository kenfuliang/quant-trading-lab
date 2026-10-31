"""Build a metadata-only, source-separated strategy inventory. No network or simulation."""
import csv,hashlib,json,re,sys
from pathlib import Path
from collections import Counter,defaultdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from research.qc_inventory import classify,normalize_community,tutorial_index,tutorial_article_observed
RAW=ROOT/'.local/qc-inventory-v1';DATA=ROOT/'research/catalogs/qc-inventory-v1';OUT=ROOT/'.local/performance/qc-inventory-v1'

def read(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def relative(p):return str(p.relative_to(ROOT))
def source(p):return {'path':relative(p),'sha256':digest(p)}

def catalog():
 passes={n:read(RAW/f'{f}.json') for n,f in [('sharpe_desc','community-pages'),('sharpe_asc','community-pages-ascending'),('author_order','community-pages-author')]}
 rows,total=normalize_community(passes);desc={r['id']:r for r in read(RAW/'community-descriptions.json')};code={r['id']:r for r in read(RAW/'code-family-reviews.json')}
 for r in rows:
  d=desc.get(r['id']);r.update(classify(r['title'],d['description'] if d else '',basis='public_description' if d else 'title'))
  if r['id'] in code:
   review=code[r['id']];r.update(families=review['families'],classification_basis='displayed_code_inspection',classification_confidence='family only; behavior unaudited',matched_terms={},family_review=review)
  r.update(code_package_status='not exported in this inventory',rights_status='unreviewed',data_readiness='unverified',next_action='O04 access/rights and O05 source-package qualification',decision_layers=layers(r['title']+' '+(d['description'] if d else '')))
  r['claim_status']='Upstream displayed claim; not our reproduced performance'
  r['claim_context']={'source_labels':['OOS 3M Return','OOS 3M Sharpe','OOS 1Y Sharpe'],'exact_sample_dates':None,'publication_date':None,'capital_costs_financing':None,'missing_reason':'Not displayed in the captured listing; detail-page qualification pending'}
  if d:r['description_evidence']={'captured_utc':d['captured_utc'],'raw_file':relative(RAW/'community-descriptions.json'),'sha256':digest(RAW/'community-descriptions.json')}
 receipts={r['url']:r for r in read(RAW/'tutorial-page-receipts.json')}
 for entry in tutorial_index((RAW/'tutorial-index.html').read_text()):
  capture=receipts[entry['url']];assert capture['status']==200
  rid=re.search(r'/research/(\d+)/',capture['final_url']);accessible=tutorial_article_observed(capture)
  r={'id':'QC-T-'+(rid[1] if rid else 'index-'+entry['url'].rsplit('/',1)[-1]),'upstream_id':rid[1] if rid else None,'source_kind':'tutorial','title':entry['title'],'url':capture['final_url'] if accessible else entry['url'],'resolved_url':capture['final_url'],'article_access':'observed' if accessible else 'soft404; index entry only','index_url':entry['url'],'author':None,'organization':None,'observed_claims':[],'appearances':[{'index':'official Strategy Library','captured_utc':capture['captured_utc']}], 'claim_status':'Tutorial method; publication metrics not collected by this inventory'}
  r.update(classify(entry['title'],entry['description'],basis='official_index_description'),decision_layers=layers(entry['description']),code_package_status='not exported in this inventory',rights_status='unreviewed',data_readiness='unverified',next_action='O04 access/rights and O05 source-package qualification',page_receipt={k:capture[k] for k in ('status','sha256','bytes','captured_utc')})
  
  if not accessible:r['next_action']='Blocked article access: indexed link resolves to soft404; seek a permitted primary replacement before O04–O07'
  rows.append(r)
 for r in rows:
  evidence_text=r['title']+' '+desc.get(r['id'],{}).get('description','')
  r['instrument_hints']=[label for label,pat in [('equity',r'stock|equity|equities|large.cap'),('ETF',r'\betf\b|\bspy\b|\bqqq\b|\btqqq\b'),('futures',r'future|commodity|commodities'),('forex',r'forex|currency|currencies|eurusd'),('crypto',r'crypto|bitcoin|\bbtc\b'),('options',r'option|straddle|\bputs\b|\bcalls\b|\bleaps\b')] if re.search(pat,evidence_text,re.I)]
  r['frequency_hint']='intraday mentioned' if re.search('intraday',evidence_text,re.I) else 'unverified'
  r['holding_period']='unverified';r['leverage_hint']='mentioned' if re.search(r'leverag|margin|[2-9]x',evidence_text,re.I) else 'unverified'
  r['shorting_hint']='mentioned' if re.search(r'short|inverse',evidence_text,re.I) else 'unverified'
  r['data_requirements']='unverified; needs candidate-specific O07 receipt'
 assert len(rows)==622 and len({r['id'] for r in rows})==622
 assert all(r['families']!=['unresolved'] for r in rows),[(r['id'],r['title']) for r in rows if r['families']==['unresolved']]
 counts={k:dict(Counter(f for r in rows if r['source_kind']==k for f in r['families']).most_common()) for k in ('community','tutorial')}
 # Similar titles establish review leads only; do not collapse strategies into one code identity.
 groups=defaultdict(list)
 for r in rows:groups[re.sub(r'[^a-z0-9]','',r['title'].lower())].append(r['id'])
 exact_title=[{'kind':'same normalized title; code equivalence unknown','ids':ids} for ids in groups.values() if len(ids)>1]
 hints=[]
 for parent in ('504','687'):
  base=next(r for r in rows if r['id']=='QC-C-'+parent)
  variants=[r['id'] for r in rows if r['source_kind']=='community' and r['id']!=base['id'] and base['title'].casefold() in r['title'].casefold()]
  hints.extend({'kind':'title-based variant hint; code equivalence unknown','parent':base['id'],'child':v} for v in variants)
 stats={'community':540,'tutorial':82,'tutorial_articles_observed':81,'tutorial_soft404':1,'total_source_records':622,'raw_community_rows':total,'listing_pages_per_pass':108,'listing_slots_per_pass':540,'distinct_ids_per_pass':{n:len({r['links'][0]['href'] for p in ps for r in p['rows']}) for n,ps in passes.items()},'classification_basis':dict(Counter(r['classification_basis'] for r in rows)),'unresolved_family_records':0,'family_memberships':counts,'family_counts_overlap':True,'catalog_coverage':'540 IDs reconcile to108pages×5slots across3orders; observed authenticated listing only','source_item_access':'Community listings observed; 67 detail descriptions read and three displayed-code family inspections; full detail access not checked for every listing','code_equivalence':'Not established across catalog','financial_attempts':0}
 return {'snapshot_id':'qc-inventory-v1','scope':read(RAW/'scope.json'),'stats':stats,'records':rows,'relationships':exact_title+hints,'processing_sources':[source(ROOT/p) for p in ['research/qc_inventory.py','scripts/build_qc_inventory.py','scripts/audit_qc_inventory.py','tests/test_qc_inventory.py']], 'input_sources':[source(RAW/f) for f in ['scope.json','community-pages.json','community-pages-ascending.json','community-pages-author.json','tutorial-index.html','tutorial-page-receipts.json','community-descriptions.json','code-family-reviews.json']],'limits':['Snapshot coverage does not include private, deleted or future strategies','Title/description labels are provisional; three displayed-code family inspections are not behavioral validation','Shared names and families are not proof of shared code or independent alpha','Upstream OOS labels are preserved as claimed, not independently validated; unreported trials and author data exposure remain unknown','No access/rights/free-data readiness inference from a listing Clone label','Raw article HTML evidence is not a complete pinned strategy-source package','No new simulations, project clones, subscriptions or broker operations']}

def layers(text):
 rules={'industry_or_sector_selection':r'sector|industr(?:y|ies)','execution_rule_hint':r'market.on.open|market.on.close|limit.order|stop.order|vwap|twap','asset_or_universe_selection':r'select|rank|screen|rotat|universe|large.cap','aggressiveness_or_sizing':r'leverag|position.siz|allocat|volatility.target|risk.budget','go_no_go_or_risk_overlay':r'gate|stop|risk.off|cash|crash.guard','strategy_selection':r'ensemble|multi.model|multi.strategy|multi.engine','risk_measurement':r'drawdown|volatil|risk.score|expected.shortfall','profit_signal':r'momentum|return|earnings|value'}
 return [k for k,v in rules.items() if re.search(v,text,re.I)] or ['unverified']

STUDIES=[
 ('spy','Initial SPY fixture','2026-10-25-local-performance-browser.md','Local SPY EMA and holding references; not a published-source reproduction.'),
 ('leverage','Leverage and financing','2026-10-25-leverage-comparison.md','Shared SPY signals at four exposures plus financing/margin stresses; correlated trials.'),
 ('strategy-suite','100 ideas and SPY adaptation suite','2026-10-25-strategy-catalogue-suite.md','100 catalog ideas; 22 daily SPY adaptations at four exposures, not 100 implemented strategies or 88 independent discoveries.'),
 ('recursive-research','Recursive research pilot','2026-10-25-recursive-research-review.md','Eight new audited financial cases and cost-sensitive rankings; no trained RL advantage.'),
 ('risk-gate','SPY risk-gate epoch','2026-10-25-rsi-risk-gate-epoch.md','Combined gate failed joint criteria; EMA/volatility-only ablation retained on viewed history; failures preserved.'),
 ('gate-robustness','Gate execution robustness','2026-10-25-rsi-gate-robustness-review.md','Cost/delay challenge retained a fixed development candidate; no independent alpha.'),
 ('gate-decisions','Decision/outcome labels','2026-10-25-gate-decision-labels.md','Protection, missed rebound and already-cash diagnostics; retrospective reconstruction.'),
 ('features','Feature engineering','2026-10-25-feature-engineering-skill.md','Three-feature causal diagnostics; descriptive associations, not a trained predictor.'),
 ('multi-asset','Independent multi-asset qualification','2026-10-25-multi-asset-qualification-v2-checkpoint.md','Synthetic/accounting and source proofs coexist with historical qualification blockers; no invented historical return.'),
 ('quantconnect-spy-v1','Hosted SPY comparison','2026-10-25-quantconnect-spy-comparison.md','Fresh hosted holding/EMA/gate references under their own longer sample and cost policy.'),
 ('sector-momentum-v1','Sector momentum','2026-10-25-sector-momentum-comparison.md','Sector rotation, sector equal weight and SPY/gate controls; matching context owned by receipt.'),
 ('qc504-v1','QC504 evaluation','2026-10-26-qc504-evaluation.md','Inspected adaptation/evaluation of community 504; extreme headline is not accepted investment evidence.'),
 ('qc504-ablation-v1','Four-sleeve ablation','2026-10-26-qc504-sleeve-ablation.md','Original ablation retains order/financing defects; funded follow-up has separate identity.'),
 ('qc504-funded-v1','Funded sleeve execution','2026-10-26-qc504-funded-execution.md','Consistent financed execution across ensemble and sleeves; not a guarantee of annual doubling.'),
 ('qc504-t11-gate-v1','T11 risk gate','2026-10-26-qc504-t11-gate.md','Gate/control tradeoffs on already-viewed history; retain distinct from source.'),
 ('qc-breadth-v1','First three selection ideas','2026-10-26-qc-selection-comparison.md','Tutorial-informed adaptations, readiness gaps and technical failures; not exact source reproduction.'),
 ('selection-completion-v1','Selection completion and controls','2026-10-26-selection-completion.md','Nine fresh cases plus cached T11; low-volatility fixed implementation rejected; exposure/capital confounds remain.'),
 ('stock-risk-v1','Stock gate/sector ablation','2026-10-26-stock-risk-ablation.md','Gate transfer reduced growth; unknown-sector cash exclusion confounded earlier sector treatment.'),
 ('sector-matched-v1','Historical sector and matched exposure','2026-10-26-sector-matched.md','27 dated inferred labels; sector offers modest advantage over target-matched control and little recovery improvement.')]

def history(c=None):
 frozen=RAW/'research-history-frozen.json'
 if frozen.exists():return read(frozen)
 files=[];errors=[]
 paths=set(ROOT.glob('docs/tasks/*.md'))|set(ROOT.glob('docs/tasks/evidence/*.json'))|set(ROOT.glob('research/plans/*.json'))|set(ROOT.glob('reports/**/*.json'))
 # Exclude this initiative's changing task/checklist and self-generated evidence.
 paths={p for p in paths if p.name not in ('2026-10-26-quantconnect-research-master-plan.md','2026-10-26-quantconnect-inventory.md','2026-10-26-quantconnect-inventory.json')}
 for p in sorted(paths):
  row=source(p);row['kind']='task' if p.suffix=='.md' else 'evidence' if '/evidence/' in str(p) else 'plan_or_input' if '/plans/' in str(p) else 'saved_research_artifact'
  row['bytes']=p.stat().st_size
  if p.suffix=='.json':
   try:
    d=read(p);row['declared_status']=d.get('status') if isinstance(d,dict) else None
   except Exception as e:errors.append({'path':relative(p),'reason':str(e)[:150]})
  files.append(row)
 studies=[];case_records=[]
 for sid,name,task,note in STUDIES:
  receipt=ROOT/'docs/tasks'/task
  if not receipt.exists():
   # Explicit absence stays visible; do not invent completion evidence.
   fallback=None
  else:fallback=source(receipt)
  folder=ROOT/'.local/performance'/sid;comparison=folder/'comparison.json'
  row={'id':sid,'name':name,'receipt':fallback,'expected_receipt':relative(receipt),'note':note,'source_relation':'local reference or declared adaptation; exact source reproduction not established by this index','new_simulation':False}
  if comparison.exists():
   d=read(comparison);row['comparison']=source(comparison);runs=d.get('runs',d.get('overall',[]));assert isinstance(runs,list)
   row['recorded_case_rows']=len(runs)
   for i,r in enumerate(runs):
    case_records.append({'study':sid,'case':str(r.get('case',r.get('mode',i))),'name':r.get('name') or d.get('names',{}).get(r.get('case',r.get('mode'))),'source':relative(comparison),'cached':r.get('cached',False),'context':{'source_context':r.get('context'),'first':r.get('first'),'last':r.get('last'),'sessions':r.get('n',r.get('sessions')),'policy':r.get('policy'),'capital_and_costs':'See frozen source receipt; missing flattened fields remain unknown'},'evidence_status':'indexed saved summary; not financially re-audited in this task'})
  else:
   row['recorded_case_rows']=None
  if folder.exists():row['review_folders']=[relative(p) for p in folder.glob('*/manifest.json')]
  studies.append(row)
 local=read(ROOT/'research/strategy_catalogue.json');ideas=[{k:r[k] for k in ('id','name','family','status','implementable_with_saved_spy','blockers') if k in r} for r in local['strategies']]
 active=[]
 for label,path in [('strategy-suite',ROOT/'reports/strategy-suite/97fc0717512bee9e/manifest.json'),('leverage',ROOT/'reports/leverage/3aba31cfafe4da76/manifest.json')]:
  d=read(path)
  for case in d['cases']:
   case_records.append({'study':label,'case':case['key'],'name':case.get('name'),'source':relative(path),'cached':False,'context':{'model':d.get('model'),'evaluation':d.get('evaluation'),'scope':'Latest selected local manifest; older versions indexed separately'},'evidence_status':'indexed saved manifest case; not financially re-audited in this task'})
  active.append({'study':label,'manifest':source(path),'case_count':len(d['cases']),'case_keys':[r['key'] for r in d['cases']],'status_in_receipt':d['status']})
 # Index exact saved attempt states without treating absent ledgers as zero attempts.
 ledgers=[]
 for p in sorted((ROOT/'.local').glob('*/attempts.json')):
  if p.parent.name not in ('sector-matched-v1','stock-risk-v1','selection-completion-v1') and not p.parent.name.startswith('qc'):continue
  d=read(p);attempts=d.get('attempts',[]);ledgers.append({'source':source(p),'status':d.get('status'),'attempt_count':len(attempts),'attempt_states':dict(Counter(str(a.get('status','unknown')) for a in attempts))})
 c=c or catalog();known={r['id']:r for r in c['records']};refs=defaultdict(set)
 for p in sorted(ROOT.glob('docs/tasks/*.md')):
  if p.name in ('2026-10-26-quantconnect-research-master-plan.md','2026-10-26-quantconnect-inventory.md'):continue
  for kind,num in re.findall(r'quantconnect\.com/(strategies|research)/(\d+)',p.read_text()):refs['QC-'+('C-' if kind=='strategies' else 'T-')+num].add(relative(p))
 crosswalk=[{'source_id':sid,'title':known[sid]['title'] if sid in known else None,'current_catalog_match':sid in known,'prior_receipts':sorted(paths),'interpretation':'Prior mention/inspection is not exact reproduction; consult receipt for tested adaptation and evidence state'} for sid,paths in sorted(refs.items())]
 for record in case_records:
  sid=record['study'];record['receipt']=next((x['receipt']['path'] for x in studies if x['id']==sid and x['receipt']),None)
  record['upstream_source_refs']=['QC-C-504'] if sid.startswith('qc504') else ['QC-T-15338','QC-T-15364','QC-T-15381'] if sid in ('qc-breadth-v1','selection-completion-v1') else ['QC-T-15364'] if sid in ('stock-risk-v1','sector-matched-v1') else []
 return {'snapshot_id':'research-history-index-v1','scope':'pre-existing project task receipts, compact evidence, research plan/input JSON and all saved reports JSON; saved hosted comparisons plus selected latest local manifests; no claim of complete lifetime trials','files':files,'file_counts':dict(Counter(r['kind'] for r in files)),'parse_errors':errors,'studies':studies,'case_records':case_records,'latest_local_manifests':active,'attempt_ledgers':ledgers,'local_ideas':ideas,'prior_source_crosswalk':crosswalk,'limits':['File presence/hash and JSON parsing do not repeat financial audits','Older report versions and failed evidence remain indexed; counts are artifact counts, not independent experiments','Missing lifetime trial/search history remains unknown','Document status active is maintenance metadata, not a passing investment result','USD10000hosted fixtures and USD300000local scenarios remain separate','Existing viewed samples are not fresh independent validation']}

def build():
 DATA.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
 c=catalog();h=history(c);assert not h['parse_errors']
 (DATA/'catalog.json').write_text(json.dumps(c,indent=2)+'\n');(DATA/'research-history.json').write_text(json.dumps(h,indent=2)+'\n')
 (OUT/'catalog.json').write_text(json.dumps(c,indent=2)+'\n');(OUT/'research-history.json').write_text(json.dumps(h,indent=2)+'\n')
 with (OUT/'strategies.csv').open('w') as f:
  keys=['id','source_kind','title','url','author','families','classification_basis','classification_confidence','decision_layers','rights_status','data_readiness','next_action'];w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
  for r in c['records']:w.writerow({k:'; '.join(r[k]) if isinstance(r[k],list) else r[k] for k in keys})
 render(c,h)
 manifest={p.name:digest(p) for p in OUT.iterdir() if p.name!='manifest.json'};(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print(json.dumps({'catalog':c['stats'],'history_file_counts':h['file_counts'],'study_groups':len(h['studies']),'saved_case_rows':len(h['case_records']),'missing_study_receipts':[r['expected_receipt'] for r in h['studies'] if not r['receipt']]},indent=2))

def render(c,h):
 payload=json.dumps({'catalog':c,'history':h},separators=(',',':')).replace('</','<\\/')
 html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Quant research · catalog and evidence</title><style>body{font:15px system-ui;background:#f6f4ed;color:#25383d;margin:30px;max-width:1650px}h1{font-size:30px}h2{margin-top:28px}p{max-width:1200px;line-height:1.55}.note{background:#fff0c9;padding:16px;border-radius:8px}.cards{display:flex;gap:15px;flex-wrap:wrap}.card{background:#e1ebe4;border:1px solid #b5c9ba;border-radius:8px;padding:15px;min-width:160px}.card b{font-size:26px;display:block}table{border-collapse:collapse;background:white;width:100%;font-size:13px}th,td{padding:9px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}th{background:#dfE8e3}select,input,button{padding:8px;margin:5px}a{color:#246c78}.scroll{overflow:auto}small{color:#56666c}td:nth-child(2){min-width:200px}.chip{background:#eef2f0;padding:3px;border-radius:3px}</style>
<h1>Quant research: what we have, and the accessible strategy catalog</h1><p>O00–O03 · snapshot qc-inventory-v1 · review date October 26, 2026, America/Los_Angeles · metadata research only</p>
<div class="cards"><div class="card"><b>540</b>Community listings</div><div class="card"><b>82</b>Tutorial index entries</div><div class="card"><b>81 + 1</b>Reachable articles + soft 404</div><div class="card"><b>19</b>Existing study groups</div><div class="card"><b>0</b>New backtests</div></div>
<p class="note"><b>Coverage checked across three listing orders.</b> Each traversal had 108 pages and 540 row slots, but only 532, 502 and 487 distinct IDs individually. Their union contains 540 IDs. Family labels are preliminary, multi-label metadata interpretations, with three displayed-code family inspections. They do not establish economic independence, free data access, reuse rights or reproduced returns.</p>
<h2>Objective status</h2><p>O00: existing evidence indexed. O01: inventory scope frozen; future experiment budgets unallocated. O02: listing/index coverage reconciled; one tutorial article unavailable. O03 partial: initial family tags complete; detailed strategy contracts and code equivalence remain open.</p>
<h2>Family coverage</h2><p>Counts overlap: one strategy can combine momentum, rotation and a risk overlay. They cannot be added to obtain a strategy total.</p><div class="scroll"><table id="families"></table></div>
<h2>Browse every strategy</h2><label>Source <select id="source"><option value="">All sources</option><option value="community">Community</option><option value="tutorial">Tutorial</option></select></label><label>Family <select id="family"><option value="">All families</option></select></label><label>Evidence <select id="basis"><option value="">All evidence</option><option value="title">Title only</option><option value="public_description">Public description</option><option value="official_index_description">Official index description</option><option value="displayed_code_inspection">Displayed code inspected</option></select></label><input id="search" placeholder="Name, ID, author, family"><label><input id="blocked" type="checkbox">Blocked article only</label><p id="count"></p><button id="prev">Previous</button><button id="next">Next</button><div class="scroll"><table id="strategies"></table></div>
<p><a href="strategies.csv">All 622 catalog records · CSV</a> · <a href="catalog.json">Catalog, source claims and provenance · JSON</a></p>
<h2>Existing research and lessons</h2><p id="historySummary"></p><p>Source receipts own actual results. This inventory checks file identity and saved record structure; it does not repeat financial audits or combine different samples, costs and capital into one performance league table. Failed and superseded evidence remains indexed.</p><div class="scroll"><table id="studies"></table></div>
<h2>Source-to-adaptation and idea boundaries</h2><p>The local 100-idea catalog is a separate population. Its latest saved suite has 22 SPY adaptations at four exposures (88 case rows), while 78 ideas need additional inputs. Those are not 100 reproduced QuantConnect strategies. Cached controls and source adaptations remain distinct in the saved-case index.</p>
<p><a href="research-history.json">Research receipts, cases, ledgers and local ideas · JSON</a> · <a href="manifest.json">Artifact integrity manifest</a></p>
<h2>Next work</h2><p>O04 access/rights and O05 complete permitted source preservation, then O06 code/mechanism inspection and O07 data qualification. The broken mutual-fund tutorial needs a permitted primary replacement. No bulk project clone, code execution or financial experiment follows automatically.</p>
<script>const D=PAYLOAD,C=D.catalog,H=D.history;const $=id=>document.getElementById(id);const label=s=>s==='machine_learning'?'Statistical / ML methods':s.replaceAll('_',' ');function table(id,heads,rows){$(id).replaceChildren();for(const [i,row] of [heads,...rows].entries()){let tr=document.createElement('tr');for(const v of row){let cell=document.createElement(i?'td':'th');if(v instanceof Node)cell.append(v);else cell.textContent=v??'Unknown';tr.append(cell)}$(id).append(tr)}}function link(text,url){let a=document.createElement('a');a.textContent=text;a.href=url;return a}const families=[...new Set(C.records.flatMap(r=>r.families))].sort();for(const f of families)$('family').add(new Option(label(f),f));table('families',['Family','Community memberships','Tutorial memberships'],families.map(f=>[label(f),C.stats.family_memberships.community[f]||0,C.stats.family_memberships.tutorial[f]||0]));
let page=0,size=25;function records(){let q=$('search').value.toLowerCase();return C.records.filter(r=>(!$('source').value||r.source_kind===$('source').value)&&(!$('family').value||r.families.includes($('family').value))&&(!$('basis').value||r.classification_basis===$('basis').value)&&(!$('blocked').checked||r.article_access?.startsWith('soft404'))&&JSON.stringify([r.id,r.title,r.author,r.families]).toLowerCase().includes(q))}function show(){let rs=records();page=Math.min(page,Math.max(0,Math.ceil(rs.length/size)-1));let visible=rs.slice(page*size,(page+1)*size);$('count').textContent=rs.length+' matching records · page '+(page+1)+' of '+Math.max(1,Math.ceil(rs.length/size));$('prev').disabled=page===0;$('next').disabled=(page+1)*size>=rs.length;table('strategies',['ID / source','Strategy','Families','Basis / confidence','Access and next action'],visible.map(r=>[r.id+' · '+r.source_kind,link(r.title,r.url),r.families.map(label).join(', '),label(r.classification_basis)+' · '+r.classification_confidence,(r.article_access||'Listing observed; full detail access not comprehensively checked')+'; '+r.next_action]))}
for(const id of ['source','family','basis','blocked'])$(id).onchange=()=>{page=0;show()};$('search').oninput=()=>{page=0;show()};$('prev').onclick=()=>{page--;show()};$('next').onclick=()=>{page++;show()};show();$('historySummary').textContent=H.studies.length+' study groups · '+H.file_counts.task+' prior task receipts · '+H.file_counts.evidence+' compact evidence receipts · '+H.file_counts.plan_or_input+' plan/input files · '+H.file_counts.saved_research_artifact+' saved research JSON artifacts. '+H.case_records.length+' selected saved case rows indexed (hosted summaries and latest local manifests, including cached references); their financial audits were not repeated.';table('studies',['Study','Evidence','What we learned / remaining limit'],H.studies.map(r=>[r.name,r.comparison?link('Saved review','/'+r.id+'/index.html'):r.receipt?'Receipt indexed: '+r.receipt.path:'Missing receipt',r.note]));</script></html>'''.replace('PAYLOAD',payload)
 a=html.index('<h2>Family coverage</h2>');b=html.index('<h2>Browse every strategy</h2>');family_section=html[a:b];html=html[:a]+html[b:];html=html.replace('<h2>Existing research and lessons</h2>',family_section+'<h2>Existing research and lessons</h2>')
 (OUT/'index.html').write_text(html)

if __name__=='__main__':build()
