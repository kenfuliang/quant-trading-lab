#!/usr/bin/env python3
"""Independently inspect saved ledgers without running financial simulations."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.evaluation.saved_review import digest, inspect, verify_artifacts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--cases', nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = {'schema_version': 1, 'observation_kind': 'read_only_analysis',
              'input_directory': str(args.directory), **verify_artifacts(args.directory),
              'cases': {name: inspect(args.directory / name) for name in args.cases},
              'reviewer_code_sha256': digest(__file__),
              'independent_metrics_code_sha256': digest(ROOT / 'research/evaluation/saved_review.py'),
              'executed_financial_trials': 0}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError('Preserve existing receipt; select a new output path.')
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({name: data['overall'] for name, data in report['cases'].items()}, indent=2))



if __name__ == "__main__":
    main()
