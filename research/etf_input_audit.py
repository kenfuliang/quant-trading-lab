"""Strict anonymous chart snapshot audit; never fetches or repairs market data."""
import hashlib,json,math
from pathlib import Path
import numpy as np
import pandas as pd

INCEPTIONS={'SPY':'1993-01-22','IEF':'2002-07-22','GLD':'2004-11-18'}
ISSUERS={'SPY':'https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy',
         'IEF':'https://www.ishares.com/us/products/239456/ishares-710-year-treasury-bond-etf',
         'GLD':'https://www.spdrgoldshares.com/usa/gld/'}


def audit_chart(payload,symbol,start='2004-12-01',end='2025-12-31'):
    chart=payload['chart']
    if chart.get('error') or len(chart['result'])!=1:raise ValueError('Invalid provider response.')
    result=chart['result'][0];meta=result['meta']
    if meta.get('symbol')!=symbol or meta.get('currency')!='USD' or meta.get('instrumentType')!='ETF' or meta.get('exchangeTimezoneName')!='America/New_York' or meta.get('dataGranularity')!='1d':
        raise ValueError('Instrument/currency/timezone/granularity identity mismatch.')
    timestamps=result['timestamp']
    if any(type(t) is not int for t in timestamps):raise ValueError('Timestamps must be integer seconds.')
    times=pd.to_datetime(timestamps,unit='s',utc=True).tz_convert('America/New_York')
    dates=times.tz_localize(None).normalize()
    if not len(dates) or dates.has_duplicates or not dates.is_monotonic_increasing:raise ValueError('Invalid/duplicated session dates.')
    if dates.min()<pd.Timestamp(INCEPTIONS[symbol]) or dates.min()<pd.Timestamp(start) or dates.max()>pd.Timestamp(end):raise ValueError('Pre-inception or out-of-scope observations.')
    if (dates.dayofweek>=5).any():raise ValueError('Weekend rows are not regular US ETF sessions.')
    quote=result['indicators']['quote'][0]
    frame=pd.DataFrame(quote,index=dates)[['open','high','low','close','volume']]
    values=frame.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (frame[['open','high','low','close']]<=0).any().any() or (frame.volume<0).any():raise ValueError('Invalid/nonfinite OHLCV.')
    if (frame.high<frame[['open','low','close']].max(axis=1)).any() or (frame.low>frame[['open','high','close']].min(axis=1)).any():raise ValueError('OHLC envelope failure.')
    adjusted=np.asarray(result['indicators']['adjclose'][0]['adjclose'],dtype=float)
    if len(adjusted)!=len(frame) or not np.isfinite(adjusted).all() or (adjusted<=0).any():raise ValueError('Invalid adjusted-close field.')
    events=result.get('events',{});dividends=events.get('dividends',{});splits=events.get('splits',{})
    fields=set();unmatched=[];date_labels=[]
    for event in dividends.values():
        fields.update(event)
        if not math.isfinite(event['amount']) or event['amount']<=0:raise ValueError('Invalid distribution amount.')
        day=pd.Timestamp(event['date'],unit='s',tz='UTC').tz_convert('America/New_York').date()
        if pd.Timestamp(day) not in dates:unmatched.append(str(day))
        date_labels.append(str(day))
    if unmatched:raise ValueError('Distribution date not joined to an observed session.')
    for event in splits.values():
        if not all(k in event for k in ('date','numerator','denominator')) or event['numerator']<=0 or event['denominator']<=0:raise ValueError('Invalid split event.')
        day=pd.Timestamp(event['date'],unit='s',tz='UTC').tz_convert('America/New_York').tz_localize(None).normalize()
        if day not in dates:raise ValueError('Split date not joined to an observed session.')
    warmup=frame.loc[:'2005-12-31'];months=warmup.groupby(warmup.index.to_period('M')).tail(1)
    receipt=dict(symbol=symbol,checks_status='basic_structure_passed_primary_study_blocked',rows=len(frame),first_date=str(dates[0].date()),last_date=str(dates[-1].date()),
        currency=meta['currency'],timezone=meta['exchangeTimezoneName'],provider_exchange_code=meta.get('exchangeName'),inception_lower_bound=INCEPTIONS[symbol],inception_source=ISSUERS[symbol],
        identity_pass=True,sorted_unique_dates_pass=True,finite_positive_price_and_volume_checks_pass=True,ohlc_envelope_pass=True,weekend_rejection_pass=True,
        no_pre_inception_rows_pass=True,adjusted_close_present=True,adjusted_close_is_not_execution_price=True,
        reported_dividend_count=len(dividends),reported_split_count=len(splits),dividend_fields=sorted(fields),event_session_joins_pass=True,
        payment_dates_present=any(k.lower() in ('paydate','paymentdate','payment_date') for k in fields),
        observed_warmup_month_ends=len(months),ten_month_warmup_observed=len(months)>=10,
        raw_price_adjustment_semantics='unverified: field names/events alone do not certify treatment of splits/distributions',
        corporate_action_completeness='unverified: empty or matching provider event lists are not independent certification',
        session_calendar_completeness='unverified: matching observed rows is not a venue calendar',
        point_in_time_availability='unverified: timestamp labels are not proof of historical publication/availability',
        rights='unverified: anonymousHTTP200 is not data-use or redistribution permission',
        dividend_cash_availability='blocked: dated amounts do not establish payment-date cash; GLD reportednone is not blanket source certification',
        evaluation_class='viewed/publicly studied development history, not untouched evaluation')
    return receipt,frame


