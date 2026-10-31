#!/usr/bin/env python3
"""Copy or restore a closed research file bundle; never resume its experiment."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.control.evidence_recovery import create_recovery_copy, restore_recovery_copy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    backup = commands.add_parser('backup')
    backup.add_argument('source', type=Path)
    backup.add_argument('destination', type=Path)
    restore = commands.add_parser('restore')
    restore.add_argument('backup', type=Path)
    restore.add_argument('destination', type=Path)
    restore.add_argument('--inventory-sha256', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'backup':
            result = create_recovery_copy(args.source, args.destination)
        else:
            result = restore_recovery_copy(args.backup, args.destination, args.inventory_sha256)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, 'Evidence recovery stopped; preserve all existing files: ' + str(error) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'file_hashes'}, indent=2))


if __name__ == '__main__':
    main()
