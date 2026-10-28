"""Bounded native synthetic accounting proof. No historical strategy execution."""
from datetime import datetime,timezone
from decimal import Decimal
import hashlib,json
from pathlib import Path

import pandas as pd
from nautilus_trader.backtest.engine import BacktestEngine,SimulatedExchange
from nautilus_trader.backtest.config import BacktestEngineConfig,SimulationModuleConfig
from nautilus_trader.backtest.models import FixedFeeModel
from nautilus_trader.backtest.modules import SimulationModule
from nautilus_trader.config import LoggingConfig,StrategyConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.identifiers import Venue,InstrumentId,Symbol
from nautilus_trader.model.instruments import Equity
from nautilus_trader.model.objects import Money,Price,Quantity
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import OmsType,AccountType,OrderSide
from nautilus_trader.trading.strategy import Strategy

STATE=Path('.local/current-etf-readiness/state.json')
VENUE=Venue('SIM');IDS={s:InstrumentId.from_str(s+'.SIM') for s in ['SPY','IEF','GLD']}
TIMES=[pd.Timestamp('2020-01-02T14:30:00Z')+pd.Timedelta(minutes=i) for i in range(6)]+[pd.Timestamp(d+'T14:30:00Z') for d in ['2020-01-03','2020-01-06','2020-01-07','2020-01-08']]
ACTIONS={0:('SPY','BUY',3),1:('IEF','BUY',4),2:('GLD','BUY',8),3:('SPY','SELL',2),4:('GLD','BUY',10),5:('IEF','BUY',1000)}


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def instrument(symbol):return Equity(IDS[symbol],Symbol(symbol),USD,2,Price.from_str('.01'),Quantity.from_int(1),0,0)
def cash(account):return float(account.balance_total(USD).as_double())


def reference_fills(fills,payments):
    """Independent Decimal cash/position accumulation, not native portfolio calls."""
    balance=Decimal('1000');held={s:0 for s in IDS};steps=[]
    for fill in fills:
        side=1 if fill['side']=='BUY' else -1
        qty=int(fill['quantity']);px=Decimal(fill['price']);fee=Decimal(fill['commission'])
        assert qty>0 and Decimal(fill['quantity'])==qty and fee==1
        balance-=side*qty*px+fee;held[fill['symbol']]+=side*qty
        assert balance>=0 and all(v>=0 for v in held.values())
        steps.append(str(balance))
    for value in payments:balance+=Decimal(str(value))
    return dict(cash=str(balance),shares=held,cash_after_each_fill=steps)


def split_signal_reference():
    # Prices are invented. A distribution belongs to ex-date total return;
    # payment transfers receivable to cash without adding the distribution twice.
    prices=[Decimal('50'),Decimal('50'),Decimal('50'),Decimal('25'),Decimal('25')]
    splits=[1,1,1,2,1];dividends=[0,2,0,0,0];tri=[Decimal('100')]
    for i in range(1,len(prices)):
        tri.append(tri[-1]*Decimal(splits[i])*(prices[i]+Decimal(dividends[i]))/prices[i-1])
    return [str(v) for v in tri]


class DistributionFixture(SimulationModule):
    """Project-side receivable fixture using native cash adjustment on pay date.

    This is deliberately not a claim of a native corporate-action service.
    Split is intentionally unhandled to expose configured native behavior.
    """
    def __init__(self):
        super().__init__(SimulationModuleConfig());self.records=[];self.processed=set();self.receivable=0.
    def pre_process(self,data):
        day=pd.Timestamp(data.ts_event,tz='UTC').strftime('%Y-%m-%d')
        if day in self.processed:return
        self.processed.add(day)
        if day=='2020-01-03':
            held=sum(p.quantity.as_double() for p in self.exchange.cache.positions_open(instrument_id=IDS['IEF']))
            before=cash(self.exchange.get_account());self.receivable=held*2
            self.records.append(dict(kind='entitlement',date=day,shares=held,per_share=2,cash_before=before,cash_after=cash(self.exchange.get_account()),receivable=self.receivable))
        elif day=='2020-01-06':
            before=cash(self.exchange.get_account());amount=self.receivable
            self.exchange.adjust_account(Money(amount,USD));self.receivable=0.
            self.records.append(dict(kind='payment',date=day,amount=amount,cash_before=before,cash_after=cash(self.exchange.get_account()),receivable=0))
        elif day=='2020-01-07':self.records.append(dict(kind='known_2for1_split_no_handler',date=day,applied=False))
    def process(self,ts_now):pass
    def log_diagnostics(self,logger):pass
    def reset(self):self.records=[];self.processed=set();self.receivable=0.


