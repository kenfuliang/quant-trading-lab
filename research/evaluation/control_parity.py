"""Explicit schema-aware comparison against historical daily sizing controls."""
import pandas as pd


def compare(oldcurve, newcurve, oldtrades, newtrades):
    """Only the documented added constant-1 target diagnostic may be absent."""
    pd.testing.assert_frame_equal(oldtrades,newtrades,check_exact=True)
    oldset,newset=set(oldcurve),set(newcurve)
    if oldset==newset:
        expected=newcurve
    elif newset-oldset=={'effective_target_leverage'} and not oldset-newset:
        if not newcurve.effective_target_leverage.eq(1.).all():
            raise AssertionError('Legacy full-target control requires constant nominal 1x diagnostic.')
        expected=newcurve[oldcurve.columns]
    else:
        raise AssertionError('Unexpected control schema difference; do not drop arbitrary fields.')
    pd.testing.assert_frame_equal(oldcurve,expected,check_exact=False,rtol=0,atol=1e-7)
    return dict(passed=True,trade_exact=True,ledger_atol_usd=1e-7,
                historical_columns=len(oldcurve.columns),current_columns=len(newcurve.columns),
                derived_diagnostic_columns=sorted(newset-oldset))
