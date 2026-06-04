"""Performance evaluation, metrics, and reporting."""

from quantify.evaluation.metrics import (
    total_return,
    cagr,
    sharpe_ratio,
    sortino_ratio,
    max_drawdown,
    max_drawdown_duration,
    calmar_ratio,
    win_rate,
    profit_factor,
    avg_win_loss_ratio,
    skewness,
    kurtosis,
    var,
    cvar,
    beta,
    alpha,
    information_ratio,
    treynor_ratio,
    annual_turnover,
    calculate_all,
)
from quantify.evaluation.tearsheet import Tearsheet
from quantify.evaluation.benchmark import (
    BenchmarkComparison,
    tracking_error,
    up_capture_ratio,
    down_capture_ratio,
    rolling_correlation,
)

__all__ = [
    # metrics
    "total_return",
    "cagr",
    "sharpe_ratio",
    "sortino_ratio",
    "max_drawdown",
    "max_drawdown_duration",
    "calmar_ratio",
    "win_rate",
    "profit_factor",
    "avg_win_loss_ratio",
    "skewness",
    "kurtosis",
    "var",
    "cvar",
    "beta",
    "alpha",
    "information_ratio",
    "treynor_ratio",
    "annual_turnover",
    "calculate_all",
    # tearsheet
    "Tearsheet",
    # benchmark
    "BenchmarkComparison",
    "tracking_error",
    "up_capture_ratio",
    "down_capture_ratio",
    "rolling_correlation",
]
