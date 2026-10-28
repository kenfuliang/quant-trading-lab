"""Read-only, explicitly scoped evidence inventory; never executes submissions."""
import hashlib
import json
from pathlib import Path


def _read(root, name):
    if not isinstance(name, str) or not name:
        raise ValueError('artifact path must be nonempty relative text')
    path = Path(name)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('artifact must remain inside the evidence root')
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('symlink evidence is unsupported')
    if not current.is_file():
        raise FileNotFoundError(name)
    if current.stat().st_size > 10_000_000:
        raise ValueError('artifact exceeds 10MB inventory bound')
    return current.read_bytes()


def _integer(value):
    return type(value) is int and value >= 0


def reconcile(root, manifest):
    """Verify declared files and fixed-launcher check receipts, without writes.

    Manifest is an explicit projection, not auto-discovery or a complete trial
    ledger. Supports the wave1 JSONL reservation / JSON-result schema only.
    Caller owns semantic review, original budget authority and manifest trust.
    """
    root = Path(root).resolve(strict=True)
    if (not isinstance(manifest, dict) or type(manifest.get('schema_version')) is not int
            or manifest['schema_version'] != 1 or not isinstance(manifest.get('program'), str)
            or not manifest['program']):
        raise ValueError('schema_version1 and program identity required')
    items = manifest.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 16:
        raise ValueError('declare 1..16 work items')
    if any(not isinstance(item, dict) for item in items):
        raise ValueError('work items must be objects')
    ids = [item.get('id') for item in items]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('unique nonempty work IDs required')
    output = []
    for item in items:
        if not isinstance(item.get('owner'), str) or not item['owner']:
            raise ValueError('each work item requires an accountable owner')
        artifacts = item.get('artifacts')
        checks = item.get('checks')
        maximum = item.get('max_commands')
        if (not isinstance(artifacts, dict) or not 1 <= len(artifacts) <= 128
                or not isinstance(checks, list) or len(checks) > 32
                or len(set(checks)) != len(checks) or not _integer(maximum)):
            raise ValueError('bounded artifacts, distinct checks and command limit required')
        if item.get('reservations') not in artifacts or not set(checks) <= set(artifacts):
            raise ValueError('reservation and result paths must be hash-declared artifacts')
        verified, missing, failed = {}, [], []
        for name, expected in artifacts.items():
            if (not isinstance(expected, str) or len(expected) != 64
                    or any(c not in '0123456789abcdef' for c in expected)):
                raise ValueError('lowercase SHA256 identities required')
            try:
                content = _read(root, name)
                if hashlib.sha256(content).hexdigest() != expected:
                    failed.append(name + ': hash mismatch')
                else:
                    verified[name] = content if name in checks or name == item['reservations'] else b''
            except FileNotFoundError:
                missing.append(name)
        reservations, results = [], []
        try:
            if item['reservations'] in verified:
                reservations = [json.loads(line) for line in verified[item['reservations']].splitlines() if line.strip()]
            for name in checks:
                if name in verified:
                    result = json.loads(verified[name])
                    if type(result.get('number')) is not int or result['number'] <= 0:
                        failed.append(name + ': invalid result number')
                    results.append(result)
                    if result.get('status') != 'passed' or type(result.get('exit_code')) is not int or result['exit_code'] != 0:
                        failed.append(name + ': check did not pass')
            numbers = [row['number'] for row in reservations]
            if any(type(n) is not int or n <= 0 for n in numbers) or numbers != list(range(1, len(numbers) + 1)):
                failed.append('invalid reservation sequence')
            if len(reservations) > maximum:
                failed.append('command budget exceeded')
            if not missing and not failed:
                if not reservations or len(reservations) != len(results):
                    failed.append('unsealed or missing launch result')
                by_number = {row['number']: row for row in results}
                if len(by_number) != len(results) or set(by_number) != set(numbers):
                    failed.append('reservation/result identities differ')
                for reservation in reservations:
                    result = by_number.get(reservation['number'], {})
                    if any(result.get(k) != reservation.get(k) for k in ('actor', 'command', 'source_sha256', 'contract_sha256', 'reserved_utc')):
                        failed.append('reservation/result context differs')
            for row in reservations + results:
                if (not isinstance(row.get('actor'), str) or not row['actor']
                        or not isinstance(row.get('command'), list) or not row['command']
                        or not isinstance(row.get('source_sha256'), dict) or not row['source_sha256']
                        or not isinstance(row.get('contract_sha256'), str)
                        or not isinstance(row.get('reserved_utc'), str)):
                    failed.append('incomplete launch context')
                if type(row.get('financial_launches')) is not int or row['financial_launches'] != 0:
                    failed.append('zero-financial evidence not established')
        except (ValueError, KeyError, TypeError, AttributeError):
            failed.append('unsupported or malformed check evidence')
        output.append({'id': item['id'], 'owner': item['owner'],
                       'evidence_status': 'failed' if failed else ('unavailable' if missing else 'verified_declared_evidence'),
                       'commands_reserved': len(reservations), 'max_commands': maximum,
                       'results_present': len(results), 'artifacts_verified': len(verified),
                       'missing': missing, 'failures': failed,
                       'financial_performance': 'not assessed', 'promotion': 'not assessed'})
    return {'schema_version': 1, 'program': manifest['program'], 'items': output,
            'execution_performed': False, 'scope': 'declared byte/check identities only; completeness and scientific validity require review'}
