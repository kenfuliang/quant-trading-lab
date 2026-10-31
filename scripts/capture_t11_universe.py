#!/usr/bin/env python3
"""Validate and record one saved cloud observation; never launch a backtest."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reporting.universe_review import parse_capture


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('case')
    args = parser.parse_args()
    root = Path('.local/t11-universe-cloud-v11')
    text = (root / args.case / 'result.ax.txt').read_text()
    result = parse_capture(text, args.case)
    ids = re.findall(r'result-tab-statistics-([0-9a-f]{32})-Tab', text)
    launches = re.findall(r'Launching analysis for ([0-9a-f]{32}) with LEAN Engine v([^\s]+)', text)
    if not launches:
        raise ValueError('No captured run/build identity')
    run_id, engine = launches[-1]
    if ids and ids[-1] != run_id:
        raise ValueError('Visible result/run identity mismatch')
    if not re.search(r"Algorithm (?:'" + run_id + r"' completed|Id:\(" + run_id + r'\) completed)', text):
        raise ValueError('No observed completion for this run')
    title = re.search(r'AXWebArea (.*?) — workspace', text)
    journal = json.loads((root / 'journal.json').read_text())
    attempt = journal['attempts'][-1]
    if attempt['case_id'] != args.case or attempt.get('source_revision') != 'v11':
        raise ValueError('Journal case/revision mismatch')
    frozen = json.loads((root / 'frozen-plan.json').read_text())
    case = next(c for c in frozen['cases'] if c['case_id'] == args.case)
    if hashlib.sha256(Path(case['source']).read_bytes()).hexdigest() != attempt['source_sha256']:
        raise ValueError('Frozen source changed')
    for prior in journal['attempts'][:-1]:
        if prior.get('source_revision') == 'v11' and prior.get('status') == 'completed_provisional':
            previous = json.loads((root / prior['case_id'] / 'captured.json').read_text())
            for key in ('gate_hash', 'feature_hash', 'calendar_hash', 'rank_n', 'lagged_n'):
                if result['audit'].get(key) != previous['records']['audit'].get(key):
                    raise ValueError('Shared input/calendar mismatch: ' + key)
    capture = dict(case_id=args.case, run_id=run_id, engine=engine,
                   name=title.group(1) if title else None, source_sha256=attempt['source_sha256'],
                   records=result, status='completed_provisional', official_export_verified=False,
                   independent_account_reconciliation=False)
    (root / args.case / 'captured.json').write_text(json.dumps(capture, indent=2)+'\n')
    attempt.update(status='completed_provisional', run_id=run_id, engine=engine,
                   name=capture['name'], captured_utc=datetime.now(timezone.utc).isoformat())
    (root / 'journal.json').write_text(json.dumps(journal, indent=2)+'\n')
    print(json.dumps({'case': args.case, 'run_id': run_id, **result['overall'],
                      'rank_n': result['audit']['rank_n'], 'lagged_n': result['audit'].get('lagged_n')}))


if __name__ == '__main__':
    main()
