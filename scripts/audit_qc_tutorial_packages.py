#!/usr/bin/env python3
"""Read-only hashes, source fidelity and rights gate audit; never executes strategies."""
import io
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research.qc_tutorial_packages import digest, inspect_python, license_gate, archive_inventory


def audit():
    out = ROOT / 'research/catalogs/qc-tutorial-packages-v1'
    review = json.loads((out / 'review.json').read_text())
    manifest = json.loads((out / 'manifest.json').read_text())
    inputs = json.loads((out / 'input-manifest.json').read_text())
    plan = {x['package_id']: x for x in json.loads((out / 'package-plan.json').read_text())}
    for item in inputs + manifest['artifacts'] + manifest['processing']:
        assert digest((ROOT / item['path']).read_bytes()) == item['sha256'], item['path']
    rows = review['records']
    assert len(rows) == len({r['id'] for r in rows}) == 82
    assert all('query' in r['source_search'] and not r['source_search'].get('error') for r in rows)
    assert all(r['free_data_status'] == 'not_qualified_for_exact_tutorial_reproduction' for r in rows)
    expected = {r['id'] for r in json.loads((ROOT / '.local/qc-detail-rights-v1/tutorial-folder-map.json').read_text())}
    assert {r['id'] for r in rows} == expected
    for package in review['packages']:
        p = plan[package['package_id']]
        body = (ROOT / p['source_local']).read_bytes()
        permission = license_gate(body, (ROOT / p['license_local']).read_bytes(), p['repo_apache_verified'])
        assert permission['permitted'] and permission == package['license']
        assert not package['runtime_verified'] and not package['data_qualified']
        assert not package['original_tutorial_identity_verified']
        assert inspect_python(body)['syntax'] == 'valid'
        bundle = (ROOT / package['zip_path']).read_bytes()
        assert digest(bundle) == package['zip_sha256']
        assert archive_inventory(bundle) == package['members']
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            source_name = 'source/' + Path(p['source_path']).name
            assert set(archive.namelist()) == {source_name, 'LICENSE', 'README.md', 'source-manifest.json'}
            assert archive.read(source_name) == body
            assert archive.read('LICENSE') == (ROOT / p['license_local']).read_bytes()
            assert 'No data' in archive.read('README.md').decode()
            for name in archive.namelist():
                assert not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts
    combined = (ROOT / review['combined_zip']['path']).read_bytes()
    assert digest(combined) == review['combined_zip']['sha256']
    assert archive_inventory(combined) == review['combined_zip']['members']
    stats = review['stats']
    assert stats['permitted_source_bundles_exported'] == len(review['packages']) == 4
    assert stats['remaining_without_qualified_licensed_source_bundle'] == 78
    assert stats['exact_current_tutorial_source_identities_verified'] == stats['runtime_qualified_packages'] == stats['financial_attempts'] == 0
    return {'id': review['id'], 'passed': True, 'records_verified': len(rows), 'source_bundles_verified': len(review['packages']),
            'input_hashes_verified': len(inputs), 'artifact_processing_hashes_verified': len(manifest['artifacts']) + len(manifest['processing']),
            'unchanged_strategy_source_bytes': True, 'no_market_data_in_archives': True, 'financial_attempts': 0}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
