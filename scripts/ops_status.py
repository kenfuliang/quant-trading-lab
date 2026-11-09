#!/usr/bin/env python3
"""Offline ops status: write .local/status.json, print a table, deliver alerts.

Exit 0 when healthy, 1 when any check is unhealthy. Reads local files only.
Remote alert sinks are enabled solely by QTL_ALERT_* environment variables.
"""
import argparse
from datetime import timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from paper_trading.alerts import (AlertManager, MacOSNotificationSink, StdoutSink,  # noqa: E402
                                  sinks_from_env)
from paper_trading.health import (HealthConfig, alerts_for, collect, render_table,  # noqa: E402
                                  write_status)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--root', type=Path, default=ROOT / '.local')
    parser.add_argument('--notify', action='store_true', help='also send a macOS notification')
    parser.add_argument('--no-alerts', action='store_true', help='report only; deliver no alerts')
    parser.add_argument('--dedup-minutes', type=float, default=60)
    args = parser.parse_args(argv)

    report = collect(HealthConfig(root=args.root))
    write_status(report, args.root / 'status.json')
    print(render_table(report))
    if not args.no_alerts:
        sinks = [StdoutSink()] + ([MacOSNotificationSink()] if args.notify else []) + sinks_from_env()
        manager = AlertManager(sinks, args.root / 'alerts' / 'alerts.jsonl',
                               window=timedelta(minutes=args.dedup_minutes))
        for alert in alerts_for(report):
            manager.send(alert)
    return 0 if report['healthy'] else 1


if __name__ == '__main__':
    sys.exit(main())
