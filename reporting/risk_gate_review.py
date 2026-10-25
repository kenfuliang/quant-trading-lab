"""Saved-evidence diagnostics only; no simulator, services or broker calls."""
import math
import numpy as np
import pandas as pd

def verify_temporal_details(eq, summary):
    a = np.asarray(eq, float)
    dd = a / np.maximum.accumulate(a) - 1
    underwater = dd < 0
    starts = np.flatnonzero(underwater & ~np.r_[False, underwater[:-1]])
    ends = np.flatnonzero(underwater & ~np.r_[underwater[1:], False])
    if not len(starts) == len(ends) == len(summary['drawdown_episodes']):
        raise AssertionError('Saved evidence verification failed')
    checks = 0
    for (start, last, saved) in zip(starts, ends, summary['drawdown_episodes'], strict=True):
        peak = start - 1
        recovered = last < len(a) - 1
        end = last + 1 if recovered else last
        trough = start + int(np.argmin(a[start:last + 1]))
        date = lambda i: pd.Timestamp(eq.index[i]).isoformat()
        expected = dict(peak_date=date(peak), trough_date=date(trough), recovery_date=date(end) if recovered else None, observed_end_date=date(end), duration_sessions=int(end - peak), underwater_sessions=int(last - start + 1), duration_calendar_days=int((eq.index[end] - eq.index[peak]).days), right_censored=not recovered)
        for (key, value) in expected.items():
            if not saved[key] == value:
                raise AssertionError((key, saved[key], value))
        if not abs(saved['drawdown'] - (a[trough] / a[peak] - 1)) < 1e-12:
            raise AssertionError('Saved evidence verification failed')
        checks += len(expected) + 1
    es = summary['historical_daily_es95']
    r = a[1:] / a[:-1] - 1
    k = math.ceil(0.05 * len(r))
    tail = np.sort(r)[:k]
    if not (es['sample_count'] == len(r) and es['tail_count'] == k and (es['actual_tail_fraction'] == k / len(r))):
        raise AssertionError('Saved evidence verification failed')
    if not (abs(es['threshold_return'] - tail[-1]) < 1e-12 and abs(es['loss_magnitude'] + tail.mean()) < 1e-12):
        raise AssertionError('Saved evidence verification failed')
    if not abs(summary['max_drawdown'] - dd.min()) < 1e-12:
        raise AssertionError('Saved evidence verification failed')
    return dict(passed=True, episode_field_checks=checks, episodes=len(starts), tail_and_drawdown_checks=6)

def verify_events(result, time, frame, gate, base, hold, capital):
    colors = time.state.to_numpy()
    n = len(frame)
    starts = []
    if colors[0] in ('red', 'yellow'):
        starts.append((0, True))
    starts.extend(((i, False) for i in range(1, n) if colors[i - 1] == 'green' and colors[i] in ('red', 'yellow')))
    if not len(starts) == len(result['warnings']):
        raise AssertionError('Saved evidence verification failed')
    checks = 0
    for ((i, left), w) in zip(starts, result['warnings'], strict=True):
        ends = [j for j in range(i + 1, n) if colors[j] == 'green']
        end = ends[0] if ends else n
        if not (w['start'] == frame.index[i] and w['left_censored'] == left):
            raise AssertionError('Saved evidence verification failed')
        if not w['end'] == (None if end == n else frame.index[end]):
            raise AssertionError('Saved evidence verification failed')
        acts = [j for j in range(i, end) if frame.intended_target.iloc[j] < frame.base_target.iloc[j]]
        if not w['actionable_index'] == (acts[0] if acts else None):
            raise AssertionError('Saved evidence verification failed')
        for (prefix, j) in (('warning', i), ('actionable', acts[0] if acts else None)):
            if j is None or j + 21 > n:
                if not w[prefix + '_price_drop_5pct'] is None:
                    raise AssertionError('Saved evidence verification failed')
            else:
                hits = [k - j for k in range(j, j + 21) if frame.close.iloc[k] / frame.open.iloc[j] <= 0.95]
                if not w[prefix + '_price_drop_5pct'] == bool(hits):
                    raise AssertionError('Saved evidence verification failed')
                if not w[prefix + '_first_drop_offset_sessions'] == (hits[0] if hits else None):
                    raise AssertionError('Saved evidence verification failed')
            checks += 2
    expected = [(frame.index[i], 'red_entry' if colors[i] == 'red' else 'red_exit', h) for i in range(1, n) if colors[i] != colors[i - 1] and (colors[i] == 'red' or colors[i - 1] == 'red') for h in (5, 21, 63)]
    if not expected == [(w['date'], w['event'], w['horizon']) for w in result['red_windows']]:
        raise AssertionError('Saved evidence verification failed')
    for w in result['red_windows']:
        i = frame.index.get_loc(w['date'])
        h = w['horizon']
        if not w['right_censored'] == (i + h > n):
            raise AssertionError('Saved evidence verification failed')
        for (name, account) in (('gate', gate), ('base', base), ('hold', hold)):
            expected_return = None if i + h > n else float(account.equity_usd.iloc[i + h - 1] / (capital if i == 0 else account.equity_usd.iloc[i - 1]) - 1)
            if not w[name + '_return'] == expected_return:
                raise AssertionError('Saved evidence verification failed')
            checks += 1
        if not w['right_censored']:
            if not abs(w['base_minus_gate'] - (w['base_return'] - w['gate_return'])) < 1e-12:
                raise AssertionError('Saved evidence verification failed')
            if not abs(w['hold_minus_gate'] - (w['hold_return'] - w['gate_return'])) < 1e-12:
                raise AssertionError('Saved evidence verification failed')
    return dict(passed=True, warning_episodes=len(starts), event_window_rows=len(expected), field_checks=checks)

def paired_verdict(gate, base, tolerance=1e-10):
    depth = abs(gate['drawdown_pct']) / 100
    other = abs(base['drawdown_pct']) / 100
    duration = gate['longest_underwater_sessions']
    other_duration = base['longest_underwater_sessions']
    passed = depth <= other + tolerance and duration <= other_duration and (depth < other - tolerance or duration < other_duration)
    return dict(path_criterion_pass=passed, drawdown_reduction_pp=(other - depth) * 100, underwater_change_sessions=duration - other_duration, cagr_change_pp=gate['cagr_pct'] - base['cagr_pct'], ending_equity_change_usd=gate['ending_equity_usd'] - base['ending_equity_usd'], gate_censored=gate['longest_censored'], base_censored=base['longest_censored'])
