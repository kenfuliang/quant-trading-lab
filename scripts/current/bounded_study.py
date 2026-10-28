#!/usr/bin/env python3
"""Validate or execute one explicit local development study; no service imports."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.studies.spy.bounded_study import preflight, run_plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('--execute', action='store_true', help='Without this flag only offline preflight is performed.')
    parser.add_argument('--output-root', type=Path, default=ROOT / 'reports/bounded-study')
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    if args.execute:
        result = run_plan(plan, args.output_root)
        print(json.dumps({k: v for k, v in result.items() if k != 'manifest'}, indent=2))
    else:
        p, raw, _ = preflight(plan)
        print(json.dumps({'status': 'preflight-passed', 'plan_id': p['plan_id'], 'cases': len(p['cases']), 'source_rows': len(raw), 'executed': False}, indent=2))


if __name__ == '__main__':
    main()
