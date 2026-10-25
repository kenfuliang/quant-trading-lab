"""Reconstruct saved decisions; attach future labels in a separate table.

No strategy execution, market access, model fitting or broker operations.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

METHOD = 'saved-gate-decision-outcomes-v1'
HORIZONS = (5, 21, 63)
TOL = 1e-10


def _dates(frame):
    idx = pd.DatetimeIndex(pd.to_datetime(frame.index))
    if idx.has_duplicates or not idx.is_monotonic_increasing or idx.hasnans:
        raise ValueError('Unique ordered valid dates required.')
    return idx


def validate_inputs(timeline, signal, gate, base, raw_close, capital):
    idx = _dates(signal)
    if not len(idx) or not np.isfinite(capital) or capital <= 0:
        raise ValueError('Nonempty history and positive finite capital required.')
    for frame in (timeline, gate, base):
        if not idx.equals(_dates(frame)):
            raise ValueError('All decision/account dates must match exactly.')
    raw_dates = _dates(raw_close)
    values = raw_close.to_numpy(float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError('Positive finite raw closes required.')
    for frame in (gate, base):
        values = frame[['equity_usd', 'shares', 'cash', 'close']].to_numpy(float)
        if (not np.isfinite(values).all() or (values[:, 0] <= 0).any()
                or (values[:, 1] < 0).any() or (values[:, 1] % 1 != 0).any()
                or (values[:, 3] <= 0).any()):
            raise ValueError('Invalid saved account fields.')
        np.testing.assert_allclose(frame.equity_usd, frame.cash + frame.shares * frame.close,
                                   atol=1e-7, rtol=0)
    targets = signal[['base_target', 'intended_target']].to_numpy(float)
    if (not np.isfinite(targets).all() or (targets < 0).any() or (targets > 1).any()
            or (targets[:, 1] > targets[:, 0] + TOL).any()):
        raise ValueError('Invalid long/cash capped targets.')
    if not timeline.state.isin(['green', 'yellow', 'red', 'unassessed']).all():
        raise ValueError('Unknown state.')
    if not np.isfinite(timeline[['fast', 'slow', 'vol', 'dd', 'cap']].to_numpy(float)).all():
        raise ValueError('Invalid decision features.')
    np.testing.assert_allclose(timeline[['base_target', 'intended_target']], targets, atol=TOL, rtol=0)
    expected_caps = timeline.state.map({'green': 1., 'yellow': .5, 'red': 0., 'unassessed': 0.})
    np.testing.assert_allclose(timeline.cap, expected_caps, atol=TOL, rtol=0)
    np.testing.assert_allclose(targets[:, 1], np.minimum(targets[:, 0], expected_caps), atol=TOL, rtol=0)
    loc = raw_dates.get_indexer(idx)
    if (loc < 1).any():
        raise ValueError('Each execution date needs a preceding source session.')
    observed = pd.DatetimeIndex(pd.to_datetime(timeline.observed_close))
    if not observed.equals(raw_dates[loc - 1]) or not (observed < idx).all():
        raise ValueError('Saved observation must be the preceding source close.')
    if not pd.DatetimeIndex(pd.to_datetime(timeline.execution_open)).equals(idx):
        raise ValueError('Saved execution-session identity changed.')
    np.testing.assert_allclose(signal.close, raw_close.to_numpy(float)[loc], atol=1e-9, rtol=0)
    np.testing.assert_allclose(gate.close, signal.close, atol=1e-9, rtol=0)
    np.testing.assert_allclose(base.close, signal.close, atol=1e-9, rtol=0)
    return idx, loc


def decision_log(timeline, signal, gate, base, raw_close, capital, pair_id, *, peak_enabled):
    """Inputs known at the modeled prior close; no same-day outcome columns."""
    idx, raw_loc = validate_inputs(timeline, signal, gate, base, raw_close, capital)
    bt = signal.base_target.to_numpy(float)
    gt = signal.intended_target.to_numpy(float)
    reducing = gt < bt - TOL
    warning = timeline.state.isin(['yellow', 'red']).to_numpy()
    prev_shares = np.r_[0, base.shares.to_numpy()[:-1]]
    prev_gate_shares = np.r_[0, gate.shares.to_numpy()[:-1]]
    prev_state = np.concatenate((['boundary_unknown'], timeline.state.to_numpy()[:-1]))
    raw = raw_close.to_numpy(float)
    prior_return = [float(raw[j-1] / raw[j-22] - 1) if j >= 22 else None for j in raw_loc]
    rows = []
    for i, date in enumerate(idx):
        t = timeline.iloc[i]
        dd = float(t.dd) if peak_enabled else 0.
        flags = []
        if t.vol >= .40: flags.append('volatility_red')
        if peak_enabled and dd < -.20: flags.append('price_peak_red')
        if t.fast <= t.slow: flags.append('trend_nonpositive')
        if t.vol >= .25: flags.append('volatility_yellow')
        if peak_enabled and dd <= -.10: flags.append('price_peak_yellow')
        # Trigger flags are not exclusive causes; memory can maintain state.
        if t.state in ('yellow', 'red'):
            flags.append('state_recurrence_and_confirmation_memory')
        if not flags: flags.append('no_current_warning_trigger')
        rows.append(dict(
            decision_id=f'{pair_id}:{date:%Y-%m-%d}', pair_id=pair_id,
            record_origin='reconstructed_from_saved_artifacts', method=METHOD,
            observed_close=str(t.observed_close), available_after='modeled_previous_regular_close',
            execution_session=f'{date:%Y-%m-%d}', state=t.state, previous_state=prev_state[i],
            fast_ema=float(t.fast), slow_ema=float(t.slow), sigma20=float(t.vol),
            raw_price_drawdown=float(t.dd), price_peak_component_enabled=peak_enabled,
            active_gate_drawdown_input=dd, red_count=int(t.red_count), green_count=int(t.green_count),
            state_cap=float(t.cap), base_target=bt[i], gate_target=gt[i],
            warning=bool(warning[i]), intended_reduction=bool(reducing[i]),
            reduction_episode_start=bool(reducing[i] and (i == 0 or not reducing[i-1])),
            warning_episode_start=bool(warning[i] and (i == 0 or not warning[i-1])),
            red_entry=bool(i > 0 and t.state == 'red' and prev_state[i] != 'red'),
            red_exit=bool(i > 0 and t.state != 'red' and prev_state[i] == 'red'),
            evaluation_boundary=bool(i == 0),
            prior_base_shares=int(prev_shares[i]), prior_gate_shares=int(prev_gate_shares[i]),
            prior_base_cash_usd=float(capital if i == 0 else base.cash.iloc[i-1]),
            prior_gate_cash_usd=float(capital if i == 0 else gate.cash.iloc[i-1]),
            base_intends_cash=bool(bt[i] == 0),
            warning_already_cash=bool(warning[i] and bt[i] == 0 and prev_shares[i] == 0),
            warning_base_exiting=bool(warning[i] and bt[i] == 0 and prev_shares[i] > 0),
            prior_spy_return_21=prior_return[i], trigger_flags='|'.join(flags)))
    return pd.DataFrame(rows)


def label_outcome(base_return, gate_return, *, actionable, already_cash, prior_return):
    if already_cash:
        return 'warning_already_cash_no_immediate_credit'
    if not actionable:
        return 'no_immediate_target_reduction'
    delta = gate_return - base_return
    if abs(delta) <= TOL:
        return 'no_material_relative_difference'
    if base_return < -TOL and delta > TOL:
        return 'helped_during_base_loss'
    if base_return > TOL and delta < -TOL:
        return ('missed_rebound' if prior_return is not None and pd.notna(prior_return)
                and prior_return < -TOL else 'missed_positive_base_move')
    if base_return < -TOL and delta < -TOL:
        return 'worsened_base_loss'
    if base_return > TOL and delta > TOL:
        return 'outperformed_positive_base'
    return 'mixed_near_flat_base'


def outcome_labels(decisions, gate_equity, base_equity, capital, horizons=HORIZONS):
    """Realized continuation-policy labels; no same-capital isolated intervention."""
    n = len(decisions)
    g = np.asarray(gate_equity, float); b = np.asarray(base_equity, float)
    if (len(g) != n or len(b) != n or not np.isfinite(capital) or capital <= 0
            or not np.isfinite(g).all() or not np.isfinite(b).all()
            or (g <= 0).any() or (b <= 0).any()):
        raise ValueError('Aligned positive finite account paths required.')
    if not horizons or any(type(h) is not int or h < 1 for h in horizons) or len(set(horizons)) != len(horizons):
        raise ValueError('Unique positive integer horizons required.')
    records = []
    for i, row in enumerate(decisions.to_dict('records')):
        for h in horizons:
            end = i + h - 1
            censored = end >= n
            gr = None if censored else float(g[end] / (capital if i == 0 else g[i-1]) - 1)
            br = None if censored else float(b[end] / (capital if i == 0 else b[i-1]) - 1)
            records.append(dict(
                decision_id=row['decision_id'], execution_session=row['execution_session'],
                horizon_sessions=h, right_censored=censored,
                label_available_after_close=None if censored else decisions.execution_session.iloc[end],
                gate_return=gr, base_return=br, gate_minus_base_pp=None if censored else (gr-br)*100,
                label='right_censored' if censored else label_outcome(br, gr,
                    actionable=row['intended_reduction'], already_cash=row['warning_already_cash'],
                    prior_return=row['prior_spy_return_21'])))
    return pd.DataFrame(records)


def summarize(decisions, outcomes):
    """Episode anchored means/counts, not sums of overlapping returns."""
    joined = outcomes.merge(decisions, on=['decision_id', 'execution_session'], validate='many_to_one')
    summaries = []
    for event in ('reduction_episode_start', 'warning_episode_start', 'red_entry', 'red_exit', 'warning_already_cash'):
        anchors = np.flatnonzero(decisions[event].to_numpy() & ~decisions.evaluation_boundary.to_numpy())
        for h in sorted(outcomes.horizon_sessions.unique()):
            rows = joined[joined[event] & ~joined.evaluation_boundary & (joined.horizon_sessions == h)]
            valid = rows[~rows.right_censored]
            summaries.append(dict(event=event, horizon_sessions=int(h), anchors=len(rows),
                evaluable=len(valid), right_censored=int(rows.right_censored.sum()),
                adjacent_overlapping_windows=int(np.sum(np.diff(anchors) < h)),
                mean_gate_return_pct=None if valid.empty else float(valid.gate_return.mean()*100),
                mean_base_return_pct=None if valid.empty else float(valid.base_return.mean()*100),
                mean_gate_minus_base_pp=None if valid.empty else float(valid.gate_minus_base_pp.mean()),
                label_counts={str(k):int(v) for k,v in valid.label.value_counts().items()}))
    daily = dict(sessions=len(decisions), warning_sessions=int(decisions.warning.sum()),
                 intended_reduction_sessions=int(decisions.intended_reduction.sum()),
                 warning_already_cash_sessions=int(decisions.warning_already_cash.sum()),
                 warning_base_exiting_sessions=int(decisions.warning_base_exiting.sum()),
                 boundary_anchors_excluded=int(decisions.evaluation_boundary.sum()))
    return daily, summaries, joined
