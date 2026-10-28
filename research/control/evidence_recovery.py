"""Offline, copy-only recovery of closed research file bundles with saved hashes.

No financial execution, source repair, deletion, database copying or service work.
A failed study remains failed. Receipts authenticate bytes only against caller-held
hashes, not the truth of the original research claims.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil

CLOSED_STATUSES = {'completed', 'failed', 'STOPPED_INCOMPLETE', 'recovery_failed_no_further_launch'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def file_hashes(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Bundle must be a regular directory, not a symlink')
    hashes = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise ValueError('Bundle contains a symlink or special file')
        if path.is_file():
            hashes[path.relative_to(root).as_posix()] = digest(path)
    return hashes


def validate_hash_map(hashes):
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError('Nonempty file hash map required')
    for name, sha in hashes.items():
        if not isinstance(name, str) or not name or '\\' in name or ':' in name:
            raise ValueError('Unsafe inventory path')
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or str(path) != name or name == '.':
            raise ValueError('Unsafe inventory path')
        if not isinstance(sha, str) or len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
            raise ValueError('Invalid SHA-256 digest')


def verify_bundle(root):
    root = Path(root)
    hashes = file_hashes(root)
    if 'manifest.json' not in hashes:
        raise ValueError('Saved manifest.json required')
    manifest = json.loads((root / 'manifest.json').read_text())
    expected = manifest.get('artifact_hashes')
    validate_hash_map(expected)
    if manifest.get('status') not in CLOSED_STATUSES:
        raise ValueError('Only recognized closed bundle statuses can be copied or restored')
    actual = {name: sha for name, sha in hashes.items() if name != 'manifest.json'}
    if expected != actual:
        raise ValueError('Saved artifact hash/coverage mismatch; preserve original without repair')
    return {'schema_version': 1, 'original_status': manifest['status'],
            'source_manifest_sha256': hashes['manifest.json'], 'file_hashes': hashes,
            'file_count': len(hashes), 'artifact_count': len(expected)}


def disjoint(left, right):
    left, right = Path(left).resolve(), Path(right).resolve()
    if left == right or left.is_relative_to(right) or right.is_relative_to(left):
        raise ValueError('Source and destination must be disjoint')


def copy_files(source, destination, hashes):
    # Caller reserves destination first. Never merge, overwrite or clean up failures.
    for name in sorted(hashes):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with (source / name).open('rb') as incoming, target.open('xb') as outgoing:
            shutil.copyfileobj(incoming, outgoing)


def create_recovery_copy(source, backup):
    source, backup = Path(source), Path(backup)
    disjoint(source, backup)
    before = verify_bundle(source)
    # Existing backups, even incomplete ones, require a new explicitly chosen path.
    backup.mkdir()
    payload = backup / 'files'
    payload.mkdir()
    copy_files(source, payload, before['file_hashes'])
    if verify_bundle(source) != before or verify_bundle(payload) != before:
        raise ValueError('Source changed or recovery copy differs; preserve partial copy')
    inventory = backup / 'inventory.json'
    with inventory.open('x') as stream:
        stream.write(json.dumps(before, indent=2) + '\n')
    return {'inventory_sha256': digest(inventory), **before}


def restore_recovery_copy(backup, destination, expected_inventory_sha256):
    backup, destination = Path(backup), Path(destination)
    disjoint(backup, destination)
    if backup.is_symlink() or not backup.is_dir():
        raise ValueError('Recovery copy must be a regular directory')
    if set(p.name for p in backup.iterdir()) != {'inventory.json', 'files'}:
        raise ValueError('Recovery copy layout changed')
    inventory = backup / 'inventory.json'
    if inventory.is_symlink() or not inventory.is_file() or digest(inventory) != expected_inventory_sha256:
        raise ValueError('Recovery inventory identity mismatch')
    saved = json.loads(inventory.read_text())
    before = file_hashes(backup)
    if verify_bundle(backup / 'files') != saved:
        raise ValueError('Recovery copy does not match its pinned inventory')
    destination.mkdir()
    copy_files(backup / 'files', destination, saved['file_hashes'])
    if verify_bundle(destination) != saved:
        raise ValueError('Restored bundle mismatch; preserve partial restore')
    if file_hashes(backup) != before or digest(inventory) != expected_inventory_sha256:
        raise ValueError('Recovery copy changed during restore; preserve all evidence')
    return {'status': 'restored-byte-identical', 'inventory_sha256': expected_inventory_sha256,
            **saved}
