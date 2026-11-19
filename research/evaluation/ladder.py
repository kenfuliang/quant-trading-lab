"""Ablation ladder: run ordered strategy rungs on the screening engine and compare them.

Each rung writes a ``run-output/v1`` run whose ``parent_run`` is the previous rung, and
``waterfall`` turns the rungs' metric summaries into step-by-step deltas.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime
from pathlib import Path

from research.evaluation.market_model import MarketConfig, MarketData, market_config_dict
from research.evaluation.metrics import METRIC_KEYS, summarize
from research.evaluation.run_output import COLUMNS, config_hash, new_run_id, write_run
from research.evaluation.screening_engine import run_screen
from research.evaluation.strategies import build_target_fn
from research.evaluation.universe import stock_labels

ENGINE_VERSION = "screening_engine (project)"


@dataclasses.dataclass(frozen=True)
class Rung:
    name: str
    strategy: dict
    market: MarketConfig


def run_ladder(data: MarketData, rungs: list[Rung], runs_root: Path, base: dict, now: datetime,
               wrap=None, universe: dict | None = None) -> list[dict]:
    """Run each rung in order; ``base`` carries ``code_commit`` and ``datasets``.

    ``wrap`` (optional) maps each rung's ``TargetFn`` to another (e.g. ``members_only``); ``universe`` is
    its plain-data description, recorded in the run config so the run id and hash reflect the mask.
    """
    instruments = list(data.bars)
    labels = stock_labels(base.get("datasets"), wrap is not None)
    universe_kind = (base.get("datasets") or {}).get("universe_kind")
    ladder_id = config_hash([{"rung": r.name, "strategy": r.strategy, "market": market_config_dict(r.market)}
                             for r in rungs] + ([universe] if wrap is not None and universe else []))[:12]
    results, parent = [], None
    for index, rung in enumerate(rungs):
        market = market_config_dict(rung.market)
        config = {
            "strategy": rung.strategy,
            "market": market,
            "instruments": instruments,
            "engine": "screen",
            "ladder": {"id": ladder_id, "rung": rung.name, "index": index},
        }
        target_fn = build_target_fn(rung.strategy)
        if wrap is not None:
            target_fn = wrap(target_fn)
            config["universe"] = universe or {"masked": True}
        result = run_screen(data, target_fn, rung.market)
        run_id = new_run_id(config, now)
        manifest = {
            "run_id": run_id,
            "created_utc": now.isoformat(),
            "code_commit": base["code_commit"],
            "config": config,
            "config_hash": config_hash(config),
            "engine": result.engine,
            "engine_version": ENGINE_VERSION,
            "datasets": base["datasets"],
            "coverage": {"instruments": instruments, "sessions": len(result.returns)},
            "parent_run": parent,
        }
        if labels:  # stock-class and masked runs only; ETF run manifests keep exactly the old keys
            manifest["labels"] = labels
            if universe_kind:
                manifest["universe_kind"] = universe_kind
        tables = {name: getattr(result, name)[list(cols)] for name, cols in COLUMNS.items()}
        write_run(runs_root, manifest, tables)
        summary = summarize(result.returns, result.fills, rung.market.initial_cash)
        results.append({"rung": rung.name, "run_id": run_id, "summary": summary})
        parent = run_id
    return results


def waterfall(steps: list[dict]) -> list[dict]:
    """Metric change between consecutive ``{rung, summary}`` steps; ``None`` propagates."""
    out = []
    for before, after in zip(steps, steps[1:]):
        delta = {}
        for key in METRIC_KEYS:
            a, b = before["summary"].get(key), after["summary"].get(key)
            delta[key] = None if a is None or b is None else b - a
        out.append({"from": before["rung"], "to": after["rung"], "delta": delta})
    return out
