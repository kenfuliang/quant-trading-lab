"""Alert sinks with a dedup window. Offline by default; remote sinks are env-gated.

Sink interface: any object with ``emit(alert)``. Default sinks are stdout and an
append-only JSON-lines log (``.local/alerts/alerts.jsonl``). The log doubles as
the dedup state: an alert is suppressed when the same ``key`` was logged within
the window, so repeated cron runs do not re-page. Only delivered alerts are
logged. Unreadable log lines are skipped (an alert is never dropped for a bad
log). A failing sink never blocks the others.

Optional sinks: macOS notification (``--notify`` in scripts/ops_status.py) and
remote sinks configured only by environment (no-op when unset, never exercised
in tests, no credentials in tracked files):

* ``QTL_ALERT_NTFY_URL``  full ntfy topic URL; optional ``QTL_ALERT_NTFY_TOKEN``
* ``QTL_ALERT_SMTP_HOST`` with ``QTL_ALERT_EMAIL_TO``; optional ``QTL_ALERT_SMTP_PORT``,
  ``QTL_ALERT_SMTP_USER``, ``QTL_ALERT_SMTP_PASSWORD``, ``QTL_ALERT_EMAIL_FROM``

Alerts carry only check names/states, never account identifiers.
"""
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass(frozen=True)
class Alert:
    key: str
    severity: str
    title: str
    detail: str
    ts: datetime

    def as_dict(self):
        return {'key': self.key, 'severity': self.severity, 'title': self.title,
                'detail': self.detail, 'ts': self.ts.astimezone(timezone.utc).isoformat()}


class StdoutSink:
    def __init__(self, stream=None):
        self.stream = stream

    def emit(self, alert):
        print(f'ALERT {alert.severity.upper()} {alert.title}: {alert.detail}',
              file=self.stream or sys.stdout)


class JsonlFileSink:
    """Append-only; opened in 'a' mode per write and fsynced."""

    def __init__(self, path):
        self.path = Path(path)

    def emit(self, alert):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(alert.as_dict(), sort_keys=True) + '\n'
        with open(self.path, 'a', encoding='utf-8') as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())


class MacOSNotificationSink:
    def __init__(self, runner=None):
        self.runner = runner or (lambda argv: subprocess.run(argv, check=False, timeout=10))

    def emit(self, alert):
        text = (alert.title + ': ' + alert.detail).replace('\\', ' ').replace('"', "'")
        self.runner(['osascript', '-e', f'display notification "{text}" with title "quant-trading-lab"'])


class NtfySink:
    def __init__(self, url, token=None):
        self.url, self.token = url, token

    def emit(self, alert):
        import urllib.request
        request = urllib.request.Request(self.url, data=alert.detail.encode(), method='POST',
                                         headers={'Title': alert.title, 'Priority': 'urgent' if alert.severity == 'critical' else 'default'})
        if self.token:
            request.add_header('Authorization', 'Bearer ' + self.token)
        urllib.request.urlopen(request, timeout=10).close()


class EmailSink:
    def __init__(self, host, to, port=587, user=None, password=None, sender=None):
        self.host, self.to, self.port = host, to, port
        self.user, self.password, self.sender = user, password, sender or user or 'alerts@localhost'

    def emit(self, alert):
        import smtplib
        from email.message import EmailMessage
        message = EmailMessage()
        message['Subject'], message['From'], message['To'] = alert.title, self.sender, self.to
        message.set_content(alert.detail)
        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            smtp.starttls()
            if self.user:
                smtp.login(self.user, self.password or '')
            smtp.send_message(message)


def sinks_from_env(env=None):
    """Remote sinks, only when their environment variables are set."""
    env = os.environ if env is None else env
    sinks = []
    if env.get('QTL_ALERT_NTFY_URL'):
        sinks.append(NtfySink(env['QTL_ALERT_NTFY_URL'], env.get('QTL_ALERT_NTFY_TOKEN')))
    if env.get('QTL_ALERT_SMTP_HOST') and env.get('QTL_ALERT_EMAIL_TO'):
        sinks.append(EmailSink(env['QTL_ALERT_SMTP_HOST'], env['QTL_ALERT_EMAIL_TO'],
                               int(env.get('QTL_ALERT_SMTP_PORT', '587')), env.get('QTL_ALERT_SMTP_USER'),
                               env.get('QTL_ALERT_SMTP_PASSWORD'), env.get('QTL_ALERT_EMAIL_FROM')))
    return sinks


class AlertManager:
    def __init__(self, sinks, log_path, window=timedelta(hours=1)):
        self.sinks = list(sinks)
        self.log = JsonlFileSink(log_path)
        self.window = window

    def _last_sent(self, key):
        latest = None
        try:
            lines = self.log.path.read_text(encoding='utf-8').splitlines()
        except OSError:
            return None
        for line in lines:
            try:
                row = json.loads(line)
                if row['key'] != key:
                    continue
                ts = datetime.fromisoformat(row['ts'])
            except (ValueError, KeyError, TypeError):
                continue
            if ts.tzinfo and (latest is None or ts > latest):
                latest = ts
        return latest

    def send(self, alert):
        """Deliver unless deduped. Returns True when delivered."""
        last = self._last_sent(alert.key)
        if last is not None and alert.ts - last < self.window:
            return False
        # Log first: the durable record must exist even if a sink fails.
        self.log.emit(alert)
        for sink in self.sinks:
            try:
                sink.emit(alert)
            except Exception as error:  # a broken sink must not hide the alert elsewhere
                print(f'alert sink {type(sink).__name__} failed: {type(error).__name__}', file=sys.stderr)
        return True
