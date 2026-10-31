"""Read-only official QC result inspection; no data downloads or simulations.

Candidate close paths use the next New York midnight candle CLOSE, with an exact
16:00 NY terminal sample for this declared2020–2025 export profile. This mapping
must pass calendar and legacy aggregate checks before descriptive comparison.
It is not an original decision log, a proven engine trace or a self-financing
cash/position replay. Preserve raw exports privately and bind parser/calendar.
"""
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import math
from zoneinfo import ZoneInfo

from .reference import compare_path, legacy_metrics

NY = ZoneInfo('America/New_York')


def positive(value):
    if isinstance(value, bool):
        raise ValueError('Numeric positive observation required.')
    x = float(value)
    if not math.isfinite(x) or x <= 0:
        raise ValueError('Positive finite observation required.')
    return x


def stamp(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timezone-aware order time required.')
    return dt


def inspect_export(document, *, name, backtest_id, sessions, reference):
    if sessions != sorted(set(sessions)) or not sessions:
        raise ValueError('Strictly ordered unique calendar required.')
    for day in sessions:
        date.fromisoformat(day)
    state = document['state']
    if state.get('Name') != name or state.get('Hostname') != 'BACKTESTING-com-' + backtest_id:
        raise ValueError('Wrong exported backtest identity.')
    if state.get('Status') != 'Completed' or state.get('RuntimeError'):
        raise ValueError('Backtest did not complete cleanly.')
    config = document['algorithmConfiguration']
    if stamp(config['startDate']).date().isoformat() != '2020-01-01' or stamp(config['endDate']).date().isoformat() != '2025-12-31':
        raise ValueError('Unexpected reference date range.')
    if positive(document['statistics']['Start Equity']) != 10000:
        raise ValueError('Wrong initial capital.')
    series = document['charts']['Strategy Equity']['series']['Equity']
    if series['seriesType'] != 2 or series.get('unit') != '$':
        raise ValueError('Expected USD OHLC equity candles.')
    samples = {}
    cadence = Counter()
    previous = None
    for point in series['values']:
        if len(point) != 5 or isinstance(point[0], bool) or not isinstance(point[0], (int, float)) or not math.isfinite(point[0]):
            raise ValueError('Invalid timestamp/OHLC point.')
        ts = datetime.fromtimestamp(point[0], timezone.utc).astimezone(NY)
        if previous is not None and ts <= previous:
            raise ValueError('Duplicate or unsorted equity samples.')
        previous = ts
        op, high, low, close = map(positive, point[1:])
        if not low <= min(op, close) <= max(op, close) <= high:
            raise ValueError('Invalid OHLC candle.')
        samples[ts] = close
        cadence[ts.strftime('%H:%M:%S')] += 1
    # Keep source timestamp next to mapped session; never use as a decision input.
    rows = []
    for day in sessions:
        dt = date.fromisoformat(day)
        observed = datetime.combine(dt + timedelta(days=1), time.min, NY)
        if day == sessions[-1]:
            observed = datetime.combine(dt, time(16), NY)
        if observed not in samples:
            raise ValueError('Required next-midnight/terminal sample missing.')
        rows.append({'session': day, 'nav_usd': samples[observed],
                     'export_sample_utc': observed.astimezone(timezone.utc).isoformat(),
                     'mapping': 'terminal16NY' if day == sessions[-1] else 'next_midnight_NY_close'})
    result = compare_path(reference, rows)
    metrics = legacy_metrics(rows)
    if abs(metrics['end'] - positive(document['statistics']['End Equity'])) > .01:
        raise ValueError('Terminal equity mismatch.')
    orders = document['orders']
    status_codes, type_codes, symbols = Counter(), Counter(), Counter()
    identities = set()
    bad_order_ids = []
    for key, order in orders.items():
        ident = str(order['id'])
        if key != ident or ident in identities:
            raise ValueError('Duplicate or mismatched order identity.')
        identities.add(ident)
        created = stamp(order['createdTime'])
        if order.get('lastFillTime') and stamp(order['lastFillTime']) < created:
            raise ValueError('Fill before order creation.')
        qty = float(order['quantity'])
        if not math.isfinite(qty) or qty == 0:
            raise ValueError('Invalid order quantity.')
        positive(order['price'])
        status_codes[str(order['status'])] += 1
        type_codes[str(order['type'])] += 1
        symbols[order['symbol']['value']] += 1
        if created.date() < date(2020, 1, 1) or created.date() > date(2025, 12, 31):
            bad_order_ids.append(ident)
    if bad_order_ids:
        raise ValueError('Orders outside expected period.')
    if len(orders) != int(document['statistics']['Total Orders']):
        raise ValueError('Order count does not match export statistics.')
    # Store literal codes; meanings are not inferred from an unpinned enum.
    audit = {'status': 'aggregate_compatible_reference' if result['aggregate_match'] else 'mismatch_preserved',
             'identity': {'name': name, 'backtest_id': backtest_id},
             'sample_count': len(samples), 'sample_cadence_NY': dict(cadence),
             'calendar_hash': metrics['calendar_hash'], 'sessions': len(rows),
             'mapping': 'next NY midnight candle close; final session exact16:00 NY sample',
             'legacy_aggregate_comparison': result, 'metrics_legacy': metrics,
             'order_count': len(orders), 'status_code_counts': dict(status_codes),
             'type_code_counts': dict(type_codes), 'symbol_order_counts': dict(symbols),
             'cash_position_ledger_reconciled': False, 'original_daily_parity': False,
             'daily_decisions_available': False, 'new_financial_runs': 0}
    annual = []
    opening, anchor = 10000., '2019-12-31'
    for year in sorted({r['session'][:4] for r in rows}):
        subset = [r for r in rows if r['session'].startswith(year)]
        m = legacy_metrics(subset, opening, anchor)
        m.update(year=year, calendar_year_return=m['ret'], annual_calmar=m['ret']/abs(m['dd']) if m['dd'] < 0 else None)
        # Full-path Calmar uses CAGR; annual Calmar uses that year's simple return.
        annual.append(m)
        opening, anchor = subset[-1]['nav_usd'], subset[-1]['session']
    audit['annual_legacy'] = annual
    return audit, rows


def annual_calmar_rounding_bound(rows, opening, *, exact_opening=False):
    """Propagate half-unit USD1e-4 source rounding; no fitted error threshold.

    Upper-bound return numerator and drawdown errors, then ratio error. Uses the
    minimum observed positive NAV to conservatively cover every peak/trough pair.
    Only applicable to this declared four-decimal official chart profile.
    """
    epsilon = .00005
    minimum = min([float(opening)] + [float(r['nav_usd']) for r in rows])
    if minimum <= epsilon or opening <= epsilon:
        raise ValueError('NAV too small for declared quantization.')
    last = float(rows[-1]['nav_usd'])
    opening_error = 0. if exact_opening else epsilon
    return_error = epsilon/(opening-opening_error) + last*opening_error/(opening*(opening-opening_error))
    dd_error = 2*epsilon/(minimum-epsilon)
    peak = float(opening)
    depth = 0.
    for row in rows:
        nav = float(row['nav_usd'])
        peak = max(peak, nav)
        depth = max(depth, 1-nav/peak)
    if depth <= dd_error:
        return None
    annual_calmar = (last/opening-1)/depth
    return (return_error+abs(annual_calmar)*dd_error)/(depth-dd_error)
