"""Reserve bounded launches and decode checksummed derived packets; never dispatch."""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT/'.local/stock-risk-v1'


def decode(texts, case):
    parts = {}
    identity = None
    for text in texts:
        if 'RSG|' not in text:
            continue
        _, name, index, total, digest, chunk = text[text.index('RSG|'):].split('|', 5)
        if name != case:
            continue
        current = (int(total), digest)
        if identity is not None and identity != current:
            raise ValueError('Conflicting packet identity')
        identity = current
        index = int(index)
        if index in parts and parts[index] != chunk:
            raise ValueError('Conflicting fragment')
        parts[index] = chunk
    if identity is None or set(parts) != set(range(identity[0])):
        raise ValueError('Missing packet/fragment')
    plain = ''.join(parts[i] for i in range(identity[0]))
    if hashlib.sha256(plain.encode()).hexdigest()[:12] != identity[1]:
        raise ValueError('Truncated/corrupted packet')
    data = json.loads(plain)
    if data['case'] != case or data['study'] != 'stock-risk-v1':
        raise ValueError('Packet identity mismatch')
    return data


def reserve(case, retry=False):
    path = RAW/'attempts.json'
    ledger = json.loads(path.read_text())
    now = datetime.now(timezone.utc)
    if ledger['status'] != 'active' or now >= datetime.fromisoformat(ledger['deadline_utc']) or len(ledger['attempts']) >= 7:
        raise ValueError('Closed/cap/deadline prevents launch')
    same = [a for a in ledger['attempts'] if a['case'] == case]
    if bool(same) != retry:
        raise ValueError('Duplicate launch or retry without failure')
    if retry and (not same[-1]['status'].startswith('failed') or sum(a['retry'] for a in ledger['attempts']) >= 2):
        raise ValueError('Technical retry not qualified')
    digest = hashlib.sha256((RAW/f'{case}-source.py').read_bytes()).hexdigest()
    if digest != ledger['source_hashes'][case]:
        raise ValueError('Source hash mismatch')
    ledger['attempts'].append(dict(case=case, attempt=len(ledger['attempts'])+1,
                                   retry=retry, status='reserved', source_sha256=digest,
                                   reserved_utc=now.isoformat()))
    path.write_text(json.dumps(ledger,indent=2)+'\n')
    print(ledger['attempts'][-1])


def record(case):
    data = decode(json.loads((RAW/f'{case}-terminal-fragments.json').read_text()), case)
    engine = json.loads((RAW/f'{case}-engine-evidence.json').read_text())
    starts = [x for x in engine if 'Launching analysis for' in x]
    if len(starts) != 1:
        raise ValueError('Native start missing or ambiguous')
    run = re.search(r'Launching analysis for ([a-f0-9]{32}) ', starts[0])[1]
    if not any(run in x and 'completed in' in x for x in engine):
        raise ValueError('Native completion missing')
    overall = data['full']
    assert overall['n'] == 1508
    assert len(data['months']) == 72
    assert not any(overall[k] for k in ('rejects','other_fills','pending_orders','feature_future','feature_invalid','feature_unordered'))
    assert abs(data['residual_usd']) <= .1
    ledger = json.loads((RAW/'attempts.json').read_text())
    pending = [a for a in ledger['attempts'] if a['case'] == case and a['status'] == 'reserved']
    assert len(pending) == 1
    assert pending[0]['source_sha256'] == hashlib.sha256((RAW/f'{case}-source.py').read_bytes()).hexdigest()
    pending[0].update(status='completed-verified', backtest_id=run)
    (RAW/f'{case}-packet.json').write_text(json.dumps(data,indent=2)+'\n')
    (RAW/'attempts.json').write_text(json.dumps(ledger,indent=2)+'\n')
    print(case,run,overall['cagr'],overall['dd'],len(data['contributions']),len(data['months']))


if __name__ == '__main__':
    {'reserve':lambda:reserve(sys.argv[2], '--retry' in sys.argv),
     'record':lambda:record(sys.argv[2])}[sys.argv[1]]()
