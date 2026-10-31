"""Strict parser for explicitly captured UR summary records; no execution."""
import json
import hashlib
import base64
import zlib
import math
import re


def extract_records(text, case_id):
    records = {}
    for section, key, raw in re.findall(r'UR\|' + re.escape(case_id) + r'\|([^|\n]+)\|([^|\n]+)\|([^\n]+)', text):
        try:
            value = json.loads(raw.strip(), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        except (ValueError, TypeError):
            continue
        part = records.setdefault(section, {})
        if key in part and part[key] != value:
            raise ValueError('Conflicting captured values')
        part[key] = value
    for section, raw in re.findall(r'URJ\|' + re.escape(case_id) + r'\|([^|\n]+)\|([^\n]+)', text):
        value = json.loads(raw.strip(), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        if section in records and records[section] != value:
            raise ValueError('Conflicting readable records')
        records[section] = value
    text_chunks = re.findall(r'UTXT\|' + re.escape(case_id) + r'\|(\d+)\|(\d+)\|([^\n]+)', text)
    if text_chunks:
        counts = {int(n) for _, n, _ in text_chunks}
        if len(counts) != 1:
            raise ValueError('Conflicting readable chunk count')
        count = counts.pop()
        parts = {}
        for i, _, part in text_chunks:
            i = int(i)
            if i in parts and parts[i] != part:
                raise ValueError('Conflicting readable chunk')
            parts[i] = part
        if set(parts) != set(range(count)):
            raise ValueError('Incomplete readable capture')
        records = json.loads(''.join(parts[i] for i in range(count)), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    chunks = re.findall(r'U8Z\|' + re.escape(case_id) + r'\|(\d+)\|(\d+)\|([0-9a-f]{12})\|([^\n]+)', text)
    if chunks:
        identities = {(int(n), h) for _, n, h, _ in chunks}
        if len(identities) != 1:
            raise ValueError('Conflicting packed capture identity')
        n, digest = identities.pop()
        parts = {}
        for i, _, _, chunk in chunks:
            i = int(i)
            if i in parts and parts[i] != chunk:
                raise ValueError('Conflicting packed chunk')
            parts[i] = chunk
        if set(parts) != set(range(n)):
            raise ValueError('Incomplete packed capture')
        encoded = ''.join(parts[i] for i in range(n))
        decoder = zlib.decompressobj()
        raw = decoder.decompress(base64.b64decode(encoded, validate=True), 100001)
        if len(raw) > 100000 or not decoder.eof or decoder.unused_data:
            raise ValueError('Invalid/oversized packed capture')
        payload = raw.decode()
        if hashlib.sha256(payload.encode()).hexdigest()[:12] != digest:
            raise ValueError('Packed capture hash mismatch')
        packed = json.loads(payload, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        if records and records != packed:
            raise ValueError('Conflicting typed/packed records')
        records = packed
    return records


def parse_capture(text, case_id):
    records = extract_records(text, case_id)
    expected = {'n', 'end', 'cagr', 'dd', 'calmar', 'sharpe', 'longest_sessions',
                'longest_days', 'longest_censored', 'temporal'}
    for section in ('overall', *(f'Y{y}' for y in range(2020, 2026))):
        required = expected | ({'year', 'return', 'annual_calmar'} if section != 'overall' else set())
        missing = required - records.get(section, {}).keys()
        if missing:
            raise ValueError(f'{section}: missing complete fields {sorted(missing)}')
        row = records[section]
        for key in required - {'year', 'temporal', 'longest_censored'}:
            value = row[key]
            if value is None and key in {'sharpe', 'calmar', 'annual_calmar'}:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f'{section}.{key}: invalid numeric field')
        if row['temporal'] != 'recovery-inclusive-v1.2':
            raise ValueError('Wrong temporal convention')
    audit = records.get('audit', {})
    required = {'rejects', 'fills', 'pending', 'financing', 'gate_seed', 'rank_n',
                'gate_hash', 'feature_hash', 'calendar_hash', 'debit_error'}
    if required - audit.keys():
        raise ValueError('Missing complete audit fields')
    for key in ('gate_hash', 'feature_hash', 'calendar_hash'):
        if not isinstance(audit[key], str) or not re.fullmatch('[0-9a-f]{64}', audit[key]):
            raise ValueError('Incomplete audit digest')
    if audit['rejects'] or audit['debit_error'] > 1e-5:
        raise ValueError('Native execution/account invariant failed')
    pending = records.get('terminal_orders', [])
    if len(pending) != audit['pending']:
        raise ValueError('Terminal pending orders not captured')
    for order in pending:
        kind = str(order.get('type', '')).replace('_', '').lower()
        if kind != 'marketonopen' or str(order.get('time', ''))[:10] != '2025-12-31':
            raise ValueError('Unexpected terminal pending order')
    if records['overall']['n'] != 1508 or audit['gate_seed'] < 200:
        raise ValueError('Unexpected calendar/warmup coverage')
    return records
