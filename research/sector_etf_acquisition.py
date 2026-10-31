"""Fixed, bounded Alpaca sector-ETF acquisition; no brokerage or simulation APIs."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

from research.alpaca_pilot import NoRedirect, catalog_import, credentials, digest, save_json, validate_pages

SYMBOLS = ('XLB','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY','SPY')
START, END = '2016-01-01', '2025-12-31'
API = {'bars':'https://data.alpaca.markets/v2/stocks/bars',
       'actions':'https://data.alpaca.markets/v1/corporate-actions'}
DOCUMENTS = {
 'bars':'https://docs.alpaca.markets/us/reference/stockbars',
 'actions':'https://docs.alpaca.markets/us/reference/corporateactions-1',
 'plans':'https://docs.alpaca.markets/us/docs/about-market-data-api',
 'terms':'https://files.alpaca.markets/disclosures/alpaca_terms_and_conditions.pdf',
}
REQUEST_CAP, BYTE_CAP, SECONDS_CAP = 16, 50_000_000, 600
PAGE_CAP = 10_000_000


class BoundedDownload:
    def __init__(self, directory, auth, *, opener=None):
        self.directory=Path(directory); self.directory.mkdir(parents=True, exist_ok=False)
        self.auth=auth; self.opener=opener or urllib.request.build_opener(NoRedirect())
        self.started=time.monotonic(); self.records=[]; self.bytes=0

    def get(self, kind, params=None):
        if kind not in API:
            raise ValueError('Unsupported endpoint class.')
        remaining=SECONDS_CAP-(time.monotonic()-self.started)
        if len(self.records)>=REQUEST_CAP or remaining<=0 or self.bytes>=BYTE_CAP:
            raise ValueError('Aggregate acquisition limit reached; no request made.')
        return self._get(API[kind], kind, params or {}, remaining, True)

    def document(self, name):
        if name not in DOCUMENTS: raise ValueError('Unsupported document.')
        remaining=SECONDS_CAP-(time.monotonic()-self.started)
        if len(self.records)>=REQUEST_CAP or remaining<=0 or self.bytes>=BYTE_CAP:
            raise ValueError('Aggregate acquisition limit reached; no request made.')
        return self._get(DOCUMENTS[name], 'doc_'+name, {}, remaining, False)

    def _get(self, endpoint, kind, params, remaining, authenticated):
        n=len(self.records)+1
        record={'attempt':n,'kind':kind,'endpoint':endpoint,'utc':datetime.now(timezone.utc).isoformat(),
                'parameters':{k:v for k,v in params.items() if k!='page_token'},
                'paginated':bool(params.get('page_token')),'status':'reserved'}
        self.records.append(record); save_json(self.directory/'requests.json',self.records)
        headers={'Accept':'application/json'} if authenticated else {'User-Agent':'quant-trading-lab personal-research'}
        if authenticated:
            headers.update({'APCA-API-KEY-ID':self.auth[0],'APCA-API-SECRET-KEY':self.auth[1]})
        url=endpoint+('?' + urllib.parse.urlencode(params) if params else '')
        request=urllib.request.Request(url,headers=headers)
        try:
            with self.opener.open(request,timeout=min(25,remaining)) as response:
                limit=min(PAGE_CAP,BYTE_CAP-self.bytes)
                body=response.read(limit+1)
                path=self.directory/f'response-{n:02d}.bin'; path.write_bytes(body)
                self.bytes+=len(body)
                record.update(status='received',http_status=response.status,bytes=len(body),
                              sha256=digest(path),path=str(path),content_type=response.headers.get('Content-Type',''))
                save_json(self.directory/'requests.json',self.records)
                if len(body)>limit: raise ValueError('Response byte cap exceeded; partial bytes retained.')
                return body
        except Exception as error:
            record.update(status='failed',error_type=type(error).__name__)
            if isinstance(error,urllib.error.HTTPError):
                record['http_status']=error.code
                limit=min(PAGE_CAP,max(0,BYTE_CAP-self.bytes))
                body=error.read(limit+1);self.bytes+=len(body)
                path=self.directory/f'error-{n:02d}.bin';path.write_bytes(body)
                record.update(bytes=len(body),sha256=digest(path),path=str(path))
            save_json(self.directory/'requests.json',self.records)
            # Never propagate exception messages, request headers or response bodies.
            raise ValueError('Data acquisition request failed; private response retained.') from None

    def pages(self, kind):
        if kind not in API: raise ValueError('Unsupported API route.')
        params={'symbols':','.join(SYMBOLS),'start':START,'sort':'asc','limit':'1000'}
        if kind=='bars':
            params.update(timeframe='1Day',start=START+'T00:00:00-05:00',
                end=END+'T23:59:59-05:00',feed='sip',adjustment='raw',asof=END,
                currency='USD',limit='10000')
        else:
            # CA filters use process_date, not ex-date. Include a terminal buffer;
            # observed completeness and later revisions still require a separate audit.
            params.update(end='2026-01-31',data_quality='all')
        token=None;seen=set();pages=[]
        while True:
            if token:params['page_token']=token
            payload=json.loads(self.get(kind,params))
            if not isinstance(payload,dict) or not isinstance(payload.get('bars' if kind=='bars' else 'corporate_actions'),dict):
                raise ValueError('Unexpected response schema; raw bytes retained.')
            pages.append(payload)
            token=payload.get('next_page_token')
            if token is None: return pages
            if not isinstance(token,str) or not token or token in seen:
                raise ValueError('Repeated or invalid pagination token; stopped.')
            seen.add(token);time.sleep(.35)


def run(plan_path, env_file='.env.alpaca', root=Path('data')):
    plan_path=Path(plan_path);plan=json.loads(plan_path.read_text());root=Path(root)
    if plan['symbols']!=list(SYMBOLS) or plan['start']!=START or plan['end']!=END:
        raise ValueError('Plan universe/date mismatch.')
    if plan['collector_sha256']!=digest(__file__) or plan['limits']!={'requests':REQUEST_CAP,'bytes':BYTE_CAP,'seconds':SECONDS_CAP,'workers':1,'retries':0}:
        raise ValueError('Plan code or bounds mismatch.')
    for name,expected in plan['dependencies'].items():
        if digest(name)!=expected:raise ValueError('Frozen collector dependency changed.')
    identifier=plan['dataset_id']
    if Path(identifier).name!=identifier or identifier in ('.','..'):raise ValueError('Invalid dataset identity.')
    manifest_path=root/'manifests'/f'{identifier}.json';manifest_path.parent.mkdir(parents=True,exist_ok=True)
    manifest={'schema':'sector-etf-acquisition-v1','dataset_id':identifier,'status':'reserved',
              'symbols':list(SYMBOLS),'start':START,'end':END,'feed':'sip','adjustment':'raw',
              'plan_sha256':digest(plan_path),'collector_sha256':digest(__file__),
              'financial_comparison_eligible':False,'redistribution':'not_qualified',
              'personal_use_review':'official personal/noncommercial terms retained; additional agreements and completeness not independently certified',
              'financial_runs':0}
    with manifest_path.open('x') as f:json.dump(manifest,f,indent=2)
    download=None
    try:
        auth=credentials(env_file)
        download=BoundedDownload(root/'raw'/'alpaca'/identifier,auth)
        for name in DOCUMENTS:download.document(name)
        bars=download.pages('bars')
        rows=validate_pages(bars,((START,END),),SYMBOLS)
        normalized=root/'normalized'/f'{identifier}.json';normalized.parent.mkdir(parents=True,exist_ok=True);save_json(normalized,rows)
        manifest.update(rows=len(rows),per_symbol_rows={s:sum(x['symbol']==s for x in rows) for s in SYMBOLS},
                        normalized=str(normalized),normalized_sha256=digest(normalized))
        result=catalog_import(rows,root/'catalog'/identifier)
        repeat=catalog_import(rows,root/'catalog'/identifier)
        manifest.update(catalog=str(root/'catalog'/identifier),catalog_verification=result,duplicate_verification=repeat,
                        status='prices_downloaded_actions_pending')
        save_json(manifest_path,manifest)
        actions=download.pages('actions')
        output=root/'normalized'/f'{identifier}-actions.json';save_json(output,actions)
        counts={}
        for page in actions:
            for kind,records in page['corporate_actions'].items():
                if not isinstance(records,list):raise ValueError('Invalid action category.')
                counts[kind]=counts.get(kind,0)+len(records)
        manifest.update(status='download_complete_qualification_pending',actions=str(output),
                        actions_sha256=digest(output),action_type_counts=counts,
                        qualification_gaps=['issuer action reconciliation','process-date vs ex-date coverage and revisions',
                                            'historical availability','corporate-action accounting and rights qualification'])
    except Exception as error:
        manifest.update(status='failed_preserved',error_type=type(error).__name__)
    finally:
        if download:
            files=[p for p in download.directory.rglob('*') if p.is_file()]
            if 'catalog' in manifest:files += [p for p in Path(manifest['catalog']).rglob('*') if p.is_file()]
            manifest.update(http_attempts=len(download.records),response_bytes=download.bytes,
                            elapsed_seconds=time.monotonic()-download.started,
                            artifacts={str(p):digest(p) for p in files})
        save_json(manifest_path,manifest)
    # Safe summary only; no server body, response header, credential or account data.
    print(json.dumps({k:manifest[k] for k in ('dataset_id','status','http_attempts','response_bytes','rows','action_type_counts') if k in manifest}))
    return 0 if manifest['status']=='download_complete_qualification_pending' else 2

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('plan');args=parser.parse_args()
    raise SystemExit(run(args.plan))
