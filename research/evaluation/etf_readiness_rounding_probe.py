"""Second/final native synthetic probe: fee-aware share budgets and rotation."""
from datetime import datetime,timezone
from decimal import Decimal,ROUND_FLOOR
from pathlib import Path
import json
import pandas as pd
from research.evaluation.etf_readiness_probe import (STATE,VENUE,IDS,TIMES,instrument,cash,digest,write,
    BacktestEngine,BacktestEngineConfig,LoggingConfig,FixedFeeModel,Money,USD,OmsType,AccountType,
    Strategy,StrategyConfig,QuoteTick,Price,Quantity,OrderSide)

ACTIONS={0:('SPY','BUY',3),1:('IEF','BUY',2),2:('GLD','BUY',2),3:('SPY','SELL',2),4:('IEF','BUY',3),5:('GLD','BUY',3),6:('SPY','OVERSIZE',1000)}


def affordable_delta(available,ask,commission,requested):
    available,ask,commission=map(lambda x:Decimal(str(x)),(available,ask,commission))
    if not all(x.is_finite() for x in (available,ask,commission)) or available<0 or ask<=0 or commission<0 or type(requested) is not int or requested<0:
        raise ValueError('Invalid synthetic share budget.')
    return min(requested,max(0,int(((available-commission)/ask).to_integral_value(rounding=ROUND_FLOOR))))


class BudgetFixture(Strategy):
    def __init__(self):super().__init__(StrategyConfig());self.rows=[];self.fills=[];self.rejections=[];self.budgets=[]
    def on_start(self):
        for iid in IDS.values():self.subscribe_quote_ticks(iid)
    def on_quote_tick(self,tick):
        if tick.instrument_id!=IDS['GLD']:return
        i=next((i for i,t in enumerate(TIMES[:8]) if tick.ts_event==t.value+2),None)
        if i is None:return
        account=self.cache.account_for_venue(VENUE);available=account.balance_free(USD).as_decimal()
        self.rows.append(dict(phase=i,cash=cash(account),available=str(available),**{s:int(self.portfolio.net_position(iid)) for s,iid in IDS.items()}))
        if i not in ACTIONS:return
        symbol,side,requested=ACTIONS[i];qty=requested
        if side=='BUY':
            quote=self.cache.quote_tick(IDS[symbol]);ask=quote.ask_price.as_decimal()
            qty=affordable_delta(available,ask,1,requested)
            self.budgets.append(dict(phase=i,symbol=symbol,available=str(available),ask=str(ask),commission='1',requested=requested,submitted=qty))
        if qty:self.submit_order(self.order_factory.market(IDS[symbol],OrderSide.SELL if side=='SELL' else OrderSide.BUY,Quantity.from_int(qty)))
    def on_order_filled(self,event):self.fills.append(dict(symbol=str(event.instrument_id).split('.')[0],side=event.order_side.name,quantity=str(event.last_qty),price=str(event.last_px),commission=str(event.commission.as_decimal())))
    def on_order_denied(self,event):self.rejections.append(dict(kind='DENIED',reason=str(event.reason)))
    def on_order_rejected(self,event):self.rejections.append(dict(kind='REJECTED',reason=str(event.reason)))


def run_native(out):
    engine=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level='ERROR',bypass_logging=True)));strategy=BudgetFixture()
    engine.add_venue(VENUE,OmsType.NETTING,AccountType.CASH,[Money(300,USD)],base_currency=USD,fee_model=FixedFeeModel(Money(1,USD)),bar_execution=False,allow_cash_borrowing=False)
    for symbol in IDS:engine.add_instrument(instrument(symbol))
    quotes=[]
    for t in TIMES[:8]:
        for i,(symbol,mark) in enumerate({'SPY':100,'IEF':50,'GLD':25}.items()):
            px=Price.from_str(f'{mark:.2f}');quotes.append(QuoteTick(IDS[symbol],px,px,Quantity.from_int(100000),Quantity.from_int(100000),t.value+i,t.value+i))
    engine.add_data(quotes);engine.add_strategy(strategy)
    try:
        engine.run();pd.DataFrame(strategy.rows).to_csv(out/'native-observations.csv',index=False)
        engine.trader.generate_order_fills_report().to_csv(out/'native-fills.csv');engine.trader.generate_orders_report().to_csv(out/'native-orders.csv')
        write(out/'budget-decisions.json',strategy.budgets);write(out/'fills.json',strategy.fills);write(out/'rejections.json',strategy.rejections)
        balance=Decimal('300');positions={s:0 for s in IDS};after=[]
        for f in strategy.fills:
            q=int(f['quantity']);sign=1 if f['side']=='BUY' else -1
            balance-=sign*q*Decimal(f['price'])+Decimal(f['commission']);positions[f['symbol']]+=sign*q;after.append(str(balance));assert balance>=0
        assert after==['99.00','48.00','22.00','221.00','70.00','19.00']
        assert [b['submitted'] for b in strategy.budgets]==[2,1,1,3,2]
        assert positions=={'SPY':0,'IEF':4,'GLD':3} and balance==19
        assert strategy.rows[-1]['cash']==19 and all(strategy.rows[-1][s]==positions[s] for s in IDS)
        assert len(strategy.rejections)==1 and len(strategy.fills)==6
        assert strategy.fills[3]['side']=='SELL' and strategy.fills[4]['side']=='BUY'
        return dict(status='synthetic_budget_and_cash_proof_passed',synthetic_only=True,historical_financial_cases=0,
          initial_cash_usd=300,final_cash_usd=19,positions=positions,filled_orders=6,fees_usd=6,
          decimal_cash_after_fills=after,independent_reconciliation_pass=True,
          fee_boundary=dict(available_usd=300,ask_usd=100,commission_usd=1,requested=3,submitted=2,reason='Three shares would cost301; two fit.'),
          shared_cash_budget_decisions=strategy.budgets,oversized_order_rejected=True,available_cash_never_borrowed=True,sell_before_buy_observed=True,
          limitations=['One synthetic venue; real cross-venue routing remains unverified','Fixture sequences orders by quote phase; not a production monthly allocator','No corporate-action adapter or calendar qualification added','Fictitious quotes, no historical strategy or return metrics'])
    finally:engine.dispose()


def execute():
    s=json.loads(STATE.read_text());now=datetime.now(timezone.utc)
    if now>=datetime.fromisoformat(s['deadline_utc']) or len(s['native_probe_revisions'])>=2:raise ValueError('Readiness probe budget/deadline exhausted.')
    n=len(s['native_probe_revisions'])+1;out=Path(f'.local/current-etf-readiness/native-r{n}');out.mkdir(exist_ok=False)
    attempt=dict(revision=n,status='reserved',source_sha256=digest(__file__),helper_sha256=digest(Path(__file__).with_name('etf_readiness_probe.py')),started_utc=now.isoformat(),output=str(out),synthetic_only=True)
    s['native_probe_revisions'].append(attempt);write(STATE,s)
    try:report=run_native(out);write(out/'proof.json',report);attempt['status']='completed'
    except Exception as error:attempt.update(status='failed',error=repr(error));write(out/'failure.json',attempt);raise
    finally:
        attempt['ended_utc']=datetime.now(timezone.utc).isoformat();write(STATE,s)
        write(out/'manifest.json',dict(artifact_hashes={p.name:digest(p) for p in out.iterdir() if p.is_file() and p.name!='manifest.json'}))
    print(json.dumps(report,indent=2))

if __name__=='__main__':execute()
