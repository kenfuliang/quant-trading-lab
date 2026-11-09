import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from paper_trading.alerts import AlertManager
from paper_trading.health import HealthConfig, alerts_for, collect, render_table, write_status

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)


def iso(dt):
    return dt.isoformat()


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.cfg = HealthConfig(root=self.root, now=NOW)

    def put(self, rel, payload, raw=False):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload if raw else json.dumps(payload))

    def healthy_tree(self, shadow_age=timedelta(hours=1), data_age=timedelta(hours=10)):
        self.put('shadow/20261108T110000Z/heartbeat.json',
                 {'written_at': iso(NOW - shadow_age), 'status': 'ok'})
        self.put('data/latest_bar.json', {'as_of': iso(NOW - data_age)})
        self.put('orders/a.json', {'client_id': 'a', 'state': 'filled', 'updated_at': iso(NOW)})

    def by_name(self, report):
        return {c['name']: c for c in report['checks']}

    def test_all_healthy(self):
        self.healthy_tree()
        report = collect(self.cfg)
        self.assertTrue(report['healthy'], report)
        self.assertEqual(alerts_for(report), [])

    def test_stale_shadow_run_alerts(self):
        self.healthy_tree(shadow_age=timedelta(hours=60))
        report = collect(self.cfg)
        self.assertFalse(report['healthy'])
        self.assertEqual(self.by_name(report)['shadow']['state'], 'stale')
        self.assertEqual([a.key for a in alerts_for(report)], ['shadow:stale'])

    def test_missing_shadow_is_unhealthy(self):
        self.healthy_tree()
        for p in (self.root / 'shadow').rglob('*.json'):
            p.unlink()
        self.assertEqual(self.by_name(collect(self.cfg))['shadow']['state'], 'missing')

    def test_latest_run_is_judged(self):
        self.healthy_tree()
        self.put('shadow/20260101T000000Z/heartbeat.json', {'written_at': iso(NOW - timedelta(days=90)), 'status': 'ok'})
        self.assertTrue(collect(self.cfg)['healthy'])

    def test_failed_shadow_status_unhealthy(self):
        self.healthy_tree()
        self.put('shadow/20261108T110000Z/heartbeat.json', {'written_at': iso(NOW), 'status': 'failed'})
        self.assertEqual(self.by_name(collect(self.cfg))['shadow']['state'], 'failed')

    def test_engaged_halt_alerts(self):
        self.healthy_tree()
        self.put('kill_switch.json', {'engaged': True, 'reason': 'drill'})
        report = collect(self.cfg)
        self.assertFalse(report['healthy'])
        self.assertEqual(self.by_name(report)['kill_switch']['state'], 'engaged')
        self.assertEqual([a.key for a in alerts_for(report)], ['kill_switch:engaged'])

    def test_absent_sentinel_is_released(self):
        self.healthy_tree()
        self.assertEqual(self.by_name(collect(self.cfg))['kill_switch']['state'], 'released')

    def test_released_sentinel_is_healthy(self):
        self.healthy_tree()
        self.put('kill_switch.json', {'engaged': False})
        self.assertTrue(collect(self.cfg)['healthy'])

    def test_unreadable_state_fails_closed(self):
        cases = {
            'kill_switch': ('kill_switch.json', '{not json'),
            'shadow': ('shadow/20261108T110000Z/heartbeat.json', '[]'),
            'data': ('data/latest_bar.json', '{"as_of": "garbage"}'),
            'journal': ('orders/b.json', ''),
        }
        for name, (rel, raw) in cases.items():
            with self.subTest(name):
                self.healthy_tree()
                self.put(rel, raw, raw=True)
                check = self.by_name(collect(self.cfg))[name]
                self.assertFalse(check['healthy'])
                self.assertEqual(check['state'], 'unreadable')

    def test_kill_switch_unreadable_directory_fails_closed(self):
        self.healthy_tree()
        (self.root / 'kill_switch.json').mkdir()
        check = self.by_name(collect(self.cfg))['kill_switch']
        self.assertFalse(check['healthy'])

    def test_naive_timestamp_unreadable(self):
        self.healthy_tree()
        self.put('data/latest_bar.json', {'as_of': '2026-11-08T10:00:00'})
        self.assertEqual(self.by_name(collect(self.cfg))['data']['state'], 'unreadable')

    def test_future_timestamp_not_fresh(self):
        self.healthy_tree()
        self.put('data/latest_bar.json', {'as_of': iso(NOW + timedelta(days=30))})
        self.assertFalse(self.by_name(collect(self.cfg))['data']['healthy'])

    def test_stale_data(self):
        self.healthy_tree(data_age=timedelta(days=10))
        self.assertEqual(self.by_name(collect(self.cfg))['data']['state'], 'stale')

    def test_unresolved_and_old_pending_orders(self):
        self.healthy_tree()
        self.put('orders/u.json', {'client_id': 'u', 'state': 'unresolved', 'updated_at': iso(NOW)})
        self.assertEqual(self.by_name(collect(self.cfg))['journal']['state'], 'unresolved')
        (self.root / 'orders/u.json').unlink()
        self.put('orders/p.json', {'client_id': 'p', 'state': 'pending', 'updated_at': iso(NOW - timedelta(hours=1))})
        self.assertEqual(self.by_name(collect(self.cfg))['journal']['state'], 'stuck')

    def test_unknown_order_state_fails_closed(self):
        self.healthy_tree()
        self.put('orders/x.json', {'client_id': 'x', 'state': 'weird', 'updated_at': iso(NOW)})
        self.assertFalse(self.by_name(collect(self.cfg))['journal']['healthy'])

    def test_no_orders_is_healthy(self):
        self.healthy_tree()
        (self.root / 'orders/a.json').unlink()
        self.assertTrue(self.by_name(collect(self.cfg))['journal']['healthy'])

    def test_status_json_and_table(self):
        self.healthy_tree()
        self.put('kill_switch.json', {'engaged': True})
        report = collect(self.cfg)
        out = write_status(report, self.root / 'status.json')
        self.assertEqual(json.loads(out.read_text())['healthy'], False)
        table = render_table(report)
        self.assertIn('kill_switch', table)
        self.assertIn('engaged', table)

    def test_status_does_not_leak_reason_free_text_beyond_detail(self):
        self.healthy_tree()
        self.put('kill_switch.json', {'engaged': True, 'reason': 'x', 'account': 'DU123456'})
        self.assertNotIn('DU123456', json.dumps(collect(self.cfg)))

    def test_end_to_end_alert_dedup(self):
        self.healthy_tree(shadow_age=timedelta(hours=60))
        manager = AlertManager([], self.root / 'alerts' / 'alerts.jsonl', window=timedelta(hours=1))
        sent = [manager.send(a) for a in alerts_for(collect(self.cfg))]
        again = [manager.send(a) for a in alerts_for(collect(self.cfg))]
        self.assertEqual((sent, again), ([True], [False]))


if __name__ == '__main__':
    unittest.main()
