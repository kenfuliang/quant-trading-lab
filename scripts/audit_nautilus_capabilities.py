#!/usr/bin/env python3
"""Offline import/configuration audit; never constructs a node or broker client."""
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "vendor/nautilus_trader"
sys.path.insert(0, str(ROOT))


def inspect_interface(module_name, names):
    try:
        module = importlib.import_module(module_name)
        result = {"import": "passed", "symbols": {name: hasattr(module, name) for name in names}}
        installed = Path(module.__file__) if getattr(module, "__file__", None) else None
        if installed and installed.suffix == ".py":
            relative = Path(*module_name.split("."))
            relative = relative / "__init__.py" if installed.name == "__init__.py" else relative.with_suffix(".py")
            source = UPSTREAM / relative
            if source.exists():
                result["source"] = str(source.relative_to(ROOT))
                result["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
                result["matches_installed"] = source.read_bytes() == installed.read_bytes()
        return result
    except Exception as error:
        return {"import": "failed", "error": f"{type(error).__name__}: {error}"}


def main():
    interfaces = {
        "nautilus_trader.backtest": ["BacktestNode"],
        "nautilus_trader.backtest.node": ["BacktestNode"],
        "nautilus_trader.backtest.config": ["BacktestRunConfig", "BacktestDataConfig"],
        "nautilus_trader.live.node": ["TradingNode"],
        "nautilus_trader.persistence.catalog.parquet": ["ParquetDataCatalog"],
        "nautilus_trader.persistence.config": ["StreamingConfig"],
        "nautilus_trader.analysis.analyzer": ["PortfolioAnalyzer"],
        "nautilus_trader.analysis.reporter": ["ReportProvider"],
        "nautilus_trader.analysis.tearsheet": ["create_tearsheet", "create_tearsheet_from_stats"],
        "nautilus_trader.cache.adapter": ["CachePostgresAdapter"],
        "nautilus_trader.risk.config": ["RiskEngineConfig"],
        "nautilus_trader.live.config": ["TradingNodeConfig", "LiveExecEngineConfig"],
        "nautilus_trader.system.kernel": ["NautilusKernel"],
        "nautilus_trader.system.config": ["NautilusKernelConfig"],
        "nautilus_trader.model.instruments": ["OptionContract", "OptionSpread"],
        "nautilus_trader.model.greeks": ["GreeksCalculator"],
        "nautilus_trader.core.nautilus_pyo3": ["EventStoreConfig", "PostgresCacheDatabase", "LiveNode", "BacktestNode"],
        "nautilus_trader.adapters.interactive_brokers.config": ["InteractiveBrokersExecClientConfig"],
    }
    results = {name: inspect_interface(name, symbols) for name, symbols in interfaces.items()}
    from nautilus_trader.analysis import tearsheet
    from nautilus_trader.common.config import DatabaseConfig
    from nautilus_trader.live.config import TradingNodeConfig
    from nautilus_trader.risk.config import RiskEngineConfig
    from nautilus_trader.adapters.interactive_brokers.config import InteractiveBrokersExecClientConfig
    from nautilus_trader.backtest.config import BacktestRunConfig
    from paper_trading.node import build_config

    config = build_config()  # Configuration only: no TradingNode construction.
    defaults = TradingNodeConfig()
    report = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "imports, source identity, configuration only; no runtime, database, network, or strategy run",
        "python": platform.python_version(),
        "platform": f"{platform.system()} {platform.machine()}",
        "engine_version": importlib.metadata.version("nautilus_trader"),
        "upstream_commit": subprocess.check_output(["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"], text=True).strip(),
        "upstream_worktree_clean": not subprocess.check_output(["git", "-C", str(UPSTREAM), "status", "--porcelain"], text=True).strip(),
        "interfaces": results,
        "optional_packages": {name: importlib.util.find_spec(name) is not None for name in ("plotly", "kaleido", "duckdb")},
        "plotly_rendering_available": tearsheet.PLOTLY_AVAILABLE,
        "python_database_default": DatabaseConfig().type,
        "risk_config_fields": list(RiskEngineConfig.__struct_fields__),
        "kernel_event_store_field": "event_store" in TradingNodeConfig.__struct_fields__,
        "backtest_run_config_id_property": hasattr(BacktestRunConfig, "id"),
        "ib_execution_config_fields": list(InteractiveBrokersExecClientConfig.__struct_fields__),
        "default_reconciliation": defaults.exec_engine.reconciliation,
        "observer": {
            "execution_client_count": len(config.exec_clients),
            "cache_backing_configured": bool(config.cache and config.cache.database),
            "message_bus_backing_configured": bool(config.message_bus and config.message_bus.database),
            "streaming_configured": config.streaming is not None,
            "load_state": config.load_state,
            "save_state": config.save_state,
        },
    }
    print(json.dumps(report, indent=2))
    return int(any(result["import"] != "passed" for result in results.values()))


if __name__ == "__main__":
    raise SystemExit(main())
