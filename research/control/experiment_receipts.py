"""Offline validation for the GRS experiment-receipt/v1 evidence envelope.

Validation establishes structural completeness and local byte identity, not truth,
financial correctness, comparison eligibility or trading readiness. No discovered
file or URL is followed: only explicitly listed artifacts below root are read.
"""
from datetime import date
import hashlib
from pathlib import Path
import re

SCHEMA = 'experiment-receipt/v1'
STATUSES = {'success', 'failed', 'blocked', 'incomplete'}
CASE_TEXT_FIELDS = ('case_id', 'name', 'run_id', 'source', 'build', 'plan', 'data',
                    'accounting', 'metric_conventions')
SHA256 = re.compile(r'^[0-9a-f]{64}$')


def validate_receipt(receipt, root):
    """Return actionable errors; root is the only allowed artifact filesystem scope.

    Missing values are null, not invented identifiers. Non-success receipts may
    declare a null required value with its exact dotted path and nonempty reason
    in missing_evidence. Required containers cannot themselves be omitted.
    """
    errors = []
    if not isinstance(receipt, dict):
        return ['receipt: expected object']
    if receipt.get('schema') != SCHEMA:
        errors.append(f'schema: expected {SCHEMA}')
    status = receipt.get('status')
    if not isinstance(status, str) or status not in STATUSES:
        errors.append('status: expected success, failed, blocked or incomplete')
    missing = receipt.get('missing_evidence')
    if not isinstance(missing, dict):
        errors.append('missing_evidence: expected path-to-reason object')
        missing = {}
    for key, reason in missing.items():
        if not isinstance(key, str) or not isinstance(reason, str) or not reason.strip():
            errors.append('missing_evidence: every path needs a nonempty reason')
    used_missing = set()

    def text_field(value, path):
        if value is None and path in missing and status != 'success':
            used_missing.add(path)
            return False
        if not isinstance(value, str) or not value.strip():
            errors.append(f'{path}: required nonempty identity/description; unavailable values need null and missing_evidence reason')
            return False
        return True

    text_field(receipt.get('cycle_id'), 'cycle_id')
    if status != 'success':
        text_field(receipt.get('outcome_reason'), 'outcome_reason')
    if status == 'success' and missing:
        errors.append('success: missing evidence is not allowed; use incomplete/blocked/failed')
    cases = receipt.get('cases')
    if not isinstance(cases, list) or not cases:
        errors.append('cases: expected nonempty array (use a named unexecuted case for blocked work)')
        cases = []
    ids = set()
    by_id = {}
    for index, case in enumerate(cases):
        prefix = f'cases.{index}'
        if not isinstance(case, dict):
            errors.append(f'{prefix}: expected object')
            continue
        for field in CASE_TEXT_FIELDS:
            if field not in case:
                errors.append(f'{prefix}.{field}: key required (use explicit null for unavailable evidence)')
            text_field(case.get(field), f'{prefix}.{field}')
        case_id = case.get('case_id')
        if isinstance(case_id, str):
            if case_id in ids:
                errors.append(f'{prefix}.case_id: duplicate {case_id}')
            ids.add(case_id)
            by_id[case_id] = case
        dates = case.get('date_range')
        if not isinstance(dates, dict):
            errors.append(f'{prefix}.date_range: expected start/end object')
        else:
            parsed = {}
            for field in ('start', 'end'):
                if field not in dates:
                    errors.append(f'{prefix}.date_range.{field}: key required (use explicit null for unavailable evidence)')
                value = dates.get(field)
                if text_field(value, f'{prefix}.date_range.{field}'):
                    try:
                        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                            raise ValueError('not extended ISO date')
                        parsed[field] = date.fromisoformat(value)
                    except ValueError:
                        errors.append(f'{prefix}.date_range.{field}: expected ISO YYYY-MM-DD date')
            if len(parsed) == 2 and parsed['start'] > parsed['end']:
                errors.append(f'{prefix}.date_range: start must not follow end')
        attempts = case.get('attempts')
        if not isinstance(attempts, dict):
            errors.append(f'{prefix}.attempts: expected used/limit object')
        else:
            values = [attempts.get(k) for k in ('used', 'limit')]
            if any(type(v) is not int or v < 0 for v in values):
                errors.append(f'{prefix}.attempts: used/limit must be nonnegative integers')
            elif values[0] > values[1]:
                errors.append(f'{prefix}.attempts: used exceeds frozen limit')
    artifacts = receipt.get('artifacts')
    if not isinstance(artifacts, list):
        errors.append('artifacts: expected array of explicit path/sha256/role records')
        artifacts = []
    if status == 'success' and not artifacts:
        errors.append('artifacts: success requires at least one hashed local artifact')
    root = Path(root).resolve()
    seen = set()
    for index, artifact in enumerate(artifacts):
        prefix = f'artifacts.{index}'
        if not isinstance(artifact, dict):
            errors.append(f'{prefix}: expected object')
            continue
        path = artifact.get('path')
        digest = artifact.get('sha256')
        text_field(artifact.get('role'), f'{prefix}.role')
        if not isinstance(path, str) or not path.strip() or Path(path).is_absolute():
            errors.append(f'{prefix}.path: expected nonempty relative local path')
            continue
        if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', path) or path.startswith('//'):
            errors.append(f'{prefix}.path: URI/network paths are forbidden; use a relative local path')
            continue
        try:
            resolved = (root / path).resolve()
        except (OSError, ValueError, RuntimeError):
            errors.append(f'{prefix}.path: invalid local path')
            continue
        if not resolved.is_relative_to(root):
            errors.append(f'{prefix}.path: escapes artifact root (including symlinks)')
            continue
        if resolved in seen:
            errors.append(f'{prefix}.path: duplicate artifact')
        seen.add(resolved)
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            errors.append(f'{prefix}.sha256: expected lowercase SHA256')
            continue
        if not resolved.is_file():
            errors.append(f'{prefix}.path: cannot read {path}: expected regular file')
            continue
        try:
            # Stream to avoid loading large saved exports into memory.
            with resolved.open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual != digest:
                errors.append(f'{prefix}.sha256: hash mismatch for {path}')
        except OSError as exc:
            errors.append(f'{prefix}.path: cannot read {path}: {exc.strerror}')
    groups = receipt.get('comparison_groups', [])
    if not isinstance(groups, list):
        errors.append('comparison_groups: expected array of case-id arrays')
        groups = []
    for index, group in enumerate(groups):
        if not isinstance(group, list) or len(group) < 2 or any(not isinstance(k, str) for k in group):
            errors.append(f'comparison_groups.{index}: expected at least two case IDs')
            continue
        if len(set(group)) != len(group) or any(k not in by_id for k in group):
            errors.append(f'comparison_groups.{index}: unknown or duplicate case IDs')
            continue
        for field in ('metric_conventions', 'date_range', 'accounting'):
            values = [by_id[k].get(field) for k in group]
            if any(v is None for v in values) or any(v != values[0] for v in values[1:]):
                errors.append(f'comparison_groups.{index}: incompatible {field}; do not rank these cases together')
    for key in missing.keys() - used_missing:
        errors.append(f'missing_evidence.{key}: must identify a null required field')
    return errors
