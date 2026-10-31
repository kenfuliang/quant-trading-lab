"""Epoch3 fork: independent Fraction policy/account and correlation/breadth replay.

Deliberately imports neither ActionLedger nor the runner, selectors or feature code.
"""
import csv
from collections import defaultdict
from datetime import date
from fractions import Fraction as F
import json
import math
from pathlib import Path
import statistics
import numpy as np

SYMS=('XLB','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY','SPY')
SECTORS=SYMS[:-1]

def cent(value):
    value=F(value)*100;q,r=divmod(value.numerator,value.denominator)
    if 2*r>value.denominator or (2*r==value.denominator and q%2):q+=1
    return F(q,100)

def readcsv(path):
    with Path(path).open() as f:return list(csv.DictReader(f))

def near(actual,expected,label,tolerance=1e-8):
    if expected is None:
        if actual is not None and str(actual).lower()!='nan':raise AssertionError('Undefined metric manufactured: '+label)
    elif not math.isfinite(float(actual)) or abs(float(actual)-float(expected))>tolerance:
        raise AssertionError('Independent metric mismatch: '+label)

def ratio(values):
    sd=statistics.stdev(values) if len(values)>1 else 0
    return statistics.mean(values)/sd*math.sqrt(252) if sd>1e-15 else None

def path_statistics(values,dates):
    peak=values[0];latest_peak=0;begin=None;episodes=[];minimum=0.;underwater=0
    for i,v in enumerate(values):
        if v>=peak:
            if begin is not None:
                episodes.append({'start':begin,'stop':i,'duration':i-begin,'days':(date.fromisoformat(dates[i])-date.fromisoformat(dates[begin])).days,'censored':False})
                begin=None
            peak=v;latest_peak=i
        else:
            underwater+=1;minimum=min(minimum,v/peak-1)
            if begin is None:begin=latest_peak
        if i==len(values)-1 and begin is not None:
            episodes.append({'start':begin,'stop':i,'duration':i-begin,'days':(date.fromisoformat(dates[i])-date.fromisoformat(dates[begin])).days,'censored':True})
    longest=max(episodes,key=lambda e:(e['duration'],e['days'])) if episodes else None
    return {'dd_pct':minimum*100,'uw_sessions':longest['duration'] if longest else 0,'uw_days':longest['days'] if longest else 0,
            'underwater_fraction':underwater/(len(values)-1),'censored':longest['censored'] if longest else False,'episodes':episodes}


def independent_gate(closes):
    fast=slow=None;state='unassessed';count=0;rows=[];returns=[]
    for i,price in enumerate(closes):
        fast=price if fast is None else (2/51)*price+(49/51)*fast
        slow=price if slow is None else (2/201)*price+(199/201)*slow
        if i:returns.append(price/closes[i-1]-1)
        vol=statistics.stdev(returns[-20:])*math.sqrt(252) if i>=20 else None
        if i<199:state='unassessed';count=0
        elif vol>=.40:state='red';count=0
        elif state=='red':
            count=count+1 if vol<.35 else 0
            if count==5:state='yellow';count=0
        else:
            if state=='unassessed':state='yellow';count=0
            if state=='green' and (fast<=slow or vol>=.25):state='yellow';count=0
            if state=='yellow':
                count=count+1 if fast>slow and vol<.20 else 0
                if count==5:state='green';count=0
        provisional='unassessed' if i<199 else 'red' if vol>=.40 else 'yellow' if fast<=slow or vol>=.25 else 'green'
        rows.append(dict(fast=fast if i>=49 else None,slow=slow if i>=199 else None,vol=vol,state=state,
            provisional=provisional,cap={'unassessed':F(0),'red':F(0),'yellow':F(1,2),'green':F(1)}[state],
            red_count=count if state=='red' else 0,green_count=count if state=='yellow' else 0))
    return rows