def main():
    state_path=Path('.local/etf-readiness/state.json');s=json.loads(state_path.read_text());out=Path('.local/etf-readiness/input-audit');out.mkdir(exist_ok=False)
    receipts=[];frames={}
    for request in s['snapshot_requests']:
        if request['status']!='received':continue
        source=Path(request['path']);actual=hashlib.sha256(source.read_bytes()).hexdigest()
        if actual!=request['sha256']:raise ValueError('Raw snapshot changed after acquisition.')
        receipt,frame=audit_chart(json.loads(source.read_text()),request['symbol'])
        receipt.update(source=str(source),sha256=actual,request_url=request['url'])
        frame.to_csv(out/(request['symbol']+'-observed-raw-fields.csv'),index_label='date')
        (out/(request['symbol']+'-receipt.json')).write_text(json.dumps(receipt,indent=2)+'\n');receipts.append(receipt);frames[request['symbol']]=frame
    common=frames['SPY'].index
    equal=all(frame.index.equals(common) for frame in frames.values())
    report=dict(status='not_ready',instruments=receipts,common_observed_dates_equal=equal,common_observed_rows=len(common),
        common_date_alignment_is_not_calendar_certification=True,
        provider_review=[dict(provider='Yahoo Finance',snapshot_requests=len(s['snapshot_requests']),anonymous_access='HTTP200 for3snapshots',
                              official_terms_fetch='tool returned999',official_adjustment_help_fetch='tool returned429',contract_status='unverified'),
                         dict(provider='Stooq',snapshot_requests=0,official_page='https://stooq.com/db/h/',access='browser verification required; no bypass attempted',adjustments_rights_actions='unverified')],
        provider_count=2,financial_simulations=0,
        blockers=['Verified dividend pay dates and payment-cash convention','Documented raw/adjusted price/action semantics and event completeness',
                  'Independent venue session-calendar completeness and availability','Data-use/redistribution rights for intended scope'])
    (out/'source-readiness.json').write_text(json.dumps(report,indent=2)+'\n')
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}
    (out/'manifest.json').write_text(json.dumps(dict(artifact_hashes=hashes),indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],rows={r['symbol']:r['rows'] for r in receipts},common_observed_dates_equal=equal,blockers=report['blockers']),indent=2))

if __name__=='__main__':main()
