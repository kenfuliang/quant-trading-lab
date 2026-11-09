import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from paper_trading.alerts import (Alert, AlertManager, JsonlFileSink, MacOSNotificationSink,
                                  StdoutSink, sinks_from_env)

T0 = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)


class Collect:
    def __init__(self):
        self.alerts = []

    def emit(self, alert):
        self.alerts.append(alert)


class AlertTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.log = self.tmp / 'alerts' / 'alerts.jsonl'

    def alert(self, key='k', when=T0):
        return Alert(key=key, severity='critical', title='t', detail='d', ts=when)

    def test_dedup_window_suppresses_then_reallows(self):
        sink = Collect()
        manager = AlertManager([sink], self.log, window=timedelta(minutes=30))
        self.assertTrue(manager.send(self.alert(when=T0)))
        self.assertFalse(manager.send(self.alert(when=T0 + timedelta(minutes=29))))
        self.assertTrue(manager.send(self.alert('other', T0 + timedelta(minutes=1))))
        self.assertTrue(manager.send(self.alert(when=T0 + timedelta(minutes=31))))
        self.assertEqual([a.key for a in sink.alerts], ['k', 'other', 'k'])

    def test_dedup_survives_new_process(self):
        AlertManager([Collect()], self.log, window=timedelta(hours=1)).send(self.alert())
        again = Collect()
        fresh = AlertManager([again], self.log, window=timedelta(hours=1))
        self.assertFalse(fresh.send(self.alert(when=T0 + timedelta(minutes=5))))
        self.assertEqual(again.alerts, [])

    def test_file_sink_is_append_only(self):
        sink = JsonlFileSink(self.log)
        sink.emit(self.alert('a'))
        first = self.log.read_bytes()
        sink.emit(self.alert('b'))
        data = self.log.read_bytes()
        self.assertTrue(data.startswith(first))
        rows = [json.loads(line) for line in data.splitlines()]
        self.assertEqual([r['key'] for r in rows], ['a', 'b'])
        # A second instance appends rather than truncating.
        JsonlFileSink(self.log).emit(self.alert('c'))
        self.assertEqual(len(self.log.read_text().splitlines()), 3)
        self.assertTrue(self.log.read_bytes().startswith(data))

    def test_corrupt_log_does_not_drop_alerts(self):
        self.log.parent.mkdir(parents=True)
        self.log.write_text('not json\n')
        sink = Collect()
        manager = AlertManager([sink], self.log, window=timedelta(hours=1))
        self.assertTrue(manager.send(self.alert()))

    def test_failing_sink_does_not_block_others(self):
        class Boom:
            def emit(self, alert):
                raise RuntimeError('x')
        sink = Collect()
        AlertManager([Boom(), sink], self.log, window=timedelta(hours=1)).send(self.alert())
        self.assertEqual(len(sink.alerts), 1)

    def test_remote_sinks_noop_without_env(self):
        self.assertEqual(sinks_from_env({}), [])
        self.assertEqual(sinks_from_env({'PATH': '/bin'}), [])

    def test_remote_sinks_enabled_by_env_not_called(self):
        sinks = sinks_from_env({'QTL_ALERT_NTFY_URL': 'https://ntfy.invalid/topic'})
        self.assertEqual(len(sinks), 1)

    def test_macos_sink_uses_injected_runner(self):
        calls = []
        MacOSNotificationSink(runner=calls.append).emit(self.alert())
        self.assertEqual(calls[0][0], 'osascript')

    def test_stdout_sink_prints(self):
        import io
        buf = io.StringIO()
        StdoutSink(buf).emit(self.alert())
        self.assertIn('CRITICAL', buf.getvalue())


if __name__ == '__main__':
    unittest.main()
