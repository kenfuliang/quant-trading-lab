#!/usr/bin/env python3
"""Offline inventory and permitted source export; never executes foreign code."""
import ast
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research.studies.checkpoint_20261031.qc_source_review import inspect_html
from research.studies.checkpoint_20261031.qc_tutorial_packages import digest, inspect_python, license_gate, make_archive, archive_inventory

RAW = ROOT / '.local/qc-tutorial-packages-v1'
OLD = ROOT / '.local/qc-detail-rights-v1'
OUT = ROOT / 'research/catalogs/qc-tutorial-packages-v1'
WEB = ROOT / '.local/performance/qc-tutorial-packages-v1'


def normalized(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def check_blob(body, sha):
    assert hashlib.sha1(b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest() == sha


def main():
    OUT.mkdir(exist_ok=True, parents=True)
    WEB.mkdir(exist_ok=True, parents=True)
    (WEB / 'packages').mkdir(exist_ok=True)
    population = json.loads((OLD / 'tutorial-folder-map.json').read_text())
    receipts = json.loads((OLD / 'licensed-file-receipts.json').read_text())
    private = json.loads((RAW / 'unlicensed-file-receipts.json').read_text())
    prior = json.loads((ROOT / 'research/catalogs/qc-detail-rights-v1/review.json').read_text())
    prior_rows = {r['id']: r for r in prior['records']}
    providers = json.loads((OUT / 'data-provider-review.json').read_text())
    plan = json.loads((OUT / 'package-plan.json').read_text())
    inputs = []
    data_rules = {
        'equity_price_and_action_inputs': r'AddEquity|add_equity|SecurityType\.(?:Equity|EQUITY)',
        'point_in_time_fundamentals_and_historical_universe': r'HasFundamentalData|has_fundamental_data|FineFundamental|FineSelection|FineFilter|MarketCap|FinancialStatements|ValuationRatios|Morningstar',
        'forex_prices_fx_conventions_and_funding': r'AddForex|add_forex|SecurityType\.(?:Forex|FOREX)',
        'futures_contracts_or_continuous_series_roll_and_margin': r'AddFuture|add_future|CHRIS/|QuandlFutures',
        'option_chains_quotes_expiration_and_assignment': r'AddOption|add_option|OptionChain|option_chain',
        'external_or_custom_data': r'AddData|add_data|Download\(|download\(|read_csv|Quandl|Dropbox|dropbox|Tiingo',
        'historical_lookback_or_warmup': r'History\(|history\(|SetWarmUp|set_warm_up',
        'object_store_or_serialized_state': r'ObjectStore|object_store|pickle.loads',
    }
    for p in [OLD / 'tutorial-folder-map.json', OLD / 'licensed-file-receipts.json',
              ROOT / 'research/catalogs/qc-detail-rights-v1/review.json',
              OUT / 'package-plan.json', OUT / 'data-provider-review.json', RAW / 'scope.json']:
        inputs.append({'path': str(p.relative_to(ROOT)), 'sha256': digest(p.read_bytes())})
    for p in sorted({p for pattern in ['*-metadata.json', '*-tree.json', '*-receipts.json', '*-revision.txt', 'linked-source-leads.json'] for p in RAW.glob(pattern)}) + [RAW / 'licensed-candidates/Common/AlgorithmImports.py']:
        inputs.append({'path': str(p.relative_to(ROOT)), 'sha256': digest(p.read_bytes())})
    inspected = []
    for r in private:
        p = ROOT / r['local']
        body = p.read_bytes()
        assert digest(body) == r['sha256']
        check_blob(body, r['git_blob_sha'])
        # Only one file-level license was established; no root grant inherited.
        grant = license_gate(body, (RAW / 'licensed-candidates/LICENSE').read_bytes())
        analysis = inspect_python(body)
        text = body.decode('utf-8-sig')
        data_observations = [{'requirement': label, 'lines': [i for i, line in enumerate(text.splitlines(), 1) if re.search(pattern, line)][:12]} for label, pattern in data_rules.items() if re.search(pattern, text)]
        resolutions = sorted(set(re.findall(r'Resolution\.([A-Za-z_]+)', text)))
        inspected.append({k: r[k] for k in ('repo', 'revision', 'path', 'git_blob_sha', 'sha256')} |
                         {'license': grant, 'static_analysis': analysis, 'data_observations': data_observations, 'resolutions': resolutions,
                          'url': f"https://github.com/{r['repo']}/blob/{r['revision']}/{quote(r['path'])}"})
        inputs.append({'path': str(p.relative_to(ROOT)), 'sha256': digest(body), 'git_blob_sha': r['git_blob_sha']})
    exported = []
    aggregate = {}
    all_receipts = json.loads((RAW / 'licensed-candidate-receipts.json').read_text()) + json.loads((RAW / 'JSTM-receipts.json').read_text()) + private
    for item in plan:
        source = ROOT / item['source_local']
        body = source.read_bytes()
        license_body = (ROOT / item['license_local']).read_bytes()
        matching = next(r for r in all_receipts if r['repo'] == item['repo'] and r['path'] == item['source_path'])
        check_blob(body, matching['git_blob_sha'])
        revision = (ROOT / item['revision_dir'] / item['revision_file']).read_text().strip()
        grant = license_gate(body, license_body, item['repo_apache_verified'])
        analysis = inspect_python(body)
        assert grant['permitted'] and analysis['syntax'] == 'valid' and not analysis['ellipsis_lines'], item['package_id']
        manifest = {'package_id': item['package_id'], 'tutorial_id': item['tutorial_id'],
                    'source': {'repository': item['repo'], 'revision': revision, 'path': item['source_path'],
                               'url': f"https://github.com/{item['repo']}/blob/{revision}/{quote(item['source_path'])}",
                               'git_blob_sha': matching['git_blob_sha'], 'sha256': digest(body)},
                    'license': grant, 'relationship': item['relation'], 'material_differences': item['material_differences'],
                    'source_preservation': 'Original strategy file bytes unchanged; added metadata clearly separate.',
                    'completeness': 'whole observed strategy/example file and declared external dependencies; not a runtime distribution',
                    'original_tutorial_identity_verified': False, 'dependency_versions_fully_locked': False,
                    'runtime_verified': False, 'data_qualified': False,
                    'financial_attempts': 0, 'dependencies': item['external_runtime'], 'static_analysis': analysis,
                    'data': item['data'], 'review_findings': item['review_findings']}
        # All non-standard source imports must be disclosed; no invented pip lock.
        packages = set(item['external_runtime']['required_python_packages'])
        for name in analysis['external_imports']:
            assert name == 'AlgorithmImports' or name.split('.')[0] in packages, (item['package_id'], name)
        readme = '# ' + item['package_id'] + '\n\nLicensed source-preservation bundle. Not installed, run, ported or investment-validated.\n\n'
        readme += item['relation'] + '\n\nSource: ' + manifest['source']['url'] + '\n\n'
        readme += 'The source file is unchanged. License and attribution are retained. No data, credentials, broker connection or published result artifacts are bundled.\n\n'
        readme += '## Dependencies\n\n' + json.dumps(item['external_runtime'], indent=2) + '\n\n'
        readme += '## Data and blockers\n\n' + json.dumps(item['data'], indent=2) + '\n\n'
        readme += '## Review findings\n\n' + '\n'.join('- ' + f for f in item['review_findings']) + '\n'
        files = {'source/' + Path(item['source_path']).name: body, 'LICENSE': license_body,
                 'README.md': readme.encode(), 'source-manifest.json': (json.dumps(manifest, indent=2) + '\n').encode()}
        bundle = make_archive(files, grant)
        destination = WEB / 'packages' / (item['package_id'] + '.zip')
        if destination.exists():
            assert destination.read_bytes() == bundle, 'Refuse mutation of frozen source export: ' + str(destination)
        else:
            destination.write_bytes(bundle)
        exported.append({**manifest, 'zip_path': str(destination.relative_to(ROOT)), 'zip_sha256': digest(bundle),
                         'members': archive_inventory(bundle)})
        aggregate.update({item['package_id'] + '/' + name: content for name, content in files.items()})
        for p in (source, ROOT / item['license_local']):
            inputs.append({'path': str(p.relative_to(ROOT)), 'sha256': digest(p.read_bytes())})
    aggregate['README.md'] = b'# Permitted source bundles\n\nFour pinned licensed source/example bundles. No data or credentials. No package is runtime, financial or original-tutorial-identity validated. See each source-manifest.json and README for differences and blockers.\n'
    full_zip = make_archive(aggregate, {'permitted': True})
    dest = WEB / 'permitted-sources.zip'
    if dest.exists():
        assert dest.read_bytes() == full_zip, 'Refuse mutation of frozen combined export'
    else:
        dest.write_bytes(full_zip)
    by_tutorial = {r['tutorial_id']: r for r in exported}
    cards = []
    for row in population:
        source_files = [r for r in receipts if r['path'].split('/')[1] == row['folder']]
        module_hints = set()
        endpoints = set()
        for r in source_files:
            p = OLD / 'licensed-tutorial-evidence' / (r['git_blob_sha'] + '.html')
            body = p.read_bytes()
            assert digest(body) == r['sha256']
            inputs.append({'path': str(p.relative_to(ROOT)), 'sha256': digest(body)})
            parsed = inspect_html(body.decode())
            for b in parsed['blocks']:
                for m in re.findall(r'^\s*(?:from|import)\s+([\w.]+)', b['text'], re.M):
                    module_hints.add(m)
            for url in re.findall(r'https?://[^\s\"\'<>]+', body.decode()):
                u = urlsplit(url.replace('&amp;', '&'))
                if any(x in u.netloc.lower() for x in ('quandl', 'dropbox', 'tiingo', 'french', 'cboe')):
                    endpoints.add(u.scheme + '://' + (u.hostname or '') + u.path)
        title = normalized(row['title'])
        matches = []
        for candidate in inspected:
            stem = normalized(Path(candidate['path']).stem)
            score = difflib.SequenceMatcher(None, title, stem).ratio()
            aliases = {
                'QC-T-15298': {'Pairs Trading Copula Method.py', 'Pairs Trading Cointegration Method.py'},
                'QC-T-15373': {'Dynamic Breakout II.py'},
                'QC-T-15258': {'Dual Thrust.py'},
                'QC-T-15344': {'Use Crude Oil to Predict Equity Returns.py', 'crude-oil-predicts-equity-returns.py'},
            }
            alias = Path(candidate['path']).name in aliases.get(row['id'], set())
            if score >= .85 or alias:
                matches.append({'path': candidate['path'], 'repo': candidate['repo'], 'revision': candidate['revision'],
                                'url': candidate['url'], 'name_similarity': round(score, 4),
                                'identity': 'curated_alias_lead_not_proven_equivalent' if alias else 'name-based_candidate_not_proven_equivalent', 'license': candidate['license'],
                                'syntax': candidate['static_analysis']['syntax'],
                                'observed_imports': candidate['static_analysis']['external_imports'], 'data_requirements': candidate['data_observations'], 'resolutions': candidate['resolutions']})
        matches.sort(key=lambda x: -x['name_similarity'])
        search_file = RAW / 'github-search' / (row['id'] + '.json')
        search = json.loads(search_file.read_text()) if search_file.exists() else None
        if search:
            inputs.append({'path': str(search_file.relative_to(ROOT)), 'sha256': digest(search_file.read_bytes())})
        prior_row = prior_rows[row['id']]
        cards.append({'id': row['id'], 'title': row['title'], 'folder': row['folder'],
                      'source_search': {'method': search['method'], 'query': search['query'],
                                        'hits': search['result'].get('total_count'), 'error': search['result'].get('error'),
                                        'observed_results': [{'repo': x['repository']['full_name'], 'path': x['path'], 'url': x['html_url']} for x in search['result'].get('items', [])]} if search else {'status': 'pending'},
                      'candidate_matches': matches, 'whole_source_package': by_tutorial.get(row['id']),
                      'original_source_identity': 'not_verified',
                      'export_status': 'licensed_source_or_mechanism_alternative_exported' if row['id'] in by_tutorial else 'blocked_no_qualified_complete_licensed_package_found_in_review',
                      'method_dependency_hints': sorted(module_hints),
                      'dependency_status': 'static_imports_only_runtime_versions_unverified',
                      'legacy_endpoint_leads': sorted(endpoints),
                      'method_observations': prior_row['observations'],
                      'manual_detail_card': prior_row.get('manual_detail_card'),
                      'free_data_status': 'not_qualified_for_exact_tutorial_reproduction',
                      'candidate_data_requirement_leads': sorted({o['requirement'] for m in matches for o in m['data_requirements']}),
                      'candidate_requirement_caveat': 'Observed in named candidate code, not a verified exact tutorial implementation; follow source paths and lines.',
                      'data_requirements_basis': 'pinned method declarations; full candidate contracts still require identity and execution review',
                      'source_refs': prior_row['source_files']})
    stats = {'tutorial_records': len(cards), 'github_title_search_receipts': sum('query' in c['source_search'] for c in cards),
             'github_title_search_errors': sum(bool(c['source_search'].get('error')) for c in cards),
             'private_candidate_files_inspected': len(inspected),
             'explicit_file_grants_in_otherwise_unlicensed_repos': sum(c['license']['permitted'] for c in inspected),
             'tutorials_with_name_matched_candidate_leads': sum(bool(c['candidate_matches']) for c in cards),
             'permitted_source_bundles_exported': len(exported),
             'remaining_without_qualified_licensed_source_bundle': len(cards) - len(exported),
             'exact_current_tutorial_source_identities_verified': 0, 'runtime_qualified_packages': 0,
             'exact_free_local_data_qualified_tutorials': 0, 'financial_attempts': 0}
    review = {'id': 'qc-tutorial-packages-v1', 'stats': stats, 'records': cards, 'packages': exported,
              'candidate_file_inspections': inspected, 'data_provider_review': providers,
              'combined_zip': {'path': str(dest.relative_to(ROOT)), 'sha256': digest(full_zip), 'members': archive_inventory(full_zip)},
              'scope': '82 frozen tutorial IDs; licensed-source discovery and static export only',
              'limits': ['Not an exhaustive search of every GitHub commit, file or repository.',
                         'Exact-title queries return only first30results and may miss differently named code.',
                         'Filename matching identifies leads, not identity or license inheritance.',
                         'Four complete observed source/example files are not82 reproduced or runtime-ready strategies.',
                         'No code or data use grant is inherited from an MIT collector or similarly named copy.']}
    encoded = json.dumps(review, indent=2, ensure_ascii=False) + '\n'
    (OUT / 'review.json').write_text(encoded)
    (WEB / 'review.json').write_text(encoded)
    (OUT / 'input-manifest.json').write_text(json.dumps(inputs, indent=2) + '\n')
    html = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Tutorial source packages</title><style>body{font:16px system-ui;background:#f7f5ef;color:#20323b;margin:0}main{max-width:1440px;padding:32px;margin:auto}h1{font-size:32px}.notice{padding:18px;background:#fff0cb;border-left:5px solid #bb8a29;border-radius:8px}.stats{display:flex;gap:14px;flex-wrap:wrap;margin:24px 0}.stat{padding:16px 23px;border:1px solid #ddd;background:white;border-radius:9px}.stat b{display:block;font-size:28px}table{width:100%;border-collapse:collapse;background:white}td,th{text-align:left;padding:14px;border-bottom:1px solid #ddd;vertical-align:top}th{background:#e6edef}small{color:#526b74}a{color:#126778}input,select{font:inherit;padding:11px;border-radius:7px;border:1px solid #b1bdc3;margin:10px 10px 20px 0}input{width:45%}summary{cursor:pointer}pre{white-space:pre-wrap;font:13px system-ui}p{line-height:1.5}</style><main><small>QUANT TRADING LAB · O03–O05 · LICENSED SOURCE DISCOVERY</small><h1>Tutorial implementations, dependencies & data gates</h1><div class="notice"><b>82 tutorials reviewed; four licensed source/example bundles exported.</b><br>These are source-preservation bundles, including alternatives. Exact hosted identity, runtime compatibility and exact free/local data remain unverified. No backtests or orders were run.</div><div class="stats" id="stats"></div><p><b>Flow:</b> source search → file-level rights → unchanged source export → dependency and data blockers → isolated reproduction later.</p><p><a href="permitted-sources.zip">Download all four permitted source bundles</a> · <a href="review.json">Review metadata</a> · <a href="/qc-detail-rights-v1/index.html">Earlier method/rights review</a></p><h2>Exported packages</h2><table><thead><tr><th>Package / relationship</th><th>Dependencies & data</th><th>Concrete blockers</th></tr></thead><tbody id="packages"></tbody></table><h2>All 82 tutorial records</h2><input id="query" aria-label="Search tutorial records" placeholder="Search ID, title, candidate or dependency"><select id="disposition" aria-label="Export disposition"><option value="">All records</option><option value="exported">Licensed bundle exported</option><option value="blocked">No qualified bundle</option></select><span id="count"></span><table><thead><tr><th>Tutorial</th><th>Discovery / rights</th><th>Dependencies / next gate</th></tr></thead><tbody id="rows"></tbody></table><h2>Verified provider documentation</h2><ul id="providers"></ul><p>Advertised free access is not a tested input contract. No market data, account information, credentials or third-party result artifacts are included in the exports.</p></main><script>const data=DATA;const $=x=>document.getElementById(x);const e=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));$('stats').innerHTML=[['Tutorials',82],['Source bundles',data.stats.permitted_source_bundles_exported],['No qualified bundle',data.stats.remaining_without_qualified_licensed_source_bundle],['Runtime / data qualified',0],['Financial attempts',0]].map(([a,b])=>`<div class="stat"><b>${b}</b>${a}</div>`).join('');$('packages').innerHTML=data.packages.map(p=>`<tr><td><b>${e(p.package_id)}</b><br><small>${e(p.tutorial_id)}</small><p>${e(p.relationship)}</p><a href="packages/${e(p.package_id)}.zip">Download ZIP</a> · <a href="${e(p.source.url)}">Pinned source</a><p><small>${e(p.license.license)} · ${e(p.license.basis)}</small></p></td><td>${e(p.dependencies.name)}<br><small>${e(p.dependencies.versions)}</small><p>${e(p.data.free_local)}</p></td><td>${p.review_findings.map(e).join('<br><br>')}<details><summary>Manifest and data requirements</summary><pre>${e(JSON.stringify(p,null,2))}</pre></details></td></tr>`).join('');function render(){const q=$('query').value.toLowerCase(),d=$('disposition').value;const rows=data.records.filter(r=>JSON.stringify(r).toLowerCase().includes(q)&&(!d||(d==='exported'?!!r.whole_source_package:!r.whole_source_package)));$('count').textContent=rows.length+' / 82 records';$('rows').innerHTML=rows.map(r=>`<tr><td><b>${e(r.title)}</b><br><small>${e(r.id)}</small></td><td>${r.whole_source_package?'Licensed source bundle exported':'No qualified licensed bundle'}<br><small>${r.candidate_matches.length} filename-based candidate leads; identity unverified<br>Exact-title GitHub search: ${e(r.source_search.hits??'unknown')} hits</small></td><td>${r.whole_source_package?'Exported source inputs: '+e(r.whole_source_package.data.inputs.join('; ')):'Candidate input leads: '+e(r.candidate_data_requirement_leads.join('; ').replaceAll('_',' ')||'no verified complete source')}<br><small>Observed method imports: ${e(r.method_dependency_hints.join(', ')||'not specified')}</small><br><small>Exact free/local input contract not qualified</small><details><summary>Source, candidates and unresolved requirements</summary><pre>${e(JSON.stringify(r,null,2))}</pre></details></td></tr>`).join('')};$('query').addEventListener('input',render);$('disposition').addEventListener('change',render);render();$('providers').innerHTML=data.data_provider_review.providers.map(p=>`<li><a href="${e(p.url)}">${e(p.id)}</a>: ${e(p.finding)}</li>`).join('');</script></html>'''
    (WEB / 'index.html').write_text(html.replace('DATA', json.dumps(review, ensure_ascii=False).replace('<', '\\u003c')))
    artifact_paths = [OUT / 'review.json', OUT / 'input-manifest.json', WEB / 'review.json', WEB / 'index.html', dest] + sorted((WEB / 'packages').glob('*.zip'))
    artifact_paths += [p for p in [WEB / 'browser-audit.json', WEB / 'review-preview.png'] if p.exists()]
    manifest = {'id': review['id'], 'stats': stats, 'artifacts': [{'path': str(p.relative_to(ROOT)), 'sha256': digest(p.read_bytes())} for p in artifact_paths],
                'processing': [{'path': n, 'sha256': digest((ROOT / n).read_bytes())} for n in ['research/qc_tutorial_packages.py', 'scripts/build_qc_tutorial_packages.py', 'scripts/audit_qc_tutorial_packages.py', 'tests/test_qc_tutorial_packages.py']]}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(stats, indent=2))


if __name__ == '__main__':
    main()
