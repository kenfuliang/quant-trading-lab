"""Narrow, read-only compatibility audit for the known EMA diagnostic transition.

This helper does not change saved outputs or override a frozen experiment gate.
Its future use requires an explicit new plan/adapter version.
"""
import numpy as np
import pandas as pd


def compare_ema_diagnostic(oldcurve,newcurve,oldtrades,newtrades,signal):
    if not oldcurve.index.equals(newcurve.index) or not newcurve.index.equals(signal.index):
        raise ValueError('Exact date alignment required')
    if list(oldcurve.columns)!=list(newcurve.columns):
        raise ValueError('Unexpected schema change')
    key='effective_target_leverage'
    if key not in oldcurve or not {'want_long','intended_target'}.issubset(signal):
        raise ValueError('Known EMA diagnostic and causal eligibility required')
    oldvalues=oldcurve[key].to_numpy(float);newvalues=newcurve[key].to_numpy(float)
    target=signal.intended_target.to_numpy(float);eligibility=signal.want_long.to_numpy(bool).astype(float)
    if not all(np.isfinite(v).all() for v in [oldvalues,newvalues,target]) or not np.array_equal(target,eligibility):
        raise ValueError('Only whole-budget EMA0/1 eligibility is supported')
    if not np.array_equal(oldvalues,target) or not np.equal(newvalues,1.).all():
        raise ValueError('Unrecognized diagnostic semantics')
    # Compare every other field, not only PnL: dates, shares, marks, fees, margin state, etc.
    columns=[c for c in oldcurve if c!=key]
    pd.testing.assert_frame_equal(oldcurve[columns],newcurve[columns],rtol=0,atol=1e-7)
    pd.testing.assert_frame_equal(oldtrades,newtrades,check_exact=True)
    return dict(passed=True,trade_exact=True,all_other_fields_atol=1e-7,only_translated_field=key,
        legacy_semantics='effective EMA0/1 target',current_semantics='nominal1budget',
        mismatch_sessions=int(np.count_nonzero(oldvalues!=newvalues)),frozen_gate_overridden=False)
