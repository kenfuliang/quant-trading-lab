#!/usr/bin/env python3
"""Build a read-only review overlay from frozen inputs; no network or strategy execution."""
import json
from collections import Counter
from pathlib import Path
import sys
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research.studies.checkpoint_20261031.qc_source_review import inspect_html, duplicate_groups, similarity_leads, rights, sha256

RAW = ROOT / '.local/qc-detail-rights-v1'
OUT = ROOT / 'research/catalogs/qc-detail-rights-v1'
WEB = ROOT / '.local/performance/qc-detail-rights-v1'


def build():
    original = ROOT / 'research/catalogs/qc-inventory-v1/catalog.json'
    catalog = json.loads(original.read_text())
    receipts = json.loads((RAW / 'licensed-file-receipts.json').read_text())
    mapping = {r['id']: r for r in json.loads((RAW / 'tutorial-folder-map.json').read_text())}
    grouped = {}
    fragments = []
    input_manifest = [{'path': str(original.relative_to(ROOT)), 'sha256': sha256(original.read_bytes())}]
    for name in ['scope.json', 'tutorial-folder-map.json', 'licensed-file-receipts.json', 'Tutorials-LICENSE', 'Tutorials-revision.txt']:
        p = RAW / name
        input_manifest.append({'path': str(p.relative_to(ROOT)), 'sha256': sha256(p.read_bytes())})
    for r in receipts:
        path = RAW / 'licensed-tutorial-evidence' / (r['git_blob_sha'] + '.html')
        assert sha256(path.read_bytes()) == r['sha256'], r['path']
        import hashlib
        assert hashlib.sha1(b'blob ' + str(path.stat().st_size).encode() + b'\0' + path.read_bytes()).hexdigest() == r['git_blob_sha']
        result = inspect_html(path.read_text())
        grouped.setdefault(r['path'].split('/')[1], []).append((r, result))
        input_manifest.append({'path': str(path.relative_to(ROOT)), 'sha256': r['sha256'], 'git_blob_sha': r['git_blob_sha']})
    manual_path = OUT / 'manual-detail-cards.json'
    manual = {r['id']: r for r in json.loads(manual_path.read_text())}
    input_manifest.append({'path': str(manual_path.relative_to(ROOT)), 'sha256': sha256(manual_path.read_bytes())})
    rows = []
    for old in catalog['records']:
        row = {k: old[k] for k in ('id', 'title', 'url', 'source_kind', 'families', 'classification_basis')}
        row.update({'rights': rights(old['source_kind']), 'holding_period': 'unverified_variable_or_not_declared',
                    'realized_leverage_and_shorting': 'unverified_requires_complete_execution_review',
                    'required_free_data_access': 'unverified_no_entitlement_probe',
                    'runtime_or_performance_verified': False, 'package_complete': False,
                    'observations': [], 'api_declarations': [], 'source_files': [],
                    'resolutions': [], 'algorithm_class_candidates': [],
                    'implementation_status': 'no_permitted_complete_source_package',
                    'duplicate_status': 'complete_source_unavailable_not_compared',
                    'mechanism_status': 'prior_metadata_only_not_verified_from_complete_code'})
        if row['id'] in mapping:
            row['folder'] = mapping[row['id']]['folder']
            row['mapping_basis'] = 'normalized_title_match_to_pinned_official_folder'
            row['mapping_score'] = mapping[row['id']]['score']
            row['mechanism_status'] = 'licensed_method_static_review_runtime_unverified'
            row['duplicate_status'] = 'observed_fragments_compared_package_equivalence_unverified'
            row['implementation_status'] = 'licensed_method_and_fragments_only'
            for receipt, result in grouped[row['folder']]:
                source = {'path': receipt['path'], 'sha256': receipt['sha256'], 'git_blob_sha': receipt['git_blob_sha'],
                          'url': receipt['url'].replace(' ', '%20'), 'blocks': len(result['blocks']), 'iframes': result['iframes']}
                row['source_files'].append(source)
                row['observations'] += [{**o, 'path': receipt['path'], 'url': source['url']} for o in result['observations']]
                row['api_declarations'] += [{'declaration': d, 'path': receipt['path']} for d in result['declarations']]
                row['resolutions'] += result['resolutions']
                for b in result['blocks']:
                    fragments.append({**b, 'id': row['id'], 'path': receipt['path']})
                    if b['algorithm_class_candidate']:
                        row['algorithm_class_candidates'].append({'path': receipt['path'], 'line': b['line']})
            row['resolutions'] = sorted(set(row['resolutions']))
            row['unresolved_contract_fields'] = ['exact_holding_period', 'complete_universe_and_history', 'runtime_leverage_shorting',
                'fills_and_financing', 'all_dependencies_and_inputs', 'current_engine_compatibility', 'data_entitlements']
        else:
            row['prior_instrument_hints'] = old.get('instrument_hints', [])
            row['unresolved_contract_fields'] = ['complete_permitted_source', 'instruments', 'frequency', 'holding_period',
                                               'leverage_and_shorting', 'data_requirements', 'source_specific_rights']
        if row['id'] in manual:
            row['manual_detail_card'] = manual[row['id']]
            row['manual_detail_card']['source_refs'] = [f for f in row['source_files'] if f['path'].endswith('/' + manual[row['id']]['source_filename'])]
            assert row['manual_detail_card']['source_refs'], row['id']
        rows.append(row)
    duplicate = duplicate_groups(fragments)
    similar = similarity_leads(fragments)
    # Name/family relations are leads; never inherit licensing or equality across them.
    relationships = catalog['relationships']
    stats = {'total_records': len(rows), 'licensed_tutorial_methods': len(mapping),
             'community_complete_source_pending': sum(r['source_kind'] == 'community' for r in rows),
             'github_files_inspected': len(receipts),
             'in_scope_github_files': sum(len(r['source_files']) for r in rows),
             'supplemental_folders_excluded_from_population': sorted(set(grouped) - {m['folder'] for m in mapping.values()}),
             'observed_code_blocks': len(fragments), 'meaningful_code_blocks': sum(b['meaningful'] for b in fragments),
             'algorithm_class_candidate_records': sum(bool(r['algorithm_class_candidates']) for r in rows),
             'iframe_file_count': sum(s['iframes'] > 0 for r in rows for s in r['source_files']),
             'fragment_identity_groups': len(duplicate), 'fragment_similarity_leads': len(similar), 'complete_packages_verified': 0,
             'package_duplicates_verified': 0, 'source_packages_exported': 0,
             'rights_dispositions': len(rows), 'manual_detail_cards': len(manual), 'financial_attempts': 0,
             'observed_requirements': dict(Counter(o['field'] for r in rows for o in {x['field']: x for x in r['observations']}.values()))}
    report = {'id': 'qc-detail-rights-v1', 'stats': stats, 'records': rows,
              'fragment_relationships': duplicate, 'fragment_similarity_leads': similar,
              'manual_relationship_review': [
                  {'ids': ['QC-T-15259', 'QC-T-15337'], 'finding': 'Shared balance-sheet accrual calculation with differing output attribute names (Accrual versus bs_acc); shared signal implementation, not proof of equal portfolio code.'},
                  {'ids': ['QC-T-9031', 'QC-T-15268'], 'finding': 'Shared monthly fundamental-universe scaffold; Energy versus Technology sector. This is infrastructure reuse, not the same alpha.'},
                  {'ids': ['QC-T-15356', 'QC-T-15256'], 'finding': 'Similar staggered long/short portfolio rebalancing; six cohorts with 1/6 sizing versus three cohorts with 1/3 sizing. Holding-period and sizing variants are material.'}], 'prior_name_and_family_leads': relationships,
              'source_revision': (RAW / 'Tutorials-revision.txt').read_text().strip(),
              'user_access_decision': 'No—use licensed sources first',
              'objective_status': {'O03': 'partial_blocked_complete_community_source_and_contracts',
                                   'O04': 'started_all_records_triaged_not_all_rights_cleared', 'O05': 'no_new_source_package_export'},
              'policies': [
                  {'id': 'APACHE-TUTORIALS', 'url': 'https://github.com/QuantConnect/Tutorials/blob/' + (RAW / 'Tutorials-revision.txt').read_text().strip() + '/LICENSE',
                   'scope': 'Pinned repository artifacts only; preserve license, applicable notices and attribution; mark changes. Inspect third-party exclusions/dependencies before packaging.'},
                  {'id': 'QC-ACCESS', 'url': 'https://www.quantconnect.com/terms/', 'version': '1.5 / October 8, 2026',
                   'scope': 'Section 3.3 restricts website extraction. Use licensed repositories or verified supported official interfaces within permitted scope. No new bulk website collection in this review.'},
                  {'id': 'QC-DATA', 'url': 'https://www.quantconnect.com/docs/v2/cloud-platform/datasets/licensing',
                   'scope': 'Cloud access, downloads and redistribution require separate dataset-specific checks; code licensing conveys no market-data entitlement.'},
                  {'id': 'RESULTS-SEPARATE', 'url': 'https://www.quantconnect.com/docs/v2/cloud-platform/security-and-ip',
                   'scope': 'Own results and other authors result artifacts are separate rights questions; no blanket republication clearance established.'}],
              'limitations': ['Static declarations are not runtime or financial validation.',
                             'No complete-package manifest exists; matching fragments do not prove algorithm equivalence.',
                             '82 folder-title matches do not prove equality to website revisions or similarly named community algorithms.',
                             'Missing full source blocks completion of O03 across all 622 records.',
                             'No free historical data access was tested; data needs remain a candidate-specific O07 gate.']}
    OUT.mkdir(parents=True, exist_ok=True)
    WEB.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    (OUT / 'review.json').write_text(encoded)
    (OUT / 'inputs.json').write_text(json.dumps(input_manifest, indent=2) + '\n')
    (WEB / 'review.json').write_text(encoded)
    html = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Source details & reuse review</title>
