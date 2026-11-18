"""Plain-pandas wrapper around NautilusTrader's tearsheet (imports nothing from ``research``)."""
from __future__ import annotations

import html

import pandas as pd


def tearsheet_html(returns: pd.Series, stats: dict[str, float], title: str,
                   benchmark: pd.Series | None = None) -> str:
    """Render a self-contained tearsheet page for a daily ``returns`` series (DatetimeIndex).

    ``stats`` are shown as the returns statistics table. The call mirrors
    ``reporting.saved_runs``: ``output_path=None`` returns the HTML string.
    """
    from nautilus_trader.analysis import (
        TearsheetConfig, TearsheetDrawdownChart, TearsheetEquityChart,
        TearsheetMonthlyReturnsChart, TearsheetStatsTableChart, TearsheetYearlyReturnsChart,
    )
    from nautilus_trader.analysis.tearsheet import create_tearsheet_from_stats

    config = TearsheetConfig(charts=[TearsheetStatsTableChart(), TearsheetEquityChart(), TearsheetDrawdownChart(),
                                     TearsheetMonthlyReturnsChart(), TearsheetYearlyReturnsChart()], height=1800)
    rendered = create_tearsheet_from_stats(
        stats_pnls={}, stats_returns=dict(stats), stats_general={}, returns=returns,
        output_path=None, title=title, config=config,
        benchmark_returns=benchmark, benchmark_name="Benchmark",
    )
    if "<title>" not in rendered:
        rendered = rendered.replace("<head>", "<head><title>" + html.escape(title) + "</title>", 1)
    return rendered
