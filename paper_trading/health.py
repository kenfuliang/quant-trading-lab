"""Heartbeat/freshness view over local operational state. Reads only; no network.

File contracts (all under the state root, default ``.local/``; UTC ISO-8601
timestamps WITH offset; producers are other packets and are not imported):

* Shadow runs: ``shadow/<UTC-run-dir>/heartbeat.json`` =
  ``{"written_at": ts, "status": "ok"|"failed"}``. The lexicographically last
  run directory is judged; none found is ``missing``.
* Kill switch: ``kill_switch.json`` = ``{"engaged": bool, ...}``. Absent means
  released; engaged or unreadable (corrupt, directory, wrong type) is unhealthy.
* Order journal: ``orders/*.json``, each ``{"client_id", "state", "updated_at"}``
  with state in pending|submitted|filled|cancelled|rejected|unresolved.
  ``unresolved`` or unknown state is unhealthy; ``pending`` older than
  ``pending_max_age`` is ``stuck``.
* Data age: ``data/latest_bar.json`` = ``{"as_of": ts}``; older than
  ``data_max_age`` is ``stale`` (default covers a long weekend), missing unhealthy.

Real producers are read first (this is what the repo actually writes); the
fixture contracts above remain a fallback:

* Shadow: ``shadow/<run>/plan.json`` (``created_utc``) + ``summary.json``
  (``status`` completed|completed_no_replay ok, completed_flagged = tracking
  mismatch, anything else failed; ``last_close`` date also feeds the data check).
* Kill switch: ``kill-switch/HALT`` written by ``paper_trading.kill_switch``;
  present or unreadable means engaged.
* Order journal: ``alpaca-paper/runs/*/journal.json`` (list of entries with a
  ``status``); file mtime is the update time.

Fail closed: anything unreadable or unrecognised is reported unhealthy
(``unreadable``), never skipped. Output is limited to check names, states and
ages; free-text fields in state files (reasons, accounts) are not copied.
"""
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from paper_trading.alerts import Alert
from paper_trading.kill_switch import KillSwitch

ORDER_STATES = {'pending', 'submitted', 'filled', 'cancelled', 'rejected', 'unresolved'}
JOURNAL_STATES = {'reserved': 'pending', 'accepted': 'submitted', 'filled': 'filled',
                  'rejected': 'rejected', 'canceled': 'cancelled', 'expired': 'cancelled',
                  'never_sent': 'cancelled', 'unknown_submission': 'unresolved',
                  'reconciliation_required': 'unresolved', 'cancel_requested_unconfirmed': 'unresolved'}


@dataclass
class HealthConfig:
    root: Path = Path('.local')
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    shadow_max_age: timedelta = timedelta(hours=36)
    data_max_age: timedelta = timedelta(hours=96)
    pending_max_age: timedelta = timedelta(minutes=15)


class Unreadable(Exception):
    pass


