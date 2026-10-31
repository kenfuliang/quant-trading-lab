"""Validate aggregate CAPM study records without importing market data."""
import hashlib
import json
import math
from datetime import date

STUDY = 'capm-spy-v1'


def decode_fragments(texts, case):
    groups = {}
    for text in texts:
        if 'CAP|' not in text:
            continue
        _, actual, sequence, index, total, digest, chunk = text[text.index('CAP|'):].split('|', 6)
        if actual != case:
            continue
        key = int(sequence), int(total), digest
        parts = groups.setdefault(key, {})
        index = int(index)
        if index in parts and parts[index] != chunk:
            raise ValueError('Conflicting fragment')
        parts[index] = chunk
    if not groups:
        raise ValueError('No study fragments')
    output = []
    for (sequence, total, digest), parts in sorted(groups.items()):
        if set(parts) != set(range(total)):
            raise ValueError('Missing fragment')
        raw = ''.join(parts[i] for i in range(total))
        if hashlib.sha256(raw.encode()).hexdigest()[:12] != digest:
            raise ValueError('Fragment checksum mismatch')
        payload = json.loads(raw)
        if payload.get('study') != STUDY or payload.get('case') != case:
            raise ValueError('Study/case mismatch')
        output.append(payload)
    return output


def audit_metrics(records):
    fulls = [r for r in records if r['kind'] == 'full']
    annuals = [r for r in records if r['kind'] == 'annual']
    if len(fulls) != 1 or sorted(r['year'] for r in annuals) != list(range(2016, 2026)):
        raise ValueError('Missing or duplicated result periods')
    full = fulls[0]
    f = full['metrics']
    if abs(f['end']/300000.0-1-f['ret']) > 1e-9:
        raise ValueError('Capital/end NAV mismatch')
    a = full['audit']
    if a['first'] != '2016-01-04' or a['last'] != '2025-12-31':
        raise ValueError('Unexpected closing endpoints')
    days = (date.fromisoformat(a['last'])-date(2015,12,31)).days
    expected_cagr = (f['end']/300000.0)**(365.25/days)-1
    if abs(expected_cagr-f['cagr']) > 1e-9:
        raise ValueError('CAGR mismatch')
    factor = 1.0
    for record in annuals:
        m = record['metrics']
        factor *= 1 + m['ret']
        _audit_ratios(m, annual=True)
    if abs(factor - (1 + f['ret'])) > 1e-8:
        raise ValueError('Annual compounding mismatch')
    if sum(r['metrics']['n'] for r in annuals) != f['n']:
        raise ValueError('Calendar count mismatch')
    _audit_ratios(f, annual=False)
    a = full['audit']
    if a['rejects'] or a['pending'] or abs(a['native_book_residual']) > 2 or abs(a.get('native_fee_residual', float('inf'))) > 0.01 or abs(a['last_mark_residual']) > 0.01:
        raise ValueError('Native execution/accounting audit failed')
    if a['fees'] < 0 or a['interest'] < 0 or not all(math.isfinite(a[k]) for k in ['fees','interest','min_cash','max_gross','native_book_residual']):
        raise ValueError('Invalid accounting summary')
    if a['fee_models'] != ['InteractiveBrokersFeeModel']:
        raise ValueError('Unexpected actual fee model')
    return dict(passed=True, case=full['case'], calendar_hash=a['calendar_hash'], n=f['n'], checks=['all10annualperiods', 'annualcompounding', 'count', 'sampleSharpe', 'Calmar', 'nativebookidentity', 'lastclosingmark', 'fees', 'noinvalidorders', 'nopendingorders'], limits='Native-book identity is not an independent cash/dividend/fill replay; path-level drawdown and underwater duration remain hosted calculations.')


def _audit_ratios(m, annual):
    n = m['n']
    variance = (m['return_square_sum'] - m['return_sum']**2 / n)/(n-1)
    expected = m['return_sum']/n/math.sqrt(max(variance, 0))*math.sqrt(252) if variance > 1e-30 else None
    if expected is None:
        if m['sharpe'] is not None:
            raise ValueError('Undefined Sharpe mismatch')
    elif m['sharpe'] is None or abs(expected - m['sharpe']) > 1e-6:
        raise ValueError('Sharpe mismatch')
    numerator = m['ret'] if annual else m['cagr']
    actual = m['annual_calmar'] if annual else m['calmar']
    expected = numerator / abs(m['dd']) if m['dd'] < 0 else None
    if expected is not None and (actual is None or abs(expected-actual) > 1e-6):
        raise ValueError('Calmar mismatch')
    if not (0 <= m['longest_uw'] <= m['uw'] <= n) or abs(m['uw']/n-m['uw_fraction']) > 1e-10:
        raise ValueError('Underwater bounds mismatch')
