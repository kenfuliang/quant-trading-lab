"""Epoch3 sector-study fork of sector_gate/model.py.

Own project accounting retained verbatim; versioned selector and breadth seams
are the only intended policy changes. Never modifies the frozen parent modules.
"""
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_EVEN
import csv
import json
from pathlib import Path
import math
import numpy as np
import pandas as pd
from research.studies.checkpoint_20261031.sector_corporate_actions import ActionLedger, SYMBOLS, total_return_indexes
from reporting.annual import annual_metrics, sharpe
from reporting.temporal import analyze_temporal
from research.studies.sector_gate.signals import timeline
from research.studies.sector_rsi.signals import breadth_timeline

D=lambda x:Decimal(str(x))
SECTORS=tuple(s for s in SYMBOLS if s!='SPY')
POLICIES=('corr','gate','equal','breadth','vol')
CASES=tuple(f'{p}-{bps}' for bps in (5,10) for p in POLICIES)
START,END='2017-02-01','2025-12-31'
CAPITAL=D('300000');ALLOCATION=D('.98')


def json_safe(obj):
    if isinstance(obj,dict):return {str(k):json_safe(v) for k,v in obj.items()}
    if isinstance(obj,(list,tuple)):return [json_safe(v) for v in obj]
    if isinstance(obj,(float,np.floating)):return float(obj) if math.isfinite(obj) else None
    if isinstance(obj,(int,np.integer)):return int(obj)
    if isinstance(obj,Decimal):return str(obj)
    return obj


def write_json(path,obj):
    with Path(path).open('x') as f:json.dump(json_safe(obj),f,indent=2,allow_nan=False);f.write('\n')


def load_inputs(bundle_path):
    bundle=json.loads(Path(bundle_path).read_text())
    raw=json.loads(Path(bundle['files']['prices']['path']).read_text())
    frames={}
    for s in SYMBOLS:
        frame=pd.DataFrame([r for r in raw if r['symbol']==s]);frame.index=pd.to_datetime(frame.session)
        frames[s]=frame.rename(columns={'o':'open','h':'high','l':'low','c':'close'})[['open','high','low','close']]
    events=json.loads(Path(bundle['files']['actions']['path']).read_text())
    return frames,events['cash_and_in_kind']+events['splits']


def selections(indexes, policy, position):
    """Only closed data through position; no future row is read."""
    if policy=='hold':return ['SPY'],{}
    if policy=='equal':return list(SECTORS),{}
    if policy not in ('raw','vol','corr') or position<252:raise ValueError('Unsupported policy or insufficient warmup.')
    scores={}
    for s in SECTORS:
        values=indexes[s].iloc[:position+1].to_numpy(float)
        total=values[-1]/values[-253]-1
        returns=values[-63:]/values[-64:-1]-1
        vol=float(np.std(returns,ddof=1)*np.sqrt(252))
        if not np.isfinite([total,vol]).all() or vol<=1e-15:raise ValueError('Invalid/zero volatility input; no eligibility substitution.')
        scores[s]={'return_252':float(total),'volatility_63':vol,'score':float(total/vol if policy in ('vol','corr') else total)}
    ranked=sorted(SECTORS,key=lambda s:(-scores[s]['score'],s))
    picks=ranked[:3]
    if policy=='corr':
        pool=ranked[:6];picks=[pool[0]]
        history=np.column_stack([indexes[s].iloc[position-63:position+1].to_numpy(float) for s in pool])
        correlations=np.corrcoef((history[1:]/history[:-1]-1).T)
        if not np.isfinite(correlations).all():raise ValueError('Invalid correlation inputs; no substitution.')
        while len(picks)<3:
            def penalty(s):
                return float(np.mean([max(0.,correlations[pool.index(s),pool.index(p)]) for p in picks]))
            next_pick=min((s for s in pool if s not in picks),key=lambda s:(round(penalty(s),12),-scores[s]['score'],s))
            picks.append(next_pick)
    return picks,scores


def is_rebalance(index, i, policy, start):
    if index[i]<pd.Timestamp(start):return False
    if index[i]==pd.Timestamp(start):return True
    return policy!='hold' and index[i].month!=index[i-1].month


