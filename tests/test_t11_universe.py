import math
import json
import base64
import zlib
import hashlib
import unittest
import pandas as pd

from research.studies.t11_universe.selection import FAMILY, UNIVERSE, align_histories, causal_window, select
from research.studies.t11_universe.metrics import annual, summarize
from reporting.temporal import analyze_temporal
from reporting.universe_review import parse_capture


def path(growth=.001):
    values = [100.]
    for i in range(252):
        values.append(values[-1] * (1 + growth + .002 * math.sin(i)))
    return values


class UniverseSelectionTests(unittest.TestCase):
    def test_readable_capture_chunks(self):
        from reporting.universe_review import extract_records
        payload = {'overall': {'calmar': .35}, 'audit': {'rejects': 0}}
        line = json.dumps(payload, separators=(',', ':'))
        chunks = [line[i:i+20] for i in range(0, len(line), 20)]
        text = '\n'.join(f'UTXT|case|{i}|{len(chunks)}|{part}' for i, part in enumerate(chunks))
        self.assertEqual(extract_records(text, 'case'), payload)
        with self.assertRaises(ValueError):
            extract_records(text.rsplit('\n', 1)[0], 'case')

    def test_common_panel_records_bounded_lag_without_future_or_imputation(self):
        dates = pd.bdate_range(end='2024-11-29', periods=260)
        cutoff = pd.Timestamp('2024-11-29T13:00').to_pydatetime()
        records = [(d.date().isoformat(), d.replace(hour=16).to_pydatetime(), 100.) for d in dates]
        records = [r for r in records if r[0] != '2024-11-28']
        h = {s: list(records) for s in UNIVERSE}
        # Thanksgiving is excluded; prior exchange session is Wednesday.
        allowed = {'2024-11-29', '2024-11-27'}
        days, panel = align_histories(h, cutoff=cutoff, allowed_latest=allowed)
        self.assertEqual(days[-1], '2024-11-27')
        self.assertEqual(len(days), 253)
        self.assertEqual(set(panel), set(UNIVERSE))
        h['TECL'] = h['TECL'][:-2]
        with self.assertRaises(ValueError):
            align_histories(h, cutoff=cutoff, allowed_latest=allowed)
        with self.assertRaises(ValueError):
            align_histories(h, cutoff=cutoff, allowed_latest={'2024-11-29'})

    def test_early_close_overfetch_keeps_only_causal_current_window(self):
        dates = pd.bdate_range(end='2024-11-29', periods=254)
        cutoff = pd.Timestamp('2024-11-29T13:00:00').to_pydatetime()
        records = [(d.date().isoformat(), d.replace(hour=16).to_pydatetime(), 100.) for d in dates]
        records[-1] = ('2024-11-29', cutoff, 101.)
        window, values = causal_window(records, cutoff=cutoff, session='2024-11-29')
        self.assertEqual(len(window), 253)
        self.assertEqual(values[-1], 101.)
        future = ('2024-12-02', pd.Timestamp('2024-12-02T16:00').to_pydatetime(), 999.)
        self.assertEqual((window, values), causal_window([*records, future], cutoff=cutoff, session='2024-11-29'))
        with self.assertRaises(ValueError):
            causal_window([*records[:-1], future], cutoff=cutoff, session='2024-11-29')
        with self.assertRaises(ValueError):
            causal_window([*records, records[-1]], cutoff=cutoff, session='2024-11-29')

    def test_family_exclusion_and_deterministic_tie(self):
        data = {s: path() for s in UNIVERSE}
        proposal = select(data)
        self.assertEqual(proposal.weights, (('QQQ', .5), ('SOXL', .5)))
        self.assertEqual(len({FAMILY[s] for s, _ in proposal.weights}), 2)
        self.assertEqual(proposal, select(dict(reversed(list(data.items())))))

    def test_cash_and_single_half_budget(self):
        data = {s: path(-.001) for s in UNIVERSE}
        self.assertEqual(select(data).weights, ())
        data['VTI'] = path()
        self.assertEqual(select(data).weights, (('VTI', .5),))

    def test_zero_volatility_is_not_infinite_winner(self):
        data = {s: [100.] * 253 for s in UNIVERSE}
        p = select(data)
        self.assertEqual(p.weights, ())
        self.assertTrue(all(r.score is None for r in p.ranking))

    def test_missing_extra_short_and_invalid_inputs_rejected(self):
        data = {s: path() for s in UNIVERSE}
        for value in (None, float('nan'), float('inf'), 0, -1, True):
            bad = {**data, 'VTI': [*data['VTI'][:-1], value]}
            with self.assertRaises(ValueError):
                select(bad)
        for bad in ({k: v for k, v in data.items() if k != 'VTI'},
                    {**data, 'SPY': path()}, {**data, 'VTI': path()[:-1]}):
            with self.assertRaises(ValueError):
                select(bad)

    def test_window_formula_against_independent_variance(self):
        p = select({s: path() for s in UNIVERSE})
        values = path()
        r = [values[i] / values[i-1] - 1 for i in range(190, 253)]
        mean = sum(r) / 63
        vol = math.sqrt(sum((v-mean)**2 for v in r) / 62 * 252)
        self.assertAlmostEqual(p.ranking[0].volatility, vol)
        self.assertAlmostEqual(p.ranking[0].momentum, values[-1]/values[0]-1)

    def test_cloud_metrics_against_temporal_owner(self):
        days = pd.bdate_range('2020-01-02', periods=8)
        values = [11000., 9000., 9500., 11000., 10500., 10000., 12000., 11900.]
        rows = [(d.date().isoformat(), v) for d, v in zip(days, values)]
        result = summarize(rows)
        eq = pd.Series([10000., *values], index=pd.DatetimeIndex(['2019-12-31', *days]))
        reference, _ = analyze_temporal(eq, initial_capital=10000.)
        self.assertAlmostEqual(result['dd'], float((eq/eq.cummax()-1).min()))
        self.assertEqual(result['longest_sessions'], 3)
        self.assertEqual(result['longest_days'], 5)
        self.assertFalse(result['longest_censored'])
        self.assertEqual(result['longest_sessions'], reference['longest_underwater_duration_sessions'])
        self.assertEqual(result['longest_days'], reference['longest_underwater_duration_calendar_days'])
        self.assertEqual(result['longest_censored'], reference['longest_underwater_right_censored'])

    def test_annual_anchor_and_invalid_paths(self):
        rows = [('2020-12-31', 11000.), ('2021-01-04', 9900.), ('2021-12-31', 12100.)]
        results = annual(rows)
        self.assertAlmostEqual(results[1]['return'], .1)
        self.assertAlmostEqual(results[1]['dd'], -.1)
        self.assertAlmostEqual(results[1]['annual_calmar'], 1.)
        for bad in ([rows[0], rows[0]], [('2020-01-02', 0.)]):
            with self.assertRaises(ValueError):
                summarize(bad)

    def test_capture_requires_complete_conventions_and_identity(self):
        row = dict(n=1508, end=12000., cagr=.03, dd=-.1, calmar=.3, sharpe=.5,
                   longest_sessions=20, longest_days=28, longest_censored=False,
                   temporal='recovery-inclusive-v1.2')
        records = {'overall': row}
        records.update({f'Y{y}': dict(row, year=str(y), **{'return': .1, 'annual_calmar': 1.})
                        for y in range(2020, 2026)})
        records['audit'] = dict(rejects=0, fills=10, pending=0, financing=0., gate_seed=4000,
            rank_n=73, gate_hash='a'*64, feature_hash='b'*64, calendar_hash='c'*64, debit_error=0.)
        text = '\n'.join(f'UR|rs125|{section}|{key}|{json.dumps(value)}'
                         for section, payload in records.items() for key, value in payload.items())
        self.assertEqual(parse_capture(text, 'rs125'), records)
        def packed_capture(payload):
            raw = json.dumps(payload, separators=(',', ':'))
            digest = hashlib.sha256(raw.encode()).hexdigest()[:12]
            encoded = base64.b64encode(zlib.compress(raw.encode())).decode()
            chunks = [encoded[i:i+60] for i in range(0, len(encoded), 60)]
            return '\n'.join(f'U8Z|rs125|{i}|{len(chunks)}|{digest}|{chunk}' for i, chunk in enumerate(chunks))
        packed = packed_capture(records)
        self.assertEqual(parse_capture(packed, 'rs125'), records)
        with self.assertRaises(ValueError):
            parse_capture('\n'.join(packed.splitlines()[:-1]), 'rs125')
        terminal = json.loads(json.dumps(records))
        terminal['audit']['pending'] = 1
        terminal['terminal_orders'] = [dict(type='MarketOnOpen', time='2025-12-31 21:00:00')]
        self.assertEqual(parse_capture(packed_capture(terminal), 'rs125'), terminal)
        terminal['terminal_orders'][0]['type'] = 'Market'
        with self.assertRaises(ValueError):
            parse_capture(packed_capture(terminal), 'rs125')
        for bad in (text.replace('recovery-inclusive-v1.2', 'legacy'),
                    text.replace('"'+'c'*64+'"', '"'+'c'*30+'...'),
                    text+'\nUR|rs125|overall|end|13000'):
            with self.assertRaises(ValueError):
                parse_capture(bad, 'rs125')
        with self.assertRaises(ValueError):
            parse_capture(text, 'wrong_case')