def _load(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise Unreadable(type(error).__name__) from error
    if not isinstance(data, dict):
        raise Unreadable('not an object')
    return data


def _ts(value):
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise Unreadable('bad timestamp') from error
    if parsed.tzinfo is None:
        raise Unreadable('naive timestamp')
    return parsed.astimezone(timezone.utc)


def _age(value, now):
    age = now - _ts(value)
    if age < timedelta(minutes=-5):
        raise Unreadable('timestamp in future')
    return age


def _check(name, healthy, state, detail):
    return {'name': name, 'healthy': healthy, 'state': state, 'detail': detail}


def _guarded(name, fn):
    try:
        return fn()
    except Unreadable as error:
        return _check(name, False, 'unreadable', str(error))
    except Exception as error:
        return _check(name, False, 'unreadable', type(error).__name__)


def _hours(age):
    return f'{age.total_seconds() / 3600:.1f}h'


def _shadow_runs(cfg):
    shadow = cfg.root / 'shadow'
    return sorted(p for p in shadow.iterdir() if p.is_dir()) if shadow.is_dir() else []


def _shadow_beat(run):
    """Heartbeat from the fixture file, else from the real runner's plan and summary."""
    if (run / 'heartbeat.json').exists():
        return _load(run / 'heartbeat.json')
    if not (run / 'summary.json').exists() or not (run / 'plan.json').exists():
        return None
    status = _load(run / 'summary.json').get('status')
    ok = isinstance(status, str) and status.startswith('completed') and status != 'completed_flagged'
    return {'written_at': _load(run / 'plan.json').get('created_utc'), 'status': 'ok' if ok else status}


def check_shadow(cfg):
    runs = []
    shadow = cfg.root / 'shadow'
    if shadow.is_dir():
        runs = sorted(p for p in shadow.iterdir() if p.is_dir())
    if not runs:
        return _check('shadow', False, 'missing', 'no shadow run directories')
    data = _shadow_beat(runs[-1])
    if data is None:
        return _check('shadow', False, 'missing', 'latest run has no heartbeat')
    age = _age(data.get('written_at'), cfg.now)
    if data.get('status') == 'completed_flagged':
        return _check('shadow', False, 'flagged', 'latest run flagged a tracking mismatch')
    if data.get('status') != 'ok':
        return _check('shadow', False, 'failed', f'latest run status {data.get("status")!r}')
    if age > cfg.shadow_max_age:
        return _check('shadow', False, 'stale', f'last heartbeat {_hours(age)} ago')
    return _check('shadow', True, 'fresh', f'last heartbeat {_hours(age)} ago')


def check_kill_switch(cfg):
    sentinel = cfg.root / 'kill-switch' / 'HALT'
    if os.path.lexists(sentinel):
        status = KillSwitch(sentinel).status()
        broken = status.get('reason') in ('unreadable_sentinel', 'malformed_sentinel')
        return _check('kill_switch', False, 'engaged',
                      'sentinel unreadable; treated as engaged' if broken else 'trading halted by sentinel')
    path = cfg.root / 'kill_switch.json'
    if not os.path.lexists(path):
        return _check('kill_switch', True, 'released', 'no sentinel')
    engaged = _load(path).get('engaged')
    if not isinstance(engaged, bool):
        raise Unreadable('engaged is not a bool')
    if engaged:
        return _check('kill_switch', False, 'engaged', 'trading halted by sentinel')
    return _check('kill_switch', True, 'released', 'sentinel released')


def check_journal(cfg):
    directory = cfg.root / 'orders'
    files = sorted(directory.glob('*.json')) if directory.is_dir() else []
    counts, problem = {}, None
    for path in files:
        row = _load(path)
        state = row.get('state')
        if state not in ORDER_STATES:
            raise Unreadable('unknown order state')
        age = _age(row.get('updated_at'), cfg.now)
        counts[state] = counts.get(state, 0) + 1
        if state == 'unresolved':
            problem = problem or ('unresolved', 'unresolved order requires reconciliation')
        elif state == 'pending' and age > cfg.pending_max_age:
            problem = problem or ('stuck', f'pending order {_hours(age)} old')
    for path in sorted((cfg.root / 'alpaca-paper' / 'runs').glob('*/journal.json')):
        try:
            entries = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as error:
            raise Unreadable(type(error).__name__) from error
        if not isinstance(entries, list):
            raise Unreadable('journal is not a list')
        updated = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        for entry in entries:
            state = JOURNAL_STATES.get(entry.get('status')) if isinstance(entry, dict) else None
            if state is None:
                raise Unreadable('unknown journal status')
            counts[state] = counts.get(state, 0) + 1
            if state == 'unresolved':
                problem = problem or ('unresolved', 'unresolved order requires reconciliation')
            elif state == 'pending' and cfg.now - updated > cfg.pending_max_age:
                problem = problem or ('stuck', f'pending order {_hours(cfg.now - updated)} old')
    summary = ', '.join(f'{k}={v}' for k, v in sorted(counts.items())) or 'no orders'
    if problem:
        return _check('journal', False, problem[0], f'{problem[1]} ({summary})')
    return _check('journal', True, 'ok', summary)


def check_data(cfg):
    path = cfg.root / 'data' / 'latest_bar.json'
    if path.exists():
        as_of = _load(path).get('as_of')
    else:
        runs = [r for r in _shadow_runs(cfg) if (r / 'summary.json').exists()]
        last = _load(runs[-1] / 'summary.json').get('last_close') if runs else None
        if last is None:
            return _check('data', False, 'missing', 'no latest_bar.json or shadow last_close')
        as_of = f'{last}T21:00:00+00:00'  # US close, conservatively late in UTC
    age = _age(as_of, cfg.now)
    if age > cfg.data_max_age:
        return _check('data', False, 'stale', f'latest bar {_hours(age)} old')
    return _check('data', True, 'fresh', f'latest bar {_hours(age)} old')


CHECKS = (('shadow', check_shadow), ('kill_switch', check_kill_switch),
          ('journal', check_journal), ('data', check_data))


def collect(cfg):
    checks = [_guarded(name, lambda fn=fn: fn(cfg)) for name, fn in CHECKS]
    return {'generated_at': cfg.now.astimezone(timezone.utc).isoformat(),
            'healthy': all(c['healthy'] for c in checks), 'checks': checks}


def alerts_for(report):
    now = datetime.fromisoformat(report['generated_at'])
    return [Alert(key=f"{c['name']}:{c['state']}", severity='critical',
                  title=f"{c['name']} {c['state']}", detail=c['detail'], ts=now)
            for c in report['checks'] if not c['healthy']]


def write_status(report, path):
    """Atomic write so readers never see a partial status.json."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.status-')
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write('\n')
    os.replace(tmp, path)
    return path


def render_table(report):
    rows = [('CHECK', 'STATE', 'OK', 'DETAIL')] + [
        (c['name'], c['state'], 'yes' if c['healthy'] else 'NO', c['detail']) for c in report['checks']]
    widths = [max(len(r[i]) for r in rows) for i in range(3)]
    lines = ['  '.join(r[i].ljust(widths[i]) for i in range(3)) + '  ' + r[3] for r in rows]
    lines.append('overall: ' + ('HEALTHY' if report['healthy'] else 'UNHEALTHY'))
    return '\n'.join(lines)
