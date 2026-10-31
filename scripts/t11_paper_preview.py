#!/usr/bin/env python3
"""One bounded read-only T11 data/decision preview. Cannot submit orders."""
from datetime import datetime,timedelta,timezone,time as daytime
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from research.alpaca_pilot import credentials,NoRedirect
from paper_trading.t11_pilot import SYMBOLS
from paper_trading.t11_preview import close_map,features,gate_preview,pinned_policy
NY=ZoneInfo('America/New_York')


def main():
    now=datetime.now(timezone.utc);today=now.astimezone(NY).date()
    if now.astimezone(NY).hour<21:raise SystemExit('Read-only preview currently requires after21:00NY to exclude incomplete daily bars.')
    start=today-timedelta(days=600);end=now-timedelta(minutes=20)
    root=ROOT/'.local/t11-paper-preview'/now.strftime('%Y%m%dT%H%M%SZ')
    root.mkdir(parents=True,mode=0o700,exist_ok=False)
    plan={'mode':'read_only_decision_preview','created_utc':now.isoformat(),'symbols':sorted(SYMBOLS),
          'adjusted_start':str(start),'raw_spy_start':'2016-01-01','completed_through':str(today),
          'data_end_utc':end.isoformat(),'feed':'sip','adjustment':'all for features;raw for gate',
          'max_requests':12,'max_bytes':32000000,'max_seconds':180,'retries':0,'workers':1,
          'allowed_endpoints':['https://paper-api.alpaca.markets/v2/calendar','https://data.alpaca.markets/v2/stocks/bars'],
          'purpose':'operational preview only; no research simulation, signal qualification or order authorization',
          'code_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['scripts/t11_paper_preview.py','paper_trading/t11_preview.py','research/studies/t11_reproduction/indicators.py','research/risk_gate.py']}}
    def save(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
    save(root/'plan.json',plan)
    summary={'status':'started','broker_submissions':0,'financial_runs':0,'requests':0,'bytes':0,'order_bearing_ready':False}
    started=time.monotonic()
    try:
        key,secret=credentials(ROOT/'.env.alpaca');opener=urllib.request.build_opener(NoRedirect())
        def request(host,path,params):
            if (host,path) not in [('https://paper-api.alpaca.markets','/v2/calendar'),('https://data.alpaca.markets','/v2/stocks/bars')]:raise ValueError('Route forbidden.')
            if summary['requests']>=12 or time.monotonic()-started>180:raise ValueError('Request/time budget exhausted.')
            summary['requests']+=1
            req=urllib.request.Request(host+path+'?'+urllib.parse.urlencode(params),method='GET',headers={'APCA-API-KEY-ID':key,'APCA-API-SECRET-KEY':secret})
            with opener.open(req,timeout=15) as response:raw=response.read(4000001)
            (root/f"response-{summary['requests']:02d}.json").write_bytes(raw)
            summary['bytes']+=len(raw)
            if len(raw)>4000000 or summary['bytes']>32000000:raise ValueError('Response/byte budget exhausted.')
            return json.loads(raw)
        calendar=request('https://paper-api.alpaca.markets','/v2/calendar',{'start':'2016-01-01','end':str(today)})
        if not isinstance(calendar,list):raise ValueError('Calendar schema error.')
        sessions=[x['date'] for x in calendar]
        if sessions!=sorted(set(sessions)) or not sessions or sessions[-1]!=str(today):raise ValueError('Latest date is not a completed trading session.')
        expected=[d for d in sessions if d>=str(start)]
        def bars(symbols,start_day,adjustment):
            params={'symbols':','.join(sorted(symbols)),'timeframe':'1Day','start':datetime.combine(datetime.fromisoformat(start_day).date(),daytime.min,NY).isoformat(),'end':end.isoformat(),'adjustment':adjustment,'feed':'sip','sort':'asc','limit':10000}
            pages=[];tokens=set()
            while True:
                payload=request('https://data.alpaca.markets','/v2/stocks/bars',params);pages.append(payload)
                token=payload.get('next_page_token')
                if not token:return pages
                if token in tokens:raise ValueError('Pagination token repeated.')
                tokens.add(token);params['page_token']=token
        adjusted=close_map(bars(SYMBOLS,str(start),'all'),SYMBOLS,set(expected))
        raw=close_map(bars({'SPY'},'2016-01-01','raw'),{'SPY'},set(sessions))['SPY']
        f=features(adjusted,expected);gate=gate_preview(raw)
        policy=pinned_policy(ROOT/'.local/t11-reproduction-v1/policy_port.py',f,gate['cap'])
        save(root/'features-private.json',f)
        summary.update(status='preview_complete_unqualified_not_for_orders',asof_session=sessions[-1],
                       feature_sessions=len(expected),gate=gate,policy=policy,
                       limitations=['No native LEAN indicator/normalization parity qualification','Local2016 gate bootstrap differs from original2004 seed','No native multi-ETF execution bridge or complete account reconciliation','No live quote/order proposal; market closed'])
    except Exception as exc:
        summary.update(status='failed_preserved',error_type=type(exc).__name__)
    finally:
        summary['elapsed_seconds']=time.monotonic()-started
        save(root/'summary.json',summary)
        save(root/'manifest.json',{'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file() and p.name!='manifest.json'}})
        print(json.dumps({'status':summary['status'],'summary':str(root/'summary.json'),'orders':0}))
    return 0 if summary['status']=='preview_complete_unqualified_not_for_orders' else 1


if __name__=='__main__':raise SystemExit(main())