def evaluate(frames,actions,policy,bps,*,start=START,end=END):
    """Called with real data only by the reservation-guarded fixed child entrypoint.

    Orders use prior-close NAV/prices, split-adjusted share units, then deterministic
    cash-feasible open fills. No completed bar is exposed at its session start.
    """
    indexes=total_return_indexes(frames,actions);dates=frames['SPY'].index
    gate=breadth_timeline(indexes) if policy=='breadth' else timeline(frames['SPY']['close'].astype(float));last_cap=None;picks=[];scores={}
    begin=dates.get_loc(pd.Timestamp(start));stop=dates.get_loc(pd.Timestamp(end))
    if begin<253:raise ValueError('Insufficient complete common warmup.')
    book=ActionLedger(actions);curve=[];trades=[];decisions=[];contributions=[]
    anchor=dates[begin-1];prior_nav=CAPITAL
    def snapshot(day,nav,marks):
        return {'date':str(day.date()),'equity_usd':str(nav),'cash':str(book.cash),'receivable':str(book.outstanding),
                'gross_exposure':float(sum(D(book.shares[s])*D(marks[s]) for s in SYMBOLS)/nav),
                **{s:book.shares[s] for s in SYMBOLS}}
    curve.append(snapshot(anchor,CAPITAL,{s:frames[s].iloc[begin-1]['close'] for s in SYMBOLS}))
    for i in range(begin,stop+1):
        stamp=dates[i];day=str(stamp.date());previous=dates[i-1]
        prev_marks={s:D(frames[s].iloc[i-1]['close']) for s in SYMBOLS}
        close={s:D(frames[s].iloc[i]['close']) for s in SYMBOLS}
        opens={s:D(frames[s].iloc[i]['open']) for s in SYMBOLS}
        start_shares=dict(book.shares);event_start=len(book.events);trade_start=len(trades)
        book.before_open(day)
        monthly=is_rebalance(dates,i,'vol' if policy in ('gate','breadth') else policy,start)
        if monthly:picks,scores=selections(indexes,'vol' if policy in ('gate','breadth') else policy,i-1)
        cap=D(gate.iloc[i]['cap']) if policy!='vol' else D(1)
        if monthly or (policy!='vol' and cap!=last_cap):
            ratios={s:D(1) for s in SYMBOLS}
            for a in actions:
                if a['kind']=='split' and a['ex_date']==day:ratios[a['symbol']]*=D(a['ratio'])
            desired={s:int((prior_nav*ALLOCATION*cap*ratios[s]/(len(picks)*prev_marks[s])).to_integral_value(rounding=ROUND_FLOOR)) if s in picks else 0 for s in SYMBOLS}
            decisions.append({'execution_date':day,'decision_close':str(previous.date()),'policy':policy,
                'picks':picks,'scores':scores,'target_gross':str(ALLOCATION*cap),'cap':str(cap),'monthly_selection':monthly,'prior_nav':str(prior_nav),
                'desired_shares':desired,'initialization':i==begin})
            for side in (-1,1):
                for s in sorted(SYMBOLS):
                    delta=desired[s]-book.shares[s]
                    if delta*side<=0:continue
                    price=(opens[s]*(1+D(side)*D(bps)/10000)).quantize(D('.01'),rounding=ROUND_HALF_EVEN)
                    quantity=delta
                    if side>0:
                        affordable=max(0,int(((book.cash-D(1))/price).to_integral_value(rounding=ROUND_FLOOR)))
                        quantity=min(delta,affordable)
                    if not quantity:continue
                    cash_before=book.cash;book.fill(s,quantity,price)
                    trades.append({'date':day,'symbol':s,'quantity':quantity,'price':str(price),'fee':'1',
                        'open':str(opens[s]),'slippage_usd':str(abs(quantity)*D(side)*(price-opens[s])),
                        'requested_quantity':delta,'clipped':quantity!=delta,'cash_before':str(cash_before),'cash_after':str(book.cash)})
        last_cap=cap
        nav=book.close(day,close);curve.append(snapshot(stamp,nav,close))
        day_events=book.events[event_start:];day_trades=trades[trade_start:]
        for s in SYMBOLS:
            asset_trades=[t for t in day_trades if t['symbol']==s]
            asset_ids={a['id'] for a in actions if a['symbol']==s}
            entitlement=sum((D(e['amount']) for e in day_events if e['kind']=='entitlement' and e['id'] in asset_ids),D(0))
            rounding=sum((D(e['rounding_pnl']) for e in day_events if e['kind']=='payment' and e['id'] in asset_ids),D(0))
            fees=sum((D(t['fee']) for t in asset_trades),D(0))
            price_pnl=D(book.shares[s])*close[s]-D(start_shares[s])*prev_marks[s]-sum((D(t['quantity'])*D(t['price']) for t in asset_trades),D(0))
            pnl=price_pnl+entitlement+rounding-fees
            contributions.append({'date':day,'symbol':s,'price_pnl':str(price_pnl),'entitlement_pnl':str(entitlement),
                'rounding_pnl':str(rounding),'fees':str(fees),'total_pnl':str(pnl),'daily_return_contribution':str(pnl/prior_nav)})
        if sum((D(x['total_pnl']) for x in contributions[-len(SYMBOLS):]),D(0))!=nav-prior_nav:raise AssertionError('Contribution conservation failed.')
        prior_nav=nav
    return curve,trades,book.events,decisions,contributions