<style>body{font:16px system-ui;margin:0;background:#f6f5f0;color:#182a35}main{max-width:1450px;margin:auto;padding:30px}h1{font-size:30px;margin:10px 0}p{line-height:1.5}.notice{padding:18px;background:#fff0cf;border-left:5px solid #bc7e15;border-radius:8px}.stats{display:flex;flex-wrap:wrap;gap:12px;margin:24px 0}.stat{background:white;padding:15px 22px;border:1px solid #ddd;border-radius:10px}.stat strong{display:block;font-size:28px}input,select{padding:12px;border:1px solid #aab6bc;border-radius:7px;font:inherit;margin-right:10px}input{width:42%}table{width:100%;border-collapse:collapse;background:white;margin-top:20px}th,td{text-align:left;padding:12px;border-bottom:1px solid #ddd;vertical-align:top}th{background:#e9eeef;position:sticky;top:0}a{color:#126476}small{color:#536874}summary{cursor:pointer}pre{white-space:pre-wrap;font:13px system-ui}.badge{color:#915200}footer{padding:25px 0}</style><main>
<small>QUANT TRADING LAB · O03 / O04 · STATIC SOURCE REVIEW</small><h1>Strategy details, code relationships & reuse rights</h1>
<div class="notice"><b>O03 remains partial. O04 started; no source packages cleared or exported.</b><br>Licensed GitHub methods are available for 82 tutorials. Complete community source, full dependency manifests and data entitlements remain unresolved. Shared fragments are not duplicate strategies.</div>
<div class="stats" id="stats"></div><p><b>Review flow:</b> frozen inventory → licensed method inspection → fragment comparison → separate rights gates → permitted package export later.</p>
<input id="query" aria-label="Search strategies" placeholder="Search ID, title, family or observed requirement"><select id="kind" aria-label="Source type"><option value="">All source types</option><option value="tutorial">Licensed tutorials</option><option value="community">Community / source pending</option></select><select id="detail" aria-label="Review depth"><option value="">All review depths</option><option value="manual">Manual detail cards</option></select><span id="count"></span>
<table><thead><tr><th>Strategy</th><th>Observed method / data declarations</th><th>Reuse gates & evidence</th></tr></thead><tbody id="rows"></tbody></table>
<h2>Code relationship limits</h2><p id="duplicates"></p><details><summary>Observed fragment identity groups</summary><pre id="groups"></pre></details><h2>Rights sources</h2><ul id="policies"></ul><footer><a href="/qc-inventory-v1/index.html">Prior frozen inventory</a> · <a href="review.json">Download review metadata</a><p>No strategy execution, financial attempts, broker actions or source-package exports.</p></footer></main>
<script>const data=DATA;const $=x=>document.getElementById(x);const esc=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const tiles=[['Records triaged',data.stats.total_records],['Licensed tutorial methods',data.stats.licensed_tutorial_methods],['Community source pending',data.stats.community_complete_source_pending],['Verified complete packages',0],['Financial attempts',0]];$('stats').innerHTML=tiles.map(([a,b])=>`<div class="stat"><strong>${b}</strong>${a}</div>`).join('');
function render(){const q=$('query').value.toLowerCase(),k=$('kind').value;const rows=data.records.filter(r=>(!k||r.source_kind===k)&&(!$('detail').value||r.manual_detail_card)&&JSON.stringify(r).toLowerCase().includes(q));$('count').textContent=rows.length+' / '+data.records.length+' records';$('rows').innerHTML=rows.map(r=>`<tr><td><b>${esc(r.title)}</b><br><small>${esc(r.id)} · ${esc(r.source_kind)}<br>${esc(r.families.join(', '))}</small></td><td>${r.manual_detail_card?'<b>'+esc(r.manual_detail_card.details.instruments)+'</b><br>'+esc(r.manual_detail_card.details.frequency)+'<br><small>Needs: '+esc(r.manual_detail_card.details.data_needs.join('; '))+'</small><br>':''}${r.observations.length?[...new Set(r.observations.map(o=>o.field))].map(x=>esc(x.replaceAll('_',' '))).join('<br>'):(r.manual_detail_card?'No API declarations in inspected fragments':'Detailed source contract unverified')}<br><small>Resolution declarations: ${esc(r.resolutions.join(', ')||'unknown')}<br>Holding period / realized leverage: unverified</small></td><td><span class="badge">${r.source_kind==='tutorial'?'Apache-2.0: repository artifacts only':'Source-specific code rights unknown'}</span><br>Data rights: separate / unverified<br>Complete-package export: blocked<details><summary>Evidence & unresolved fields (${r.source_files.length} files)</summary><ul>${r.source_files.map(s=>`<li><a href="${esc(s.url)}">${esc(s.path)}</a> · ${s.blocks} blocks / ${s.iframes} iframes</li>`).join('')}</ul><pre>${esc(JSON.stringify({status:r.implementation_status,unresolved:r.unresolved_contract_fields,rights:r.rights,manual_detail_card:r.manual_detail_card,observations:r.observations,api_declarations:r.api_declarations},null,2))}</pre></details></td></tr>`).join('')};$('query').addEventListener('input',render);$('kind').addEventListener('change',render);$('detail').addEventListener('change',render);render();
$('duplicates').textContent=data.stats.fragment_identity_groups+' raw/AST fragment groups; '+data.stats.fragment_similarity_leads+' lexical similarity leads, manually reviewed; '+data.stats.algorithm_class_candidate_records+' records contain candidate algorithm-class snippets. Neither count establishes complete packages or independent returns.';$('groups').textContent=JSON.stringify({exact_fragments:data.fragment_relationships,similarity_leads:data.fragment_similarity_leads,manual_review:data.manual_relationship_review},null,2);$('policies').innerHTML=data.policies.map(p=>`<li><a href="${esc(p.url)}">${esc(p.id)}</a>: ${esc(p.scope)}</li>`).join('');</script></html>'''
    # Prevent source titles/metadata from terminating the inline script.
    html = html.replace('DATA', json.dumps(report, ensure_ascii=False).replace('<', '\\u003c'))
    (WEB / 'index.html').write_text(html)
    manifest = {'id': report['id'], 'stats': stats, 'artifacts': [
        {'path': str(p.relative_to(ROOT)), 'sha256': sha256(p.read_bytes())}
        for p in [OUT / 'review.json', OUT / 'inputs.json', WEB / 'review.json', WEB / 'index.html'] +
        [p for p in [WEB / 'browser-audit.json', WEB / 'review-preview.png'] if p.exists()]],
        'processing': [{'path': name, 'sha256': sha256((ROOT / name).read_bytes())} for name in
                       ['research/qc_source_review.py', 'scripts/build_qc_source_review.py', 'tests/test_qc_source_review.py', 'scripts/audit_qc_source_review.py']]}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(stats, indent=2))


if __name__ == '__main__':
    build()
