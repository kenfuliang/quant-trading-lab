#!/usr/bin/env python3
"""Run the defined offline financing experiment and prepare local browser outputs."""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd

from research.studies.spy.spy_backtest import load_data
from research.evaluation.leveraged_spy import FinancingModel, simulate, score_rows
from research.evaluation.leverage_audit import reconcile
from reporting.annual import score_ranks

SOURCE = ROOT / 'reports/spy/20261024-235746-728801'
FILES = ['research/evaluation/leveraged_spy.py','research/evaluation/leverage_audit.py','research/leverage-model.md','scripts/current/leverage_comparison.py']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare():
    raw, dividends, metadata = load_data(SOURCE / 'source-data.json')
    manifest = json.loads((SOURCE/'manifest.json').read_text())
    assert metadata['sha256'] == manifest['source']['sha256']
    close = raw.close.round(2)
    fast = close.ewm(span=50,adjust=False).mean()
    slow = close.ewm(span=200,adjust=False).mean()
    saved = pd.read_csv(SOURCE/'trend_equity.csv',index_col='date')
    assert np.allclose(fast.loc[saved.index],saved.fast_ema,rtol=0,atol=1e-9)
    assert np.allclose(slow.loc[saved.index],saved.slow_ema,rtol=0,atol=1e-9)
    frame = raw[['open','low','close']].round(2)
    frame['want_long'] = (fast > slow).shift(1,fill_value=False)
    frame = frame.loc[saved.index]
    model = FinancingModel()
    identity = {'model':asdict(model),'source_sha256':metadata['sha256'],
                'code_hashes':{p:digest(ROOT/p) for p in FILES},'signal_fixture_sha256':digest(SOURCE/'trend_equity.csv')}
    fingerprint = hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    directory = ROOT/'reports/leverage'/fingerprint[:16]
    if (directory/'manifest.json').exists():
        current=json.loads((directory/'manifest.json').read_text())
        if current['status'] != 'completed': raise ValueError('Existing incomplete research run; inspect before retry.')
        for path,sha in current['artifact_hashes'].items():
            if digest(directory/path)!=sha: raise ValueError('Saved leveraged result hash mismatch: '+path)
        return directory
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('Incomplete run retained at '+str(directory)+'; preserve and inspect it before retry.')
    directory.mkdir(parents=True,exist_ok=True)
    all_rows, audits, cases = [], {}, []
    for scenario,config in [('base_6pct',model),('rate_9pct',replace(model,annual_rate=.09)),('maintenance_50pct',replace(model,maintenance=.50))]:
        for mode in ('trend','buy_hold'):
            for leverage in (1.,1.25,1.5,2.):
                key=f'{scenario}_{mode}_{leverage:g}x'
                folder=directory/key;folder.mkdir(exist_ok=True)
                curve,trades=simulate(frame,dividends,mode,leverage,config)
                audits[key]=reconcile(frame,dividends,curve,trades,mode,leverage,config)
                name=('EMA 50/200' if mode=='trend' else 'Buy/hold signal') + f' · {leverage:g}×'
                rows=score_rows(curve,config,name,mode,leverage)
                for row in rows: row.update(scenario=scenario,case=key)
                all_rows.extend(rows)
                curve.to_csv(folder/'ledger.csv',index_label='date')
                trades.to_csv(folder/'trades.csv',index=False)
                annual=pd.DataFrame(rows[1:]);annual.to_csv(folder/'annual.csv',index=False)
                # MLflow-compatible daily histories include one synthetic starting anchor.
                anchored=pd.concat([pd.Series([config.capital],index=[pd.Timestamp(curve.index[0])-pd.Timedelta(days=1)]),pd.Series(curve.equity_usd.to_numpy(),index=pd.to_datetime(curve.index))])
                history=pd.DataFrame({'equity_usd':anchored,'return_pct':anchored.pct_change().fillna(0)*100,'drawdown_pct':(anchored/anchored.cummax()-1)*100})
                if (anchored<=0).any(): history.loc[anchored<=0,'return_pct']=np.nan
                history.to_csv(folder/'equity.csv',index_label='date')
                overall=rows[0]
                (folder/'metrics.json').write_text(json.dumps(overall,indent=2))
                cases.append({'key':key,'scenario':scenario,'mode':mode,'leverage':leverage,'name':name,'folder':str(folder.resolve()),'metrics':overall,'parameters':asdict(config)})
    scores=pd.DataFrame(all_rows)
    for metric in ('calmar','sharpe'):
        scores[metric+'_rank']=scores.groupby(['scenario','period'])[metric].transform(score_ranks)
    scores.to_csv(directory/'scores.csv',index=False)
    (directory/'assumptions.md').write_text((ROOT/'research/leverage-model.md').read_text())
    (directory/'manifest.json').write_text(json.dumps({'status':'completed','created_utc':datetime.now(timezone.utc).isoformat(),
        'fingerprint':fingerprint,**identity,'audits':audits,'cases':cases,
        'artifact_hashes':{str(p.relative_to(directory)):digest(p) for p in directory.rglob('*') if p.is_file()}},indent=2))
    return directory


if __name__=='__main__':
    from reporting.leverage import render
    directory=prepare()
    render(directory)
    import subprocess
    subprocess.run([str(ROOT/'.local/venvs/mlflow/bin/python'),str(ROOT/'scripts/import_leverage_mlflow.py'),str(directory)],cwd=ROOT,check=True)
    render(directory)
    print(directory)
