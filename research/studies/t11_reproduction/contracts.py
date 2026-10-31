"""Project-owned evidence contracts, not a copy or port of the third-party policy."""
from datetime import date,datetime
from decimal import Decimal as D
import hashlib
from zoneinfo import ZoneInfo


def number(value):
    result=D(str(value))
    if not result.is_finite():raise ValueError('Nonfinite financial field.')
    return result


def utc(value):
    stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
    if stamp.utcoffset() is None:raise ValueError('Explicit timezone required.')
    return stamp


def decision(record,calendar):
    """Validate a proposed record; raw vendor features require separate data rights.

    Date labels are economic sessions; all observation/availability/decision/fill
    timestamps are timezone-aware. Red may still have pending reductions: the
    faithful controller is staged, not the instantaneous sector liquidation model.
    """
    dates=list(calendar)
    if dates!=sorted(set(dates)):raise ValueError('Calendar must be unique and sorted.')
    day=record['session'];date.fromisoformat(day)
    if day not in dates or dates.index(day)==len(dates)-1:raise ValueError('Decision needs an actual next execution session.')
    observed,available,decided=map(utc,[record['observed_through_utc'],record['available_at_utc'],record['decision_at_utc']])
    if not observed<=available<=decided:raise ValueError('Future/unavailable input at decision.')
    if observed.astimezone(ZoneInfo('America/New_York')).date().isoformat()!=day:raise ValueError('Observed timestamp and economic session disagree.')
    next_open=datetime.combine(date.fromisoformat(record['earliest_execution_session']),datetime.min.time().replace(hour=9,minute=30),ZoneInfo('America/New_York'))
    if decided>=next_open:raise ValueError('Decision unavailable before intended execution open.')
    if record['input_session']!=day:raise ValueError('Decision must identify its completed input session.')
    if record['earliest_execution_session']!=dates[dates.index(day)+1]:raise ValueError('Execution must be the next actual trading session.')
    caps={'green':D(1),'yellow':D('.5'),'red':D(0),'unassessed':D(0)}
    cap=number(record['cap'])
    if record['state'] not in caps or cap!=caps[record['state']]:raise ValueError('State/cap mismatch.')
    if record['controller_phase'] not in ('idle','reduce_pending','buy_eligible','buy_pending','complete'):raise ValueError('Unknown staged phase.')
    base={s:number(w) for s,w in record['base_weights'].items()};target={s:number(w) for s,w in record['target_weights'].items()}
    if any(w<0 for w in [*base.values(),*target.values()]) or sum(base.values(),D(0))>1:raise ValueError('Invalid long-only policy budget.')
    expected={s:w*cap*D('.9') for s,w in base.items() if w*cap}
    if {s:w for s,w in target.items() if w}!=expected:raise ValueError('Target changed beyond the frozen gate and90percent allocation.')
    if record['positions']!= {s:int(q) for s,q in record['positions'].items()} or any(q<0 for q in record['positions'].values()):raise ValueError('Invalid whole long share positions.')
    if not isinstance(record['pending_order_ids'],list) or len(record['pending_order_ids'])!=len(set(record['pending_order_ids'])):raise ValueError('Invalid pending order identity.')
    for key in ('policy_source_sha256','input_identity_sha256'):
        h=record[key]
        if not isinstance(h,str) or len(h)!=64 or any(c not in '0123456789abcdef' for c in h):raise ValueError('Frozen identity required.')
    return {'status':'contract_valid','policy_or_account_parity_proven':False}


def funding(previous_cash,previous_session,session):
    """Frozen legacy debt charge: 6percent ACT/360; do not round to cents here."""
    days=(date.fromisoformat(session)-date.fromisoformat(previous_session)).days
    if days<=0:raise ValueError('Funding dates must increase.')
    return max(-number(previous_cash),D(0))*D('.06')*D(days)/D(360)


def nav_check(record,tolerance='0.000001'):
    """Read saved closing states only; this is not a simulator or margin model."""
    cash=number(record['cash_usd']);receivables=number(record['receivables_usd']);nav=number(record['nav_usd'])
    if receivables<0 or nav<=0:raise ValueError('Invalid closing NAV/receivables.')
    positions=record['positions'];marks=record['marks_usd']
    if set(positions)-set(marks):raise ValueError('Missing position marks.')
    for q in positions.values():
        v=number(q)
        if v<0 or v!=int(v):raise ValueError('Non-whole or short position.')
    if any(number(x)<=0 for x in marks.values()):raise ValueError('Invalid mark.')
    expected=cash+receivables+sum((number(q)*number(marks[s]) for s,q in positions.items()),D(0))
    residual=nav-expected
    if abs(residual)>number(tolerance):raise ValueError('NAV does not reconcile.')
    return {'status':'closing_identity_valid','residual_usd':str(residual),'cash_transitions_or_margin_proven':False}
