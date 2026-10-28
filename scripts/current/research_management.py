#!/usr/bin/env python3
"""Print an explicit read-only research evidence inventory; no execution adapter."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research.control.research_management import reconcile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.manifest.stat().st_size > 1_000_000:
            raise ValueError('manifest exceeds 1MB')
        result = reconcile(args.evidence_root, json.loads(args.manifest.read_text()))
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({'status': 'invalid', 'reason': str(error)}))
        return 1
    print(json.dumps(result, indent=2))
    statuses = {item['evidence_status'] for item in result['items']}
    return 1 if 'failed' in statuses else (2 if 'unavailable' in statuses else 0)


if __name__ == '__main__':
    raise SystemExit(main())