def save_case(output,frames,actions,policy,bps,*,start=START,end=END):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    curve,trades,events,decisions,contrib=evaluate(frames,actions,policy,bps,start=start,end=end)
    c=pd.DataFrame(curve).set_index('date');c.to_csv(output/'ledger.csv',index_label='date')
    trade_fields=['date','symbol','quantity','price','fee','open','slippage_usd','requested_quantity','clipped','cash_before','cash_after']
    with (output/'trades.csv').open('x') as f:
        writer=csv.DictWriter(f,fieldnames=trade_fields);writer.writeheader();writer.writerows(trades)
    if policy!='vol':
        gt=breadth_timeline(total_return_indexes(frames,actions)) if policy=='breadth' else timeline(frames['SPY']['close'].astype(float))
        gt.loc[start:end].to_csv(output/'gate-decisions.csv',index_label='date')
    write_json(output/'events.json',events);write_json(output/'selections.json',decisions)
    pc=pd.DataFrame(contrib);pc.to_csv(output/'contributions.csv',index=False)
    for period in ('year','month'):
        pc[period]=pc.date.str[:4 if period=='year' else 7]
        rows=[]
        for (p,s),group in pc.groupby([period,'symbol']):
            rows.append({period:p,'symbol':s,**{key:str(sum((D(x) for x in group[key]),D(0))) for key in ('price_pnl','entitlement_pnl','rounding_pnl','fees','total_pnl')}})
        pd.DataFrame(rows).to_csv(output/f'{period}-contributions.csv',index=False)
    equity=pd.Series([float(r['equity_usd']) for r in curve],index=pd.to_datetime([r['date'] for r in curve]))
    temporal,table=analyze_temporal(equity,initial_capital=float(CAPITAL));write_json(output/'temporal.json',temporal);table.to_csv(output/'temporal.csv',index_label='date')
    annual=annual_metrics(pd.DataFrame({'equity_usd':equity}))
    for key in ('annual_uw_sessions','annual_uw_days','annual_underwater_fraction'):annual[key]=np.nan
    for j,year in enumerate(annual.year):
        locs=np.flatnonzero(equity.index.year==year);locs=locs[locs>0]
        part=equity.iloc[locs[0]-1:locs[-1]+1];ts,_=analyze_temporal(part,initial_capital=float(part.iloc[0]))
        annual.loc[j,'annual_uw_sessions']=ts['longest_underwater_duration_sessions'];annual.loc[j,'annual_uw_days']=ts['longest_underwater_duration_calendar_days']
        annual.loc[j,'annual_underwater_fraction']=float((part.iloc[1:]<part.cummax().iloc[1:]).mean())
    annual['partial_year']=annual.year==2017;annual.to_csv(output/'annual.csv',index=False)
    years=(equity.index[-1]-equity.index[0]).days/365.25;cagr=(equity.iloc[-1]/equity.iloc[0])**(1/years)-1
    dd=-temporal['max_drawdown'];daily=equity.pct_change().iloc[1:]
    summary={'policy':policy,'cost_bps':bps,'cagr_pct':float(cagr*100),'max_drawdown_pct':float(dd*100),
        'calmar':float(cagr/dd) if dd else None,'sharpe':sharpe(daily),'terminal_equity':float(equity.iloc[-1]),'sessions':len(equity)-1,
        'uw_sessions':temporal['longest_underwater_duration_sessions'],'uw_days':temporal['longest_underwater_duration_calendar_days'],
        'underwater_fraction':float((equity.iloc[1:]<equity.cummax().iloc[1:]).mean()),'right_censored':temporal['longest_underwater_right_censored'],
        'fees_usd':len(trades),'slippage_usd':float(sum((D(t['slippage_usd']) for t in trades),D(0))),
        'trades':len(trades),'clipped_buys':sum(bool(t['clipped']) for t in trades),'mean_gross_exposure':float(pd.to_numeric(c.gross_exposure.iloc[1:]).mean()),
        'rebalance_decisions':len(decisions),'start':start,'end':end,'anchor':str(equity.index[0].date()),'mode':'project_ledger_development'}
    write_json(output/'summary.json',summary)
    return summary
