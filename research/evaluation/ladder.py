"""Ablation ladder: run ordered strategy rungs on the screening engine and compare them.

Each rung writes a ``run-output/v1`` run whose ``parent_run`` is the previous rung, and
``waterfall`` turns the rungs' metric summaries into step-by-step deltas.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime
from pathlib import Path

from research.evaluation.market_model import MarketConfig, MarketData
from research.evaluation.metrics import METRIC_KEYS, summarize
from research.evaluation.run_output import COLUMNS, config_hash, new_run_id, write_run
from research.evaluation.screening_engine import run_screen
from research.evaluation.strategies import build_target_fn

ENGINE_VERSION = "screening_engine (project)"


@dataclasses.dataclass(frozen=True)
class Rung:
    name: str
    strategy: dict
    market: MarketConfig


def run_ladder(data: MarketData, rungs: list[Rung], runs_root: Path, base: dict, now: datetime) -> list[dict]:
    """Run each rung in order; ``base`` carries ``code_commit`` and ``datasets``."""
    instruments = list(data.bars)
    ladder_id = config_hash([{"rung": r.name, "strategy": r.strategy, "market": dataclasses.asdict(r.market)}
                             for r in rungs])[:12]
    results, parent = [], None
    for index, rung in enumerate(rungs):
        market = dataclasses.asdict(rung.market)
        config = {
            "strategy": rung.strategy,
            "market": market,
            "instruments": instruments,
            "engine": "screen",
            "ladder": {"id": ladder_id, "rung": rung.name, "index": index},
        }
        result = run_screen(data, build_target_fn(rung.strategy), rung.market)
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
