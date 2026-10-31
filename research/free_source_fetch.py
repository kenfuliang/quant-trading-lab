"""Bounded anonymous artifact fetch; log reservation before HTTP, preserve errors."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

STATE = Path('.local/multi-asset-qualification-v2/state.json')


def fetch(url, label):
    state = json.loads(STATE.read_text())
    if len(state['requests']) >= state['artifact_request_limit']:
        raise ValueError('Artifact request ceiling exhausted.')
    if (datetime.now(timezone.utc)-datetime.fromisoformat(state['started_utc'])).total_seconds() >= 5400:
        raise ValueError('Epoch deadline exhausted.')
    domain = urlsplit(url).hostname
    if urlsplit(url).scheme != 'https' or not domain:
        raise ValueError('Anonymous HTTPS sources only.')
    domains = {urlsplit(item['url']).hostname for item in state['requests']} | {domain}
    if len(domains) > state['max_domains']:
        raise ValueError('Provider domain ceiling exhausted.')
    folder = STATE.parent / 'sources'
    folder.mkdir(exist_ok=True)
    path = folder / f'{len(state["requests"])+1:02}-{label}.bin'
    if not label.replace('-', '').isalnum() or path.exists():
        raise ValueError('New simple source label required.')
    record = dict(url=url, path=str(path), status='reserved', started_utc=datetime.now(timezone.utc).isoformat())
    state['requests'].append(record)
    STATE.write_text(json.dumps(state, indent=2)+'\n')
    try:
        with urlopen(Request(url, headers={'User-Agent':'quant-trading-lab-local-research/1.0'}), timeout=25) as response:
            body = response.read(30_000_001)
            if len(body) > 30_000_000:
                raise ValueError('Artifact exceeds30MB bound.')
            path.write_bytes(body)
            record.update(status='received', http_status=response.status, content_type=response.headers.get('Content-Type'),
                          final_url=response.url, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
    except Exception as error:
        record.update(status='failed', error=str(error))
        path.with_suffix('.error.json').write_text(json.dumps(record, indent=2)+'\n')
        raise
    finally:
        STATE.write_text(json.dumps(state, indent=2)+'\n')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url')
    parser.add_argument('label')
    args = parser.parse_args()
    print(json.dumps(fetch(args.url, args.label), indent=2))
