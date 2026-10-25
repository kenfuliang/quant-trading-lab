"""NautilusTrader data-only observation; no execution client or order strategy."""
import os
import threading
from pathlib import Path

from nautilus_trader.adapters.interactive_brokers.common import IB
from nautilus_trader.adapters.interactive_brokers.config import (
    IBMarketDataTypeEnum,
    InteractiveBrokersDataClientConfig,
    InteractiveBrokersInstrumentProviderConfig,
)
from nautilus_trader.adapters.interactive_brokers.factories import InteractiveBrokersLiveDataClientFactory
from nautilus_trader.config import LoggingConfig, TradingNodeConfig
from nautilus_trader.examples.strategies.subscribe import SubscribeStrategy, SubscribeStrategyConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.identifiers import InstrumentId

from .gateway import HOST, PORT

ROOT = Path(__file__).resolve().parents[1]


def build_config():
    provider = InteractiveBrokersInstrumentProviderConfig(load_ids=frozenset(["SPY.ARCA"]))
    return TradingNodeConfig(
        trader_id="PAPER-001",
        logging=LoggingConfig(log_level="INFO", log_colors=False),
        data_clients={IB: InteractiveBrokersDataClientConfig(
            ibg_host=HOST,
            ibg_port=PORT,
            ibg_client_id=72,
            instrument_provider=provider,
            market_data_type=IBMarketDataTypeEnum.DELAYED_FROZEN,
            connection_timeout=20,
            request_timeout_secs=20,
        )},
        exec_clients={},
        timeout_connection=30.0,
        timeout_disconnection=5.0,
        timeout_post_stop=2.0,
    )


def observe(seconds=45):
    os.environ["IB_MAX_CONNECTION_ATTEMPTS"] = "1"
    node = TradingNode(config=build_config())
    node.add_data_client_factory(IB, InteractiveBrokersLiveDataClientFactory)
    node.trader.add_strategy(SubscribeStrategy(SubscribeStrategyConfig(
        instrument_id=InstrumentId.from_str("SPY.ARCA"), quote_ticks=True,
    )))
    node.build()
    result = {"connected": False, "instrument_loaded": False}
    finished = threading.Event()

    def stop_later():
        if not finished.wait(seconds):
            def snapshot_and_stop():
                result["connected"] = bool(node.kernel.data_engine.check_connected())
                result["instrument_loaded"] = node.cache.instrument(InstrumentId.from_str("SPY.ARCA")) is not None
                node.stop()
            node.kernel.loop.call_soon_threadsafe(snapshot_and_stop)

    timer = threading.Thread(target=stop_later, daemon=True)
    timer.start()
    try:
        node.run(raise_exception=True)
    finally:
        finished.set()
        node.dispose()
        timer.join(timeout=2)
    return result
