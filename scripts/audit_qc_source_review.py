#!/usr/bin/env python3
"""Read-only checks of the overlay, preserved inputs and conservative reuse gates."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research/catalogs/qc-detail-rights-v1'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    review = json.loads((OUT / 'review.json').read_text())
    original = json.loads((ROOT / 'research/catalogs/qc-inventory-v1/catalog.json').read_text())
    inputs = json.loads((OUT / 'inputs.json').read_text())
    manifest = json.loads((OUT / 'manifest.json').read_text())
    for item in inputs + manifest['artifacts'] + manifest['processing']:
        path = ROOT / item['path']
        assert digest(path) == item['sha256'], item['path']
        if 'git_blob_sha' in item:
            body = path.read_bytes()
            assert hashlib.sha1(b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest() == item['git_blob_sha']
    rows = review['records']
    ids = {r['id'] for r in rows}
    assert len(rows) == len(ids) == 622
    assert ids == {r['id'] for r in original['records']}
    assert sum(r['source_kind'] == 'tutorial' for r in rows) == 82
    assert sum(r['source_kind'] == 'community' for r in rows) == 540
    files = set()
    for r in rows:
        assert not r['package_complete'] and not r['runtime_or_performance_verified']
        assert r['rights']['source_package_export'].startswith('blocked')
        assert r['rights']['data_cloud_entitlement'].startswith('unverified')
        assert r['unresolved_contract_fields']
        allowed_paths = {s['path'] for s in r['source_files']}
        files.update(allowed_paths)
        assert all(o['path'] in allowed_paths for o in r['observations'])
        if r['source_kind'] == 'community':
            assert r['rights']['redistribution'] == 'unknown'
            assert not r['source_files']
        else:
            assert r['mapping_score'] >= .95 and r['source_files']
            assert 'Apache' in r['rights']['modification']
        if 'manual_detail_card' in r:
            assert r['manual_detail_card']['source_refs']
            assert r['manual_detail_card']['details']['data_needs']
    assert len(files) == review['stats']['in_scope_github_files'] == 337
    assert review['stats']['source_packages_exported'] == review['stats']['financial_attempts'] == 0
    for group in review['fragment_relationships'] + review['fragment_similarity_leads']:
        assert group['package_equivalence'] == 'unverified'
        assert all(m['id'] in ids for m in group['members'])
    assert review['objective_status']['O03'].startswith('partial')
    return {'id': review['id'], 'passed': True, 'records': len(rows), 'manifest_inputs_verified': len(inputs),
            'artifact_and_processing_hashes_verified': len(manifest['artifacts']) + len(manifest['processing']),
            'complete_packages_verified': 0, 'financial_attempts': 0}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
