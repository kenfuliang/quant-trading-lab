"""Offline proposal and restart evidence; no broker API calls."""
import json
from pathlib import Path
import tempfile
import unittest

from paper_trading.t11_pilot import IntentJournal, PilotError, POLICY_HASH, proposal


class T11PilotTests(unittest.TestCase):
    def plan(self, **changes):
        decision = {'policy_sha256': POLICY_HASH, 'qualification': 'verified',
                    'available_at': '2026-10-28T21:00:00Z',
                    'input_close': '2026-10-28T20:00:00Z', 'gate_cap': '1',
                    'base_weights': {'TQQQ': '.5', 'SOXL': '.5'}}
        decision.update(changes)
        quotes = {s: {'bid': '99.99', 'ask': '100', 'timestamp': '2026-10-29T13:24:59Z'}
                  for s in ['TQQQ', 'SOXL']}
        return proposal(decision, quotes, now='2026-10-29T13:25:00Z',
                        next_open='2026-10-29T13:30:00Z', cash='10000')

    def test_three_gate_caps_and_limit_budget(self):
        green, yellow, red = [self.plan(gate_cap=x) for x in ('1', '.5', '0')]
        self.assertEqual(len(green['orders']), 2)
        self.assertLess(int(yellow['orders'][0]['qty']), int(green['orders'][0]['qty']))
        self.assertEqual(red['orders'], [])
        self.assertFalse(green['order_bearing_ready'])
        from decimal import Decimal
        total = sum(Decimal(o['limit_price'])*Decimal(o['qty']) for o in green['orders'])
        self.assertLessEqual(total, Decimal('9000')-4)

    def test_policy_and_causality_guards(self):
        for changes in [{'policy_sha256': 'x'}, {'qualification': 'unverified'},
                        {'gate_cap': '.75'}, {'base_weights': {'SPY': '1.01'}},
                        {'base_weights': {'UNKNOWN': '1'}},
                        {'available_at': '2026-10-29T14:00:00Z'},
                        {'input_close': '2026-10-01T20:00:00Z'}, {'gate_cap': 'NaN'}]:
            with self.subTest(changes=changes), self.assertRaises(PilotError):
                self.plan(**changes)

    def test_auction_cutoff_cash_and_quotes(self):
        d = {'policy_sha256': POLICY_HASH, 'qualification': 'verified',
             'available_at': '2026-10-28T21:00:00Z', 'input_close': '2026-10-28T20:00:00Z',
             'gate_cap': '1', 'base_weights': {'SPY': '1'}}
        kwargs = dict(now='2026-10-29T13:25:00Z', next_open='2026-10-29T13:30:00Z', cash='10000')
        q = {'SPY': {'bid': '100', 'ask': '101', 'timestamp': '2026-10-29T13:25:00Z'}}
        for override in [{'now': '2026-10-29T13:28:00Z'}, {'cash': '9999'}, {'capital': '10001'},
                         {'now': '2026-10-29T13:25:00'}, {'now': '2026-10-29T12:00:00Z'}]:
            with self.subTest(override=override), self.assertRaises(PilotError):
                proposal(d, q, **(kwargs | override))
        for invalid in [{'bid': '102'}, {'ask': 'NaN'}, {'timestamp': '2026-10-29T13:24:00Z'},
                        {'timestamp': '2026-10-29T13:26:00Z'}, {'ask': '110'}]:
            with self.subTest(invalid=invalid), self.assertRaises(PilotError):
                proposal(d, {'SPY': q['SPY'] | invalid}, **kwargs)

    def test_restart_partial_fill_duplicate_and_terminal(self):
        with tempfile.TemporaryDirectory() as root:
            plan = self.plan()
            order = plan['orders'][0]
            j = IntentJournal(root)
            client = j.reserve(order, plan['proposal_sha256'])
            restarted = IntentJournal(root)
            with self.assertRaises(PilotError):
                restarted.reserve(order, plan['proposal_sha256'])
            observed = order | {'client_order_id': client, 'status': 'partially_filled',
                                'filled_qty': '1', 'filled_avg_price': '100'}
            first = restarted.reconcile(client, observed)
            second = restarted.reconcile(client, observed)
            self.assertEqual(len(second['observations']), 1)
            self.assertEqual(first, second)
            for bad in [{'filled_qty': '0'}, {'symbol': 'SPY'}, {'qty': '999'},
                        {'limit_price': '999'}, {'status': 'mystery'}, {'filled_avg_price': '102'}]:
                with self.subTest(bad=bad), self.assertRaises(PilotError):
                    restarted.reconcile(client, observed | bad)
            canceled = restarted.reconcile(client, observed | {'status': 'canceled'})
            self.assertEqual(canceled['filled_qty'], '1')
            with self.assertRaises(PilotError):
                restarted.reconcile(client, observed | {'status': 'canceled', 'filled_avg_price': '99'})
            with self.assertRaises(PilotError):
                restarted.reconcile(client, observed)
            self.assertEqual(json.loads((Path(root)/(client+'.json')).read_text()), canceled)

    def test_lock_and_invalid_terminal_fill_preserve_unknown(self):
        with tempfile.TemporaryDirectory() as root:
            j = IntentJournal(root)
            p = self.plan(); order = p['orders'][0]
            (Path(root)/'writer.lock').write_text('existing')
            with self.assertRaises(PilotError):
                j.reserve(order, p['proposal_sha256'])
            (Path(root)/'writer.lock').unlink()  # disposable fixture, never real evidence
            client = j.reserve(order, p['proposal_sha256'])
            with self.assertRaises(PilotError):
                j.reconcile(client, order | {'client_order_id': client, 'status': 'filled',
                                            'filled_qty': '1', 'filled_avg_price': '100'})
            self.assertEqual(json.loads((Path(root)/(client+'.json')).read_text())['status'], 'reserved_unknown')


if __name__ == '__main__':
    unittest.main()