class SharedCashFixture(Strategy):
    def __init__(self,module):
        super().__init__(StrategyConfig());self.module=module;self.rows=[];self.fills=[];self.rejections=[]
    def on_start(self):
        for iid in IDS.values():self.subscribe_quote_ticks(iid)
    def on_quote_tick(self,tick):
        if tick.instrument_id!=IDS['GLD']:return
        phase=next((i for i,t in enumerate(TIMES) if tick.ts_event==t.value+2),None)
        if phase is None:return
        a=self.cache.account_for_venue(VENUE)
        self.rows.append(dict(phase=phase,date=TIMES[phase].isoformat(),cash=cash(a),available_cash=a.balance_free(USD).as_double(),
             receivable_fixture=self.module.receivable,**{s:int(self.portfolio.net_position(iid)) for s,iid in IDS.items()}))
        if phase in ACTIONS:
            symbol,side,qty=ACTIONS[phase]
            self.submit_order(self.order_factory.market(IDS[symbol],OrderSide.BUY if side=='BUY' else OrderSide.SELL,Quantity.from_int(qty)))
    def on_order_filled(self,event):
        self.fills.append(dict(symbol=str(event.instrument_id).split('.')[0],side=event.order_side.name,
             quantity=str(event.last_qty),price=str(event.last_px),commission=str(event.commission.as_decimal()),timestamp=int(event.ts_event)))
    def on_order_rejected(self,event):self.rejections.append(dict(kind='REJECTED',reason=str(event.reason)))
    def on_order_denied(self,event):self.rejections.append(dict(kind='DENIED',reason=str(event.reason)))


def native_events():
    result=[]
    for phase,t in enumerate(TIMES):
        marks={'SPY':110 if phase>=3 else 100,'IEF':25 if phase>=8 else 50,'GLD':26 if phase>=3 else 25}
        for i,(symbol,mark) in enumerate(marks.items()):
            p=Price.from_str(f'{mark:.2f}')
            result.append(QuoteTick(IDS[symbol],p,p,Quantity.from_int(100000),Quantity.from_int(100000),t.value+i,t.value+i))
    return result


