#!/usr/bin/env python3
"""Trace saved closing losses to engine-reported trades/orders; never simulate."""
import csv
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {'leveraged_long': {'SOXL', 'TECL', 'TQQQ', 'SPXL', 'QLD'},
          'inverse_equity': {'SQQQ', 'TECS', 'SOXS', 'PSQ', 'SH'},
          'volatility': {'UVXY', 'UVIX', 'SVIX', 'SVXY'}}


def main():
    base = ROOT / '.local/t11-reference-v2'
    out = ROOT / '.local/t11-loss-trace-v1'
    out.mkdir(exist_ok=True)
    reference = json.loads((base/'export-review-v2/comparison.json').read_text())
    result = {'status': 'descriptive_engine_trade_trace_partial_attribution',
              'financial_runs': 0, 'cases': {}, 'limitations': [
                  'Closed-trade profitLoss and totalFees are engine fields retained separately; fee inclusion is not reinterpreted',
                  'Closed-trade sums exclude a complete account reconciliation; residuals are not attributed',
                  'Trade intervals and orders identify candidate held instruments, not daily instrument mark-to-market PnL or gate/feature states',
                  'Retrospective diagnostic dates and asset rankings are development evidence, not removal/addition backtests']}
    inputs = []
    for case in ('t11', 'gated_t11'):
        export_file = base/'exports'/f'{case}.json'
        raw = json.loads(export_file.read_text())
        digest = hashlib.sha256(export_file.read_bytes()).hexdigest()
        if digest != reference[case]['export_sha256']:
            raise ValueError('Original export hash mismatch')
        path_file = base/'export-review-v2'/f'{case}-candidate-close-path.json'
        rows = json.loads(path_file.read_text())
        equity = pd.Series([10000.] + [r['nav_usd'] for r in rows],
                           index=pd.to_datetime(['2019-12-31'] + [r['session'] for r in rows]))
        if len(rows) != 1508 or equity.index.has_duplicates or not equity.index.is_monotonic_increasing:
            raise ValueError('Reference path calendar mismatch')
        returns = equity.pct_change().dropna()
        orders = raw['orders']
        trades = raw['totalPerformance']['closedTrades']
        asset = {}
        for trade in trades:
            if not all(str(i) in orders for i in trade['orderIds']):
                raise ValueError('Trade references missing order ID')
            symbol = '+'.join(s['value'] for s in trade['symbols'])
            row = asset.setdefault(symbol, {'symbol': symbol, 'closed_trade_count': 0,
                                           'reported_profitLoss_usd': 0., 'reported_totalFees_usd': 0.})
            row['closed_trade_count'] += 1
            row['reported_profitLoss_usd'] += float(trade['profitLoss'])
            row['reported_totalFees_usd'] += float(trade['totalFees'])
        assets = sorted(asset.values(), key=lambda r: r['reported_profitLoss_usd'], reverse=True)
        events = []
        worst_dates = [str(t.date()) for t in returns.nsmallest(10).index]
        for day in sorted(set(worst_dates + ['2025-01-27', '2025-04-09', '2020-03-24'])):
            # The daily reference ends NY16:00; interval membership uses actual UTC timestamps.
            close = pd.Timestamp(day, tz='America/New_York') + pd.Timedelta(hours=16)
            carried = [t for t in trades if pd.Timestamp(t['entryTime']) < close < pd.Timestamp(t['exitTime'])]
            recent = sorted([o for o in orders.values() if pd.Timestamp(o['lastFillTime']) <= close],
                            key=lambda o: (o['lastFillTime'], o['id']))[-8:]
            events.append(dict(session=day, account_return=float(returns.loc[day]),
                               account_pnl_usd=float(equity.loc[day]-equity.shift(1).loc[day]),
                               reported_trade_intervals_crossing_close=[dict(symbols=[s['value'] for s in t['symbols']],
                                 entry=t['entryTime'], exit=t['exitTime'], quantity=t['quantity'],
                                 reported_profitLoss_usd=t['profitLoss'], reported_totalFees_usd=t['totalFees'],
                                 order_ids=t['orderIds']) for t in carried],
                               recent_exported_fills=[dict(id=o['id'], symbol=o['symbol']['value'],
                                 quantity=o['quantity'], price=o['price'], created=o['createdTime'],
                                 last_fill=o['lastFillTime'], tag=o['tag']) for o in recent],
                               branch_id=None, gate_state=None, daily_asset_pnl=None))
        closed_sum = sum(t['profitLoss'] for t in trades)
        result['cases'][case] = dict(closed_trades=len(trades), assets=assets,
          reported_closed_profitLoss_sum_usd=closed_sum,
          ending_account_profit_usd=float(equity.iloc[-1]-10000),
          account_profit_minus_reported_closed_profitLoss_usd=float(equity.iloc[-1]-10000-closed_sum),
          group_reported_closed_profitLoss_usd={g: sum(r['reported_profitLoss_usd'] for r in assets if r['symbol'] in names) for g,names in GROUPS.items()},
          events=events)
        with (out/f'{case}-reported-closed-trades.csv').open('w') as f:
            writer = csv.DictWriter(f, fieldnames=list(assets[0]))
            writer.writeheader()
            writer.writerows(assets)
        inputs.extend([dict(path=str(p.relative_to(ROOT)), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                       for p in (export_file, path_file)])
    result['inputs'] = inputs
    (out/'trace.json').write_text(json.dumps(result, indent=2)+'\n')
    for case, data in result['cases'].items():
        print(json.dumps(dict(case=case, closed_trades=data['closed_trades'],
           closed_sum=data['reported_closed_profitLoss_sum_usd'], unexplained_account_gap=data['account_profit_minus_reported_closed_profitLoss_usd'],
           groups=data['group_reported_closed_profitLoss_usd'])))
    print('Saved read-only trace. No strategy changes or financial runs.')


if __name__ == '__main__':
    main()