def independent_breadth(features,dates):
    state='unassessed';recovery=confirmation=0;rows=[]
    for i,day in enumerate(dates):
        if i<199:
            value=None;state='unassessed';provisional='unassessed';recovery=confirmation=0
        else:
            value=sum(features[s][i]>statistics.mean(features[s][i-199:i+1]) for s in SECTORS)/10
            provisional='red' if value<=.2 else 'yellow' if value<.6 else 'green'
            if state=='unassessed':state='yellow'
            if value<=.2:state='red';recovery=confirmation=0
            elif state=='red':
                recovery=recovery+1 if value>=.4 else 0;confirmation=0
                if recovery>=5:state='yellow';recovery=0
            else:
                if state=='green' and value<.6:state='yellow';confirmation=0
                if state=='yellow':
                    confirmation=confirmation+1 if value>=.7 else 0
                    if confirmation>=5:state='green';confirmation=0
        rows.append(dict(breadth=value,state=state,provisional=provisional,red_count=recovery,green_count=confirmation,
                         cap={'unassessed':F(0),'red':F(0),'yellow':F(1,2),'green':F(1)}[state]))
    return rows


def replay(bundle_path,output,policy,bps,*,start='2017-02-01',end='2025-12-31'):
    output=Path(output);bundle=json.loads(Path(bundle_path).read_text())
    source=json.loads(Path(bundle['files']['prices']['path']).read_text())
    actions_doc=json.loads(Path(bundle['files']['actions']['path']).read_text())
    actions=actions_doc['cash_and_in_kind']+actions_doc['splits']
    prices={(r['symbol'],r['session']):{k:F(r[k]) for k in ('o','c')} for r in source}
    dates=sorted({r['session'] for r in source if r['symbol']=='SPY'})
    first=dates.index(start);last=dates.index(end);eval_dates=dates[first:last+1]
    # Independent float multiplication of elementary economic factors, no shared TRI.
    features={s:[100.] for s in SYMS};events_by=defaultdict(list)
    for a in actions:events_by[a['ex_date']].append(a)
    for i in range(1,len(dates)):
        day=dates[i]
        for s in SYMS:
            split=1.;distribution=0.;child=0.
            for a in events_by[day]:
                if a['symbol']!=s:continue
                if a['kind']=='split':split*=float(a['ratio'])
                elif a['kind']=='cash':distribution+=float(a['amount'])
                elif a['kind']=='in_kind':child+=float(a['ratio'])*float(prices[(a['child_symbol'],day)]['c'])
                else:raise AssertionError('Unknown input action.')
            factor=(split*(float(prices[(s,day)]['c'])+distribution)+child)/float(prices[(s,dates[i-1])]['c'])
            features[s].append(features[s][-1]*factor)
    gate=independent_breadth(features,dates) if policy=='breadth' else independent_gate([float(prices[('SPY',d)]['c']) for d in dates]);last_cap=None;picks=[];scores={}
    if policy!='vol':
        recorded_gate=readcsv(output/'gate-decisions.csv');assert len(recorded_gate)==len(eval_dates)
        for row,day in zip(recorded_gate,eval_dates):
            i=dates.index(day);expected=gate[i-1]
            assert row['date']==day and row['decision_close']==dates[i-1]
            for k in ('state','provisional'):assert row[k]==expected[k]
            for k in ('cap','red_count','green_count'):assert F(row[k])==expected[k]
            for k in (('breadth',) if policy=='breadth' else ('fast','slow','vol')):near(row[k],expected[k],'causal gate '+k,1e-10)
    recorded=readcsv(output/'ledger.csv');assert len(recorded)==len(eval_dates)+1
    trade_rows=readcsv(output/'trades.csv');trades_by=defaultdict(list)
    for t in trade_rows:trades_by[t['date']].append(t)
    selections=json.loads((output/'selections.json').read_text());selections_by={s['execution_date']:s for s in selections}
    assert len(selections_by)==len(selections)
    cc=readcsv(output/'contributions.csv');actual_contrib={(x['date'],x['symbol']):x for x in cc}
    assert len(actual_contrib)==len(cc)==len(eval_dates)*len(SYMS)
    cash=F(300000);held={s:0 for s in SYMS};receivables={};paid=set();expected_events=[];nav_previous=cash
    expected_contrib={};expected_decision_dates=[];total_slippage=F(0);fills=0;clipped=0;max_nav_delta=F(0)
    def settle(day,inclusive):
        nonlocal cash
        roundings=defaultdict(F)
        for key,(amount,pay,symbol) in receivables.items():
            if key not in paid and (pay<=day if inclusive else pay<day):
                credit=cent(amount);cash+=credit;paid.add(key);roundings[symbol]+=credit-amount
                expected_events.append({'kind':'payment','id':key,'date':day,'cash_credit':credit,'rounding_pnl':credit-amount})
        return roundings
    for j,day in enumerate(eval_dates):
        i=dates.index(day);before=dict(held);roundings=settle(day,False)
        for a in events_by[day]:
            if a['kind']=='split':
                s=a['symbol'];after=F(held[s])*F(a['ratio']);assert after.denominator==1
                expected_events.append({'kind':'split','id':a['id'],'date':day,'old_shares':held[s],'new_shares':int(after)});held[s]=int(after)
            elif a['kind']=='in_kind':assert held[a['symbol']]==0,'Held in-kind outside qualified scope.'
        entitlement=defaultdict(F)
        for a in events_by[day]:
            if a['kind']=='cash':
                s=a['symbol'];amount=held[s]*F(a['amount']);receivables[a['id']]=(amount,a['pay_date'],s);entitlement[s]+=amount
                expected_events.append({'kind':'entitlement','id':a['id'],'date':day,'shares':held[s],'amount':amount})
        expected_trades=[]
        monthly=j==0 or (policy!='hold' and day[:7]!=dates[i-1][:7])
        cap=gate[i-1]['cap'] if policy!='vol' else F(1)
        rebalance=monthly or (policy!='vol' and cap!=last_cap)
        if rebalance:
            expected_decision_dates.append(day)
            if policy=='hold':picks=['SPY'];scores={}
            elif policy=='equal':picks=list(SECTORS);scores={}
            elif monthly:
                scores={}
                for s in SECTORS:
                    v=features[s];ret=v[i-1]/v[i-253]-1
                    rs=[v[k]/v[k-1]-1 for k in range(i-63,i)]
                    vol=statistics.stdev(rs)*math.sqrt(252);assert vol>1e-15
                    scores[s]={'return_252':ret,'volatility_63':vol,'score':ret/vol if policy in ('vol','gate','corr','breadth') else ret}
                ranked=sorted(SECTORS,key=lambda s:(-scores[s]['score'],s))
                picks=ranked[:3]
                if policy=='corr':
                    pool=ranked[:6];picks=[pool[0]]
                    observations={s:[features[s][k]/features[s][k-1]-1 for k in range(i-63,i)] for s in pool}
                    while len(picks)<3:
                        def penalty(s):
                            return statistics.mean(max(0.,statistics.correlation(observations[s],observations[t])) for t in picks)
                        next_pick=min((s for s in pool if s not in picks),key=lambda s:(round(penalty(s),12),-scores[s]['score'],s))
                        picks.append(next_pick)
            decision=selections_by[day]
            assert decision['picks']==picks and decision['decision_close']==dates[i-1]
            for s,item in scores.items():
                for key,v in item.items():near(decision['scores'][s][key],v,'selection feature',2e-10)
            desired={}
            for s in SYMS:
                split=math.prod(F(a['ratio']) for a in events_by[day] if a['symbol']==s and a['kind']=='split')
                amount=nav_previous*F(98,100)*cap*split/(len(picks)*prices[(s,dates[i-1])]['c']) if s in picks else F(0)
                desired[s]=amount.numerator//amount.denominator
            assert decision['desired_shares']==desired
            assert F(decision['cap'])==cap and bool(decision['monthly_selection'])==monthly and F(decision['target_gross'])==F(98,100)*cap
            for direction in (-1,1):
                for s in sorted(SYMS):
                    wanted=desired[s]-held[s]
                    if wanted*direction<=0:continue
                    opening=prices[(s,day)]['o'];fill=cent(opening*(1+F(direction*bps,10000)));quantity=wanted
                    if direction>0:
                        available=(cash-1)/fill;quantity=min(wanted,max(0,available.numerator//available.denominator))
                    if quantity==0:continue
                    before_cash=cash;cash-=quantity*fill+1;held[s]+=quantity
                    assert cash>=0 and held[s]>=0
                    slip=abs(quantity)*direction*(fill-opening);total_slippage+=slip;fills+=1;clipped+=quantity!=wanted
                    expected_trades.append({'date':day,'symbol':s,'quantity':quantity,'price':fill,'fee':F(1),'open':opening,
                        'slippage_usd':slip,'requested_quantity':wanted,'cash_before':before_cash,'cash_after':cash,'clipped':quantity!=wanted})
        last_cap=cap
        observed_trades=trades_by[day];assert len(observed_trades)==len(expected_trades)
        for actual,expected in zip(observed_trades,expected_trades):
            for k,v in expected.items():
                if k in ('date','symbol'):assert actual[k]==v
                elif k=='clipped':assert (actual[k]=='True')==v
                else:assert F(actual[k])==F(v),f'Independent trade mismatch {day} {k}'
        for s,v in settle(day,True).items():roundings[s]+=v
        outstanding=sum((v[0] for k,v in receivables.items() if k not in paid),F(0))
        nav=cash+outstanding+sum((held[s]*prices[(s,day)]['c'] for s in SYMS),F(0));row=recorded[j+1]
        assert row['date']==day and F(row['cash'])==cash and F(row['receivable'])==outstanding
        for s in SYMS:assert int(row[s])==held[s]
        max_nav_delta=max(max_nav_delta,abs(nav-F(row['equity_usd'])));assert nav==F(row['equity_usd'])
        sum_pnl=F(0)
        for s in SYMS:
            trades=[t for t in expected_trades if t['symbol']==s];fees=F(len(trades))
            pp=held[s]*prices[(s,day)]['c']-before[s]*prices[(s,dates[i-1])]['c']-sum((t['quantity']*t['price'] for t in trades),F(0))
            pnl=pp+entitlement[s]+roundings[s]-fees;sum_pnl+=pnl
            parts={'price_pnl':pp,'entitlement_pnl':entitlement[s],'rounding_pnl':roundings[s],'fees':fees,'total_pnl':pnl}
            actual=actual_contrib[(day,s)]
            for k,v in parts.items():assert F(actual[k])==v,f'Contribution mismatch {day} {s} {k}'
            near(actual['daily_return_contribution'],float(pnl/nav_previous),'daily contribution',1e-12)
            expected_contrib[(day,s)]=parts
        assert sum_pnl==nav-nav_previous
        nav_previous=nav
    assert set(selections_by)==set(expected_decision_dates)
    observed_events=json.loads((output/'events.json').read_text());assert len(observed_events)==len(expected_events)
    for actual,expected in zip(observed_events,expected_events):
        assert set(actual)==set(expected)
        for key,v in expected.items():
            if key in ('kind','id','date'):assert actual[key]==v
            else:assert F(actual[key])==F(v)
    for kind,size in [('year',4),('month',7)]:
        sums=defaultdict(lambda:defaultdict(F))
        for (day,s),parts in expected_contrib.items():
            for k,v in parts.items():sums[(day[:size],s)][k]+=v
        observed=readcsv(output/f'{kind}-contributions.csv');assert len(observed)==len(sums)
        for row in observed:
            for k,v in sums[(row[kind],row['symbol'])].items():assert F(row[k])==v
    summary=json.loads((output/'summary.json').read_text());temporal=json.loads((output/'temporal.json').read_text())
    values=[float(x['equity_usd']) for x in recorded];all_dates=[x['date'] for x in recorded]
    assert F(recorded[0]['equity_usd'])==300000 and recorded[0]['date']==dates[first-1]
    durations=path_statistics(values,all_dates);daily=[values[i]/values[i-1]-1 for i in range(1,len(values))]
    cagr=((values[-1]/values[0])**(365.25/(date.fromisoformat(all_dates[-1])-date.fromisoformat(all_dates[0])).days)-1)*100
    independent={'cagr_pct':cagr,'max_drawdown_pct':-durations['dd_pct'],'calmar':cagr/-durations['dd_pct'] if durations['dd_pct'] else None,
        'sharpe':ratio(daily),'terminal_equity':values[-1],'uw_sessions':durations['uw_sessions'],'uw_days':durations['uw_days'],
        'underwater_fraction':durations['underwater_fraction'],'fees_usd':fills,'slippage_usd':float(total_slippage),'trades':fills,'clipped_buys':clipped,'sessions':len(eval_dates),'rebalance_decisions':len(expected_decision_dates)}
    for k,v in independent.items():near(summary[k],v,k)
    assert summary['right_censored']==durations['censored']
    assert len(temporal['drawdown_episodes'])==len(durations['episodes'])
    for actual,e in zip(temporal['drawdown_episodes'],durations['episodes']):
        assert actual['peak_date'][:10]==all_dates[e['start']] and actual['observed_end_date'][:10]==all_dates[e['stop']]
        assert actual['duration_sessions']==e['duration'] and actual['duration_calendar_days']==e['days'] and actual['right_censored']==e['censored']
    rolling_checks=0
    for window in (21,63,252):
        changes=[values[i]/values[i-window]-1 for i in range(window,len(values))]
        item=temporal['rolling_returns'][str(window)]
        for k,v in [('minimum_return',min(changes) if changes else None),('maximum_return',max(changes) if changes else None),('last_return',changes[-1] if changes else None)]:near(item[k],v,'rolling '+str(window),1e-10);rolling_checks+=1
    annual=readcsv(output/'annual.csv');annual_checks=0
    for row in annual:
        year=row['year'];positions=[i for i,d in enumerate(all_dates) if i>0 and d.startswith(year)]
        first_y,last_y=positions[0],positions[-1];part=values[first_y-1:last_y+1];days=all_dates[first_y-1:last_y+1]
        dd=path_statistics(part,days);ret=(part[-1]/part[0]-1)*100;rets=[part[i]/part[i-1]-1 for i in range(1,len(part))]
        metrics={'annual_return_pct':ret,'annual_max_drawdown_pct':dd['dd_pct'],'annual_sharpe_zero_rf':ratio(rets),
            'annual_calmar':ret/abs(dd['dd_pct']) if dd['dd_pct'] else None,'annual_uw_sessions':dd['uw_sessions'],'annual_uw_days':dd['uw_days'],
            'annual_underwater_fraction':dd['underwater_fraction'],'opening_equity_usd':part[0],'ending_equity_usd':part[-1],'sessions':len(positions)}
        for k,v in metrics.items():near(row[k],v,'annual '+year+' '+k);annual_checks+=1
        assert (row['partial_year']=='True')==(year=='2017')
    return {'status':'passed','method':'independent Fraction account/policy + separate economic factors and statistics',
        'sessions':len(eval_dates),'max_account_difference_usd':str(max_nav_delta),'fills_verified':fills,'events_verified':len(expected_events),
        'selections_verified':len(expected_decision_dates),'daily_asset_contributions_verified':len(expected_contrib),
        'annual_metric_checks':annual_checks,'full_metric_checks':len(independent),'rolling_metric_checks':rolling_checks,
        'native_or_broker_parity':False,'financial_slots':1}
