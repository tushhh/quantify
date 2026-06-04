"""
quantify.backtest
~~~~~~~~~~~~~~~~~
Event-driven backtesting engine and simulation utilities.

Public API
----------
* :class:`~quantify.backtest.costs.CostModel`       — transaction cost model
* :class:`~quantify.backtest.engine.BacktestEngine` — main simulation engine
* :class:`~quantify.backtest.engine.BacktestResult` — result container
* :class:`~quantify.backtest.report.BacktestReport` — reporting and charts
* :func:`~quantify.backtest.analysis.walk_forward_analysis`
* :func:`~quantify.backtest.analysis.in_sample_out_of_sample`
* :func:`~quantify.backtest.analysis.monte_carlo_test`
* :func:`~quantify.backtest.analysis.aggregate_walk_forward_stats`
* :class:`~quantify.backtest.analysis.PurgedKFold`
"""

from quantify.backtest.costs import CostModel
from quantify.backtest.engine import BacktestEngine, BacktestResult
from quantify.backtest.report import BacktestReport
from quantify.backtest.analysis import (
    walk_forward_analysis,
    in_sample_out_of_sample,
    monte_carlo_test,
    aggregate_walk_forward_stats,
    PurgedKFold,
)

__all__ = [
    "CostModel",
    "BacktestEngine",
    "BacktestResult",
    "BacktestReport",
    "walk_forward_analysis",
    "in_sample_out_of_sample",
    "monte_carlo_test",
    "aggregate_walk_forward_stats",
    "PurgedKFold",
]
