"""Invented prices only; no historical data access or subprocess launches."""
import json
from pathlib import Path
import tempfile
import unittest
import math
from decimal import Decimal as D
import numpy as np
import pandas as pd
from research.studies.sector_selection import model,audit
from research.us_etf_calendar import sessions


def synthetic_input(root):
    dates=sessions('2016-01-01','2017-04-28');rows=[]
    for j,s in enumerate(model.SYMBOLS):
        for i,date in enumerate(dates):
            factor=2 if s=='XLB' and date>=pd.Timestamp('2017-03-06') else 1
            base=(50+j*3)*math.exp(i*(.0002+j*.00003)+.015*math.sin(i*.17+j))
            close=round(base/factor,4);opening=round(close*(1+.002*math.sin(i*.31+j)),4)
            rows.append({'symbol':s,'session':str(date.date()),'o':str(opening),'h':str(max(opening,close)+1),'l':str(min(opening,close)-1),'c':str(close)})
    actions=[dict(id='warmup-share',symbol='XLF',kind='in_kind',ex_date='2016-09-19',pay_date='2016-09-22',ratio='.139146',child_symbol='XLRE'),
             dict(id='cash-before-split',symbol='XLB',kind='cash',ex_date='2017-03-03',pay_date='2017-03-10',amount='1.125'),
             dict(id='second-cash',symbol='XLE',kind='cash',ex_date='2017-03-31',pay_date='2017-04-03',amount='.455'),
             dict(id='split',symbol='XLB',kind='split',ex_date='2017-03-06',ratio='2')]
    prices=root/'prices.json';prices.write_text(json.dumps(rows))
    act=root/'actions.json';act.write_text(json.dumps({'cash_and_in_kind':actions[:-1],'splits':actions[-1:]}))
    bundle=root/'bundle.json';bundle.write_text(json.dumps({'files':{'prices':{'path':str(prices)},'actions':{'path':str(act)}}}))
    return bundle


class TestSectorModel(unittest.TestCase):
    def test_eight_invented_policy_accounts_match_independent_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bundle=synthetic_input(root);frames,acts=model.load_inputs(bundle)
            for bps in (5,10):
                for policy in model.POLICIES:
                    output=root/f'{policy}-{bps}'
                    summary=model.save_case(output,frames,acts,policy,bps,start='2017-02-01',end='2017-04-28')
                    proof=audit.replay(bundle,output,policy,bps,start='2017-02-01',end='2017-04-28')
                    self.assertEqual(proof['status'],'passed');self.assertEqual(proof['max_account_difference_usd'],'0')
                    self.assertEqual(summary['rebalance_decisions'],1 if policy=='hold' else 3)

    def test_future_prices_do_not_change_rank_or_order_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle=synthetic_input(Path(tmp));frames,acts=model.load_inputs(bundle)
            indexes=model.total_return_indexes(frames,acts);i=frames['SPY'].index.get_loc('2017-01-31')
            original=model.selections(indexes,'vol',i)
            changed={s:f.copy() for s,f in frames.items()}
            for f in changed.values():f.loc[f.index>'2017-01-31','close']='99999'
            later=model.total_return_indexes(changed,acts)
            self.assertEqual(model.selections(later,'vol',i),original)

    def test_zero_volatility_fails_no_asset_drop(self):
        index=pd.date_range('2016-01-01',periods=270)
        features={s:pd.Series(np.repeat(100.,270),index=index) for s in model.SYMBOLS}
        with self.assertRaises(ValueError):model.selections(features,'raw',269)

    def test_exact_rank_ties_use_alphabetical_symbols(self):
        index=pd.date_range('2016-01-01',periods=270);values=100+np.arange(270)+np.sin(np.arange(270))
        features={s:pd.Series(values,index=index) for s in model.SYMBOLS}
        picks,_=model.selections(features,'vol',269);self.assertEqual(picks,sorted(model.SECTORS)[:3])

    def test_metric_undefined_and_recovery_conventions(self):
        self.assertIsNone(audit.ratio([0,0]));self.assertEqual(audit.cent(audit.F('1.005')),audit.F(1))
        p=audit.path_statistics([100,90,100,80],['2020-01-01','2020-01-02','2020-01-03','2020-01-04'])
        self.assertEqual(p['uw_sessions'],2);self.assertEqual(p['uw_days'],2)