def run_native(out):
    engine=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level='ERROR',bypass_logging=True)))
    module=DistributionFixture();strategy=SharedCashFixture(module)
    engine.add_venue(VENUE,OmsType.NETTING,AccountType.CASH,[Money(1000,USD)],base_currency=USD,modules=[module],
                     fee_model=FixedFeeModel(Money(1,USD)),bar_execution=False,allow_cash_borrowing=False)
    for symbol in IDS:engine.add_instrument(instrument(symbol))
    engine.add_data(native_events());engine.add_strategy(strategy)
    try:
        engine.run()
        pd.DataFrame(strategy.rows).to_csv(out/'native-observations.csv',index=False)
        engine.trader.generate_order_fills_report().to_csv(out/'native-fills.csv')
        orders=engine.trader.generate_orders_report();orders.to_csv(out/'native-orders.csv')
        write(out/'observed-fills.json',strategy.fills);write(out/'distribution-fixture.json',module.records);write(out/'rejections.json',strategy.rejections)
        rows={r['phase']:r for r in strategy.rows};ref=reference_fills(strategy.fills,[r['amount'] for r in module.records if r['kind']=='payment'])
        assert len(strategy.fills)==5 and ref['cash_after_each_fill']==['699.00','498.00','297.00','516.00','255.00']
        assert strategy.fills[3]['side']=='SELL' and strategy.fills[4]['side']=='BUY'
        assert len(strategy.rejections)==1 and rows[6]['cash']==255 and rows[6]['IEF']==4
        assert rows[6]['receivable_fixture']==8 and rows[6]['cash']==rows[5]['cash']
        assert rows[7]['cash']==263 and rows[7]['receivable_fixture']==0
        assert float(ref['cash'])==rows[9]['cash'] and ref['shares']=={s:rows[9][s] for s in IDS}
        assert rows[9]['available_cash']==rows[9]['cash'] and all(r['cash']>=0 for r in strategy.rows)
        native_shares=rows[9]['IEF'];economic_shares=rows[7]['IEF']*2
        assert native_shares==4 and economic_shares==8
        native_value=rows[9]['cash']+rows[9]['SPY']*110+rows[9]['IEF']*25+rows[9]['GLD']*26
        split_value=rows[9]['cash']+rows[9]['SPY']*110+economic_shares*25+rows[9]['GLD']*26
        tri=split_signal_reference();assert [Decimal(v) for v in tri]==[Decimal(100),Decimal(104),Decimal(104),Decimal(104),Decimal(104)]
        return dict(status='shared_cash_verified_corporate_action_readiness_blocked',synthetic_only=True,historical_financial_cases=0,
          accounting_reference=ref,native_final_cash=rows[9]['cash'],native_final_positions={s:rows[9][s] for s in IDS},
          native_account_cash_reconciliation_pass=True,initial_cash=1000,filled_orders=5,fees_usd=5,oversize_order_rejected=True,
          whole_share_integer_check=True,sell_before_buy_observed=True,
          dividend=dict(ex_date_cash=rows[6]['cash'],ex_date_receivable_fixture=8,pay_date_cash=rows[7]['cash'],
                        entitlement_cash_not_spendable=True,pay_credit_once=True,implementation='Project fixture tracks receivable; native adjust_account credits cash. Not native receivable accounting.'),
          split=dict(status='blocked_expected_negative_probe',native_quantity=native_shares,required_economic_quantity=economic_shares,
                     native_cash_plus_marked_positions=native_value,economic_value_with_verified_split=split_value,missing_value_due_to_unhandled_split=split_value-native_value,
                     cause='Configured native cash account has no split handler. Ordinary quote change does not adjust position quantity; do not substitute artificial buy/sell fills.'),
          signal=dict(raw_IEF_prices=[50,50,50,25,25],forward_total_return_index=tri,pay_date_not_double_counted=True,
                      execution='Uses invented raw bid/ask quotes; TRI only an independent reference, never an execution price.'),
          limitations=['Single synthetic venue/account; cross-venue routing and actual instrument policies unverified','No native dividend receivable/corporate-action service configured','No split adjustment adapter configured','No production rebalance planner or cost-aware portfolio target sizing proved by fixed-order fixture','No native historical strategy performance or real broker operation'])
    finally:engine.dispose()


def execute():
    s=json.loads(STATE.read_text());now=datetime.now(timezone.utc)
    if now>=datetime.fromisoformat(s['deadline_utc']):raise ValueError('Readiness deadline expired.')
    if len(s['native_probe_revisions'])>=2:raise ValueError('Native probe revision limit exhausted.')
    n=len(s['native_probe_revisions'])+1;out=Path(f'.local/current-etf-readiness/native-r{n}');out.mkdir(exist_ok=False)
    attempt=dict(revision=n,status='reserved',source_sha256=digest(__file__),started_utc=now.isoformat(),output=str(out),synthetic_only=True)
    s['native_probe_revisions'].append(attempt);write(STATE,s)
    try:
        report=run_native(out);write(out/'proof.json',report);attempt['status']='completed_with_explicit_readiness_gaps'
    except Exception as error:
        attempt.update(status='failed',error=repr(error));write(out/'failure.json',attempt);raise
    finally:
        attempt['ended_utc']=datetime.now(timezone.utc).isoformat();write(STATE,s)
        write(out/'manifest.json',dict(artifact_hashes={p.name:digest(p) for p in out.iterdir() if p.is_file() and p.name!='manifest.json'}))
    print(json.dumps(report,indent=2))

if __name__=='__main__':execute()
