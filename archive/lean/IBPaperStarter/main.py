from AlgorithmImports import *


class IBPaperStarter(QCAlgorithm):
    """Connection and order smoke test, not an investment strategy."""

    def initialize(self):
        self.set_start_date(2013, 10, 7)
        self.set_end_date(2013, 10, 11)
        self.set_cash(100000)
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)
        self.symbol = self.add_equity("SPY", Resolution.MINUTE).symbol
        self.smoke_order = self.get_parameter("smoke-order") == "true"
        self.attempted = False
        self.observed = False
        self.log("IBPaperStarter: " + ("one-share smoke order enabled" if self.smoke_order else "observe only"))

    def on_data(self, data: Slice):
        if self.live_mode:
            # Broker-reported deployment details are checked before any order.
            details = self.deployment_details
            if (details["ib-trading-mode"] != "paper"
                    or not details["ib-account"].startswith("DU")):
                raise RuntimeError("Requires IBKR paper mode and a DU paper account.")
        if not data.bars.contains_key(self.symbol):
            return
        if not self.observed:
            self.log(f"First SPY bar: {data.bars[self.symbol].close}")
            self.observed = True
        if not self.smoke_order or self.attempted or not self.is_market_open(self.symbol):
            return
        self.attempted = True
        if self.portfolio[self.symbol].quantity != 0 or self.transactions.get_open_orders(self.symbol):
            self.log("Existing SPY position or open order: skipping smoke order.")
            return
        self.market_order(self.symbol, 1, tag="Paper connection smoke test")

    def on_order_event(self, order_event: OrderEvent):
        self.log(str(order_event))
