import unittest
from datetime import date
from types import SimpleNamespace as NS
from decimal import Decimal
from research.quantconnect import qc504_funded_policy as p

class Portfolio(dict):
    def __init__(self,cash,positions,prices):
        super().__init__({s:NS(quantity=q) for s,q in positions.items()});self.cash=cash;self.prices=prices
        self.cash_book={'USD':NS(add_amount=self.add)}
    def add(self,x):self.cash+=x
    @property
    def total_portfolio_value(self):return self.cash+sum(h.quantity*self.prices[s] for s,h in self.items())
    def get_buying_power(self,s,d):return self.cash*2

class FundedTests(unittest.TestCase):
    def make(self,held=None,cash=10000):
        class Symbol(str):
            @property
            def value(self):return str(self)
        a,b=Symbol('A'),Symbol('B');prices={a:100.,b:100.};pf=Portfolio(cash,held or {a:0,b:0},prices);orders=[]
        security={s:NS(price=v,set_margin_interest_rate_model=lambda x:None,buying_power_model=NS(get_initial_margin_required_for_order=lambda args:NS(value=args[2]['q']*100*.5))) for s,v in prices.items()}
        x=NS(_syms={'A':a,'B':b},portfolio=pf,securities=security,transactions=NS(get_open_orders=lambda:list(orders)),order_factory=NS(market_on_open_order=lambda s,q:dict(s=s,q=q)),market_on_open_order=lambda s,q,tag:orders.append(dict(s=s,q=q,tag=tag)))
        x._t10_weights=lambda:{b:1.};x._t11_weights=x._s2_weights=x._s3_weights=lambda:{}
        p.MarginInterestRateModel=NS(NULL=None);p.Order=NS(create_order=lambda x:x);p.OrderDirection=NS(BUY=1);p.InitialMarginRequiredForOrderParameters=lambda *a:a
        p.math=__import__('math');p.date=date;p.fund_initialize(x)
        return x,a,b,orders
    def test_sales_fill_before_buys_and_guard_pending(self):
        x,a,b,orders=self.make();x.portfolio[a].quantity=100;x.portfolio.cash=1000
        p.funded_rebalance(x);self.assertTrue(orders);self.assertTrue(all(o['q']<0 for o in orders));n=len(orders)
        p.funded_rebalance(x);self.assertEqual(len(orders),n)
        for o in list(orders):x.portfolio.cash-=o['q']*100;x.portfolio[o['s']].quantity+=o['q']
        orders.clear();p.funded_rebalance(x)
        self.assertTrue(orders);self.assertTrue(all(o['q']>0 for o in orders));self.assertLessEqual(sum(o['q']*100.25+2+.01*o['q'] for o in orders),x.portfolio.cash-.1*x.portfolio.total_portfolio_value)
    def test_funding_weekend_and_previous_cash(self):
        x,a,b,orders=self.make();x._fund_date=date(2020,1,3);x._fund_cash=-10000
        p.fund_accrue(x,date(2020,1,6));expected=Decimal('10000')*Decimal('.06')*Decimal(3)/Decimal(360)
        self.assertEqual(Decimal(str(x._fund_interest)),expected);self.assertEqual(x.portfolio.cash,9995.);self.assertEqual(x._fund_debt_days,3);self.assertLess(x._fund_max_post_debit_error,1e-9)
    def test_positive_cash_no_interest_and_no_duplicate_accrual(self):
        x,a,b,orders=self.make();p.fund_accrue(x,date(2020,1,2));self.assertEqual(x._fund_interest,0)
        with self.assertRaisesRegex(ValueError,'not increasing'):p.fund_accrue(x,date(2020,1,2))
    def test_margin_preflight_defers_without_submitting_rejected_order(self):
        x,a,b,orders=self.make();x.portfolio.get_buying_power=lambda s,d:0
        p.funded_rebalance(x)
        self.assertFalse(orders);self.assertGreater(x._fund_margin_deferrals,0);self.assertFalse(x._fund_working)
