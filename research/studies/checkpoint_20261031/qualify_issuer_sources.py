"""Read-only source reconciliation checkpoint; never grants missing price rights."""
import json
from pathlib import Path

import pandas as pd

from research.studies.checkpoint_20261031.issuer_actions import ssga_spy, ishares_ief
from research.evaluation.etf_input_audit import audit_chart
from research.studies.checkpoint_20261031.us_etf_calendar import sessions, clocks
from research.studies.checkpoint_20261031.free_source_fetch import STATE
from research.evaluation.saved_review import verify_artifacts, digest


def main():
    base = STATE.parent
    state = json.loads(STATE.read_text())
    for source in state['requests']:
        if source['status'] == 'received' and digest(source['path']) != source['sha256']:
            raise ValueError('Acquired artifact identity changed.')
    actions = ssga_spy(base/'sources/03-ssga-historical-distributions.bin') + ishares_ief(base/'sources/02-ishares-ief-page.bin')
    actions = sorted([r for r in actions if '2004-12-01' <= r['ex_date'] <= '2025-12-31'],key=lambda row:(row['ex_date'],row['symbol']))
    joins = []
    prior = json.loads(Path('.local/etf-readiness/state.json').read_text())
    for request in prior['snapshot_requests']:
        if digest(request['path']) != request['sha256']:
            raise ValueError('Prior price snapshot changed.')
        payload = json.loads(Path(request['path']).read_text())
        receipt, frame = audit_chart(payload,request['symbol'])
        expected = sessions(frame.index[0],frame.index[-1])
        if not frame.index.equals(expected):
            raise ValueError('Price/calendar date mismatch.')
        events = payload['chart']['result'][0].get('events',{}).get('dividends',{})
        provider = {pd.Timestamp(e['date'],unit='s',tz='UTC').tz_convert('America/New_York').strftime('%Y-%m-%d'):e['amount'] for e in events.values()}
        official = {a['ex_date']:a for a in actions if a['symbol'] == request['symbol']}
        if set(provider) != set(official):
            raise ValueError('Issuer/provider action date mismatch.')
        differences = [dict(ex_date=day,issuer_amount=official[day]['amount'],provider_amount=provider[day],
                            delta_per_share=float(official[day]['amount'])-provider[day]) for day in official
                       if abs(float(official[day]['amount'])-provider[day])>1e-8]
        joins.append(dict(symbol=request['symbol'],issuer_action_count=len(official),provider_action_count=len(provider),
                          action_dates_match=True,calendar_sessions=len(expected),calendar_dates_match=True,
                          reported_splits=receipt['reported_split_count'],price_use_permission='not established',
                          precision_and_value_differences=differences))
    fixture = pd.read_csv(base/'sources/06-xnys-calendar-fixture.bin')
    dates = pd.to_datetime(fixture.iloc[:,0],utc=True).dt.tz_localize(None)
    selected = fixture.loc[(dates>='2004-01-01') & (dates<='2023-01-13')]
    idx = pd.DatetimeIndex(dates.loc[selected.index])
    if not idx.equals(sessions(idx[0],idx[-1])):
        raise ValueError('Independent maintainer calendar fixture mismatch.')
    for day,opening,closing in zip(idx,pd.to_datetime(selected.open,utc=True),pd.to_datetime(selected.close,utc=True),strict=True):
        if clocks(day) != (opening,closing):
            raise ValueError('Independent session-clock mismatch.')
    out = base/'source-checkpoint'
    out.mkdir(exist_ok=False)
    (out/'issuer-actions.json').write_text(json.dumps(actions,indent=2)+'\n')
    report = dict(status='data_and_accounting_progress_price_permission_pending',historical_financial_attempts=0,
                  source_requests=len(state['requests']),provider_domains=sorted({__import__('urllib.parse',fromlist=['urlsplit']).urlsplit(r['url']).hostname for r in state['requests']}),
                  issuer_distribution_actions=len(actions),input_joins=joins,
                  calendar=dict(independent_fixture_sessions=len(idx),independent_open_close_clock_matches=len(idx),
                                rule_scope='2004–2025; fixture through2023-01-13 plus source-rule extension; not venue certification',
                                license='Apache-2.0 source snapshot retained',dataset_vintage='Retrieved2026; not original historical publication vintages'),
                  native_checks={name:verify_artifacts(base/name) for name in ('accounting-rotation','accounting-terminal')},
                  source_limitations=dict(yahoo_general_terms='Saved terms restrict automated collection without prior permission; authorization for anonymous price snapshots is not established',
                                          finance_specific_page='Retrieved page is Finance Community terms; not a historical-price license',
                                          stooq='JavaScript browser verification page; not market data; no challenge executed',
                                          action_values='New issuer-primary source; historical provider disagreements preserved; no old input overwritten'),
                  remaining_for_financial_launch=['Permission-qualified raw ETF price input and reviewed source/adjustment/no-split qualification',
                      'Assemble reviewed normalized bundle and freeze executable code/inputs/criterion',
                      'Reserve and run the ten financial paths; independently audit all results'])
    (out/'review.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'manifest.json').write_text(json.dumps(dict(artifact_hashes={p.name:digest(p) for p in out.iterdir() if p.is_file()}),indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','issuer_distribution_actions','calendar','remaining_for_financial_launch')},indent=2))


if __name__ == '__main__':
    main()
