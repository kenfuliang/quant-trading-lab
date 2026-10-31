"""Project-owned staged MOO execution and explicit end-of-session debit accrual.
Injected into private copies; signal functions remain outside this module.
"""

def fund_initialize(self):
    self._fund_date = date(2019,12,31)
    self._fund_cash = 10000.
    self._fund_interest = 0.
    self._fund_interest_year = {}
    self._fund_debt_days = 0
    self._fund_sell_batches = self._fund_buy_batches = 0
    self._fund_wait_sessions = self._fund_margin_deferrals = 0
    self._fund_cash_clipped = 0
    self._fund_intent = None
    self._fund_working = False
    self._fund_reduced = False
    self._fund_submitted_buys = self._fund_submitted_sells = 0
    self._fund_max_post_debit_error = 0.
    for sym in self._syms.values():
        self.securities[sym].set_margin_interest_rate_model(MarginInterestRateModel.NULL)


def fund_accrue(self, session):
    days=(session-self._fund_date).days
    if days<=0:raise ValueError('Funding dates not increasing')
    charge=max(-self._fund_cash,0.)*.06*days/360.
    if self._fund_cash<0:self._fund_debt_days+=days
    before=float(self.portfolio.total_portfolio_value)
    if charge:
        self.portfolio.cash_book['USD'].add_amount(-charge)
    after=float(self.portfolio.total_portfolio_value)
    error=abs(before-after-charge)
    self._fund_max_post_debit_error=max(self._fund_max_post_debit_error,error)
    if error>max(.00001,abs(before)*1e-10):raise ValueError('Funding debit does not reconcile to NAV')
    self._fund_interest+=charge
    key=str(session.year)
    self._fund_interest_year[key]=self._fund_interest_year.get(key,0.)+charge
    self._fund_date=session


def funded_rebalance(self):
    combined={}
    intent_parts=[]
    for key in ('t10','t11','s2','s3'):
        weights=getattr(self,'_'+key+'_weights')()
        intent_parts.append((key,tuple(sorted((s.value,round(w,10)) for s,w in weights.items()))))
        for sym,weight in weights.items():
            if not math.isfinite(weight) or weight<0:raise ValueError('Invalid target weight')
            combined[sym]=combined.get(sym,0.)+weight
    if sum(combined.values())>1.000001:raise ValueError('Target budget exceeded')
    intent=tuple(intent_parts)
    if intent!=self._fund_intent:
        self._fund_intent=intent
        self._fund_working=True
        self._fund_reduced=False
    if self.transactions.get_open_orders():
        self._fund_wait_sessions+=1
        return
    if not self._fund_working:return
    nav=float(self.portfolio.total_portfolio_value)
    if not math.isfinite(nav) or nav<=0:raise ValueError('Invalid execution NAV')
    targets={}
    for ticker,sym in sorted(self._syms.items()):
        held=int(self.portfolio[sym].quantity)
        if held<0:raise ValueError('Short holdings forbidden')
        price=float(self.securities[sym].price)
        weight=combined.get(sym,0.)
        if weight and price<=0:raise ValueError('Target price unavailable')
        targets[sym]=int(nav*.90*weight/price) if weight else 0
    reductions=[]
    for ticker,sym in sorted(self._syms.items()):
        delta=targets[sym]-int(self.portfolio[sym].quantity)
        if delta<0:reductions.append((sym,delta))
    if reductions and not self._fund_reduced:
        self._fund_reduced=True
        for sym,delta in reductions:
            self.market_on_open_order(sym,delta,tag='funded-v1:reduce')
            self._fund_submitted_sells+=1
        self._fund_sell_batches+=1
        self._fund_wait_sessions+=1
        return
    # Do not spend proceeds from any unfilled sale. Leave10% NAV in cash at sizing.
    budget=max(0.,float(self.portfolio.cash)-.10*nav)
    buys=0
    for ticker,sym in sorted(self._syms.items()):
        delta=targets[sym]-int(self.portfolio[sym].quantity)
        if delta<=0:continue
        price=float(self.securities[sym].price)
        # Reservation only; native fee model still determines the actual fee.
        unit=price*1.0025+.01
        quantity=min(delta,max(0,int((budget-2.)/unit)))
        if quantity<delta:self._fund_cash_clipped+=1
        # Native preflight before submission. It cannot guarantee future-open affordability.
        while quantity>0:
            request=self.order_factory.market_on_open_order(sym,quantity)
            order=Order.create_order(request)
            required=abs(float(self.securities[sym].buying_power_model.get_initial_margin_required_for_order(
                InitialMarginRequiredForOrderParameters(self.portfolio.cash_book,self.securities[sym],order)).value))
            available=float(self.portfolio.get_buying_power(sym,OrderDirection.BUY))
            if required<=max(0.,available)*.99:
                break
            self._fund_margin_deferrals+=1
            quantity//=2
        if quantity>0:
            self.market_on_open_order(sym,quantity,tag='funded-v1:buy')
            budget-=quantity*unit+2.
            self._fund_submitted_buys+=1
            buys+=1
    if buys:self._fund_buy_batches+=1
    self._fund_working=False
