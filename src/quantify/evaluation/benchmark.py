"""
quantify.evaluation.benchmark
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Benchmark comparison utilities for evaluating strategy performance
relative to a market index or any reference return series.

Usage
-----
    from quantify.evaluation.benchmark import BenchmarkComparison

    bc = BenchmarkComparison()
    spy = bc.load_benchmark("SPY", start="2020-01-01", end="2023-12-31")
    result = bc.compare(strategy_returns, spy)
    bc.print_comparison()
"""

from __future__ import annotations

import logging
import math
import warnings
from datetime import date
from typing import Optional, Union

import numpy as np
import pandas as pd

try:
    import yfinance as yf
    _HAS_YFINANCE = True
except ImportError:
    _HAS_YFINANCE = False
    warnings.warn("yfinance not installed — load_benchmark() will be unavailable", stacklevel=2)

from quantify.evaluation.metrics import (
    alpha,
    beta,
    cagr,
    information_ratio,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
    _clean,
    _TRADING_DAYS,
)

log = logging.getLogger(__name__)

_DateLike = Union[str, date, pd.Timestamp]


# ---------------------------------------------------------------------------
# Module-level helper functions
# ---------------------------------------------------------------------------


def tracking_error(returns: pd.Series, benchmark: pd.Series) -> float:
    """
    Annualised tracking error (std dev of active returns).

    Parameters
    ----------
    returns:
        Strategy daily return series.
    benchmark:
        Benchmark daily return series.

    Returns
    -------
    float
        Annualised tracking error.  Returns 0.0 if insufficient data.
    """
    s = _clean(returns)
    b = _clean(benchmark)
    aligned = pd.concat([s, b], axis=1).dropna()

    if len(aligned) < 2:
        return 0.0

    active = aligned.iloc[:, 0] - aligned.iloc[:, 1]
    return float(active.std(ddof=1) * math.sqrt(_TRADING_DAYS))


def up_capture_ratio(returns: pd.Series, benchmark: pd.Series) -> float:
    """
    Up-capture ratio: strategy return on benchmark-up days / benchmark return.

    Measures how much of the benchmark's upside the strategy captures.
    Values > 1.0 indicate the strategy outperforms the benchmark in up markets.

    Parameters
    ----------
    returns:
        Strategy daily return series.
    benchmark:
        Benchmark daily return series.

    Returns
    -------
    float
        Up-capture ratio.  Returns 0.0 if there are no benchmark-up days.
    """
    s = _clean(returns)
    b = _clean(benchmark)
    aligned = pd.concat([s, b], axis=1).dropna()

    if aligned.empty:
        return 0.0

    up_days = aligned[aligned.iloc[:, 1] > 0]
    if up_days.empty:
        return 0.0

    strat_up = float((1.0 + up_days.iloc[:, 0]).prod() - 1.0)
    bench_up = float((1.0 + up_days.iloc[:, 1]).prod() - 1.0)

    if bench_up == 0.0:
        return 0.0

    # Annualise both using number of up-days
    n = len(up_days)
    strat_ann = (1.0 + strat_up) ** (_TRADING_DAYS / n) - 1.0 if n > 0 else 0.0
    bench_ann = (1.0 + bench_up) ** (_TRADING_DAYS / n) - 1.0 if n > 0 else 0.0

    if bench_ann == 0.0:
        return 0.0

    return float(strat_ann / bench_ann)


def down_capture_ratio(returns: pd.Series, benchmark: pd.Series) -> float:
    """
    Down-capture ratio: strategy return on benchmark-down days / benchmark return.

    Measures how much of the benchmark's downside the strategy captures.
    Values < 1.0 indicate the strategy loses less than the benchmark in down markets.

    Parameters
    ----------
    returns:
        Strategy daily return series.
    benchmark:
        Benchmark daily return series.

    Returns
    -------
    float
        Down-capture ratio.  Returns 0.0 if there are no benchmark-down days.
    """
    s = _clean(returns)
    b = _clean(benchmark)
    aligned = pd.concat([s, b], axis=1).dropna()

    if aligned.empty:
        return 0.0

    down_days = aligned[aligned.iloc[:, 1] < 0]
    if down_days.empty:
        return 0.0

    strat_down = float((1.0 + down_days.iloc[:, 0]).prod() - 1.0)
    bench_down = float((1.0 + down_days.iloc[:, 1]).prod() - 1.0)

    if bench_down == 0.0:
        return 0.0

    n = len(down_days)
    # For down periods, returns are negative; we preserve sign then divide
    strat_ann = -((1.0 + abs(strat_down)) ** (_TRADING_DAYS / n) - 1.0) if n > 0 else 0.0
    bench_ann = -((1.0 + abs(bench_down)) ** (_TRADING_DAYS / n) - 1.0) if n > 0 else 0.0

    if bench_ann == 0.0:
        return 0.0

    return float(strat_ann / bench_ann)


def rolling_correlation(
    returns: pd.Series,
    benchmark: pd.Series,
    window: int = 63,
) -> pd.Series:
    """
    Rolling Pearson correlation between strategy and benchmark returns.

    Parameters
    ----------
    returns:
        Strategy daily return series.
    benchmark:
        Benchmark daily return series.
    window:
        Rolling window in trading days (default: 63 ≈ one quarter).

    Returns
    -------
    pd.Series
        Rolling correlation series.  Empty series if insufficient data.
    """
    s = _clean(returns)
    b = _clean(benchmark)
    aligned = pd.concat([s, b], axis=1).dropna()

    if len(aligned) < window:
        return pd.Series(dtype=float)

    return aligned.iloc[:, 0].rolling(window).corr(aligned.iloc[:, 1])


# ---------------------------------------------------------------------------
# BenchmarkComparison class
# ---------------------------------------------------------------------------


class BenchmarkComparison:
    """
    Benchmark comparison toolkit.

    Supports loading benchmark data from Yahoo Finance, computing
    relative performance metrics, and printing side-by-side summaries.

    Attributes
    ----------
    strategy_returns:
        Strategy daily returns (set after calling :meth:`compare`).
    benchmark_returns:
        Benchmark daily returns (set after calling :meth:`load_benchmark`
        or :meth:`compare`).
    comparison_result:
        Last comparison result dict (set after calling :meth:`compare`).
    strategy_name:
        Display name for the strategy.
    benchmark_name:
        Display name for the benchmark.
    """

    def __init__(
        self,
        strategy_name: str = "Strategy",
        benchmark_name: str = "Benchmark",
    ) -> None:
        self.strategy_name = strategy_name
        self.benchmark_name = benchmark_name
        self.strategy_returns: Optional[pd.Series] = None
        self.benchmark_returns: Optional[pd.Series] = None
        self.comparison_result: Optional[dict] = None

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_benchmark(
        self,
        symbol: str = "SPY",
        start: Optional[_DateLike] = None,
        end: Optional[_DateLike] = None,
    ) -> pd.Series:
        """
        Download benchmark daily returns from Yahoo Finance.

        Parameters
        ----------
        symbol:
            Yahoo Finance ticker (default: "SPY").
        start:
            Start date (inclusive).  Accepts str, date, or Timestamp.
        end:
            End date (inclusive).  Accepts str, date, or Timestamp.

        Returns
        -------
        pd.Series
            Daily return series indexed by date.

        Raises
        ------
        ImportError
            If yfinance is not installed.
        ValueError
            If no data is returned for the symbol/date range.
        """
        if not _HAS_YFINANCE:
            raise ImportError(
                "yfinance is required for load_benchmark(). "
                "Install it with: pip install yfinance"
            )

        log.info("Downloading benchmark %s from %s to %s", symbol, start, end)

        kwargs: dict = {"auto_adjust": True, "progress": False}
        if start:
            kwargs["start"] = str(start)
        if end:
            kwargs["end"] = str(end)

        try:
            data = yf.download(symbol, **kwargs)
        except Exception as exc:
            raise ValueError(f"Failed to download benchmark data for {symbol}: {exc}") from exc

        if data.empty:
            raise ValueError(f"No data returned for {symbol} between {start} and {end}")

        close = data["Close"]
        if isinstance(close, pd.DataFrame):
            # Multi-level columns when multiple tickers — take first
            close = close.iloc[:, 0]

        returns = close.pct_change().dropna()
        returns.name = symbol
        returns.index = pd.to_datetime(returns.index)

        self.benchmark_returns = returns
        self.benchmark_name = symbol
        log.info("Loaded %d daily returns for %s", len(returns), symbol)
        return returns

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def compare(
        self,
        strategy_returns: pd.Series,
        benchmark_returns: pd.Series,
        risk_free_rate: float = 0.0,
    ) -> dict:
        """
        Compute a comprehensive set of relative performance metrics.

        Parameters
        ----------
        strategy_returns:
            Strategy daily return series.
        benchmark_returns:
            Benchmark daily return series.
        risk_free_rate:
            Annual risk-free rate as a decimal.

        Returns
        -------
        dict
            Flat dictionary with strategy metrics, benchmark metrics, and
            relative metrics (alpha, beta, IR, tracking error, capture ratios).
        """
        self.strategy_returns = strategy_returns
        self.benchmark_returns = benchmark_returns

        s = _clean(strategy_returns)
        b = _clean(benchmark_returns)

        result: dict = {}

        # --- Strategy standalone ---
        result["strategy_total_return"] = float((1.0 + s).prod() - 1.0) if not s.empty else 0.0
        result["strategy_cagr"] = cagr(s)
        result["strategy_sharpe"] = sharpe_ratio(s, risk_free_rate)
        result["strategy_sortino"] = sortino_ratio(s, risk_free_rate)
        result["strategy_max_drawdown"] = max_drawdown(s)
        result["strategy_annual_vol"] = float(s.std(ddof=1) * math.sqrt(_TRADING_DAYS)) if len(s) >= 2 else 0.0

        # --- Benchmark standalone ---
        result["benchmark_total_return"] = float((1.0 + b).prod() - 1.0) if not b.empty else 0.0
        result["benchmark_cagr"] = cagr(b)
        result["benchmark_sharpe"] = sharpe_ratio(b, risk_free_rate)
        result["benchmark_sortino"] = sortino_ratio(b, risk_free_rate)
        result["benchmark_max_drawdown"] = max_drawdown(b)
        result["benchmark_annual_vol"] = float(b.std(ddof=1) * math.sqrt(_TRADING_DAYS)) if len(b) >= 2 else 0.0

        # --- Relative metrics ---
        result["alpha"] = alpha(s, b, risk_free_rate)
        result["beta"] = beta(s, b)
        result["information_ratio"] = information_ratio(s, b)
        result["tracking_error"] = tracking_error(s, b)
        result["up_capture_ratio"] = up_capture_ratio(s, b)
        result["down_capture_ratio"] = down_capture_ratio(s, b)

        # Capture ratio summary (higher up / lower down = better)
        uc = result["up_capture_ratio"]
        dc = result["down_capture_ratio"]
        result["capture_ratio"] = float(uc / dc) if (dc != 0.0 and not math.isnan(dc)) else float("nan")

        # Correlation
        aligned = pd.concat([s, b], axis=1).dropna()
        if len(aligned) >= 2:
            result["correlation"] = float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1]))
        else:
            result["correlation"] = float("nan")

        # Active return (annualised)
        result["active_return"] = result["strategy_cagr"] - result["benchmark_cagr"]

        self.comparison_result = result
        return result

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def print_comparison(self) -> None:
        """
        Print a side-by-side comparison table to the console.

        Requires :meth:`compare` to have been called first.  Raises
        ``RuntimeError`` if no comparison is available.
        """
        if self.comparison_result is None:
            raise RuntimeError("Call compare() before print_comparison().")

        m = self.comparison_result

        col_w = 28
        val_w = 16

        divider = "-" * (col_w + 2 * val_w + 4)

        print(f"\n{'=' * (col_w + 2 * val_w + 4)}")
        print(f"  BENCHMARK COMPARISON")
        print(f"{'=' * (col_w + 2 * val_w + 4)}")
        print(f"  {'Metric':<{col_w}}  {self.strategy_name:>{val_w}}  {self.benchmark_name:>{val_w}}")
        print(divider)

        def _row(label: str, s_key: str, b_key: str, pct: bool = False) -> None:
            sv = m.get(s_key, float("nan"))
            bv = m.get(b_key, float("nan"))

            def _fmt(v: float) -> str:
                if math.isnan(v):
                    return "N/A"
                if pct:
                    return f"{v * 100:+.2f}%"
                return f"{v:.4f}"

            print(f"  {label:<{col_w}}  {_fmt(sv):>{val_w}}  {_fmt(bv):>{val_w}}")

        def _rel_row(label: str, key: str, pct: bool = False) -> None:
            v = m.get(key, float("nan"))

            def _fmt(v: float) -> str:
                if math.isnan(v):
                    return "N/A"
                if pct:
                    return f"{v * 100:+.2f}%"
                return f"{v:.4f}"

            print(f"  {label:<{col_w}}  {_fmt(v):>{val_w}}  {'---':>{val_w}}")

        # --- Standalone metrics ---
        _row("Total Return", "strategy_total_return", "benchmark_total_return", pct=True)
        _row("CAGR", "strategy_cagr", "benchmark_cagr", pct=True)
        _row("Annual Volatility", "strategy_annual_vol", "benchmark_annual_vol", pct=True)
        _row("Max Drawdown", "strategy_max_drawdown", "benchmark_max_drawdown", pct=True)
        _row("Sharpe Ratio", "strategy_sharpe", "benchmark_sharpe")
        _row("Sortino Ratio", "strategy_sortino", "benchmark_sortino")

        print(divider)
        print(f"  {'Relative Metrics':<{col_w}}")
        print(divider)

        _rel_row("Alpha (annualised)", "alpha", pct=True)
        _rel_row("Beta", "beta")
        _rel_row("Information Ratio", "information_ratio")
        _rel_row("Tracking Error", "tracking_error", pct=True)
        _rel_row("Active Return", "active_return", pct=True)
        _rel_row("Correlation", "correlation")
        _rel_row("Up Capture Ratio", "up_capture_ratio")
        _rel_row("Down Capture Ratio", "down_capture_ratio")
        _rel_row("Capture Ratio (Up/Down)", "capture_ratio")

        print(f"{'=' * (col_w + 2 * val_w + 4)}\n")

    # ------------------------------------------------------------------
    # Convenience — rolling metrics
    # ------------------------------------------------------------------

    def rolling_correlation(self, window: int = 63) -> pd.Series:
        """
        Rolling correlation between strategy and benchmark.

        Requires :meth:`compare` to have been called first.

        Parameters
        ----------
        window:
            Rolling window in trading days (default: 63).

        Returns
        -------
        pd.Series
            Rolling correlation series.
        """
        if self.strategy_returns is None or self.benchmark_returns is None:
            raise RuntimeError("Call compare() before rolling_correlation().")
        return rolling_correlation(self.strategy_returns, self.benchmark_returns, window)

    def __repr__(self) -> str:
        has_result = self.comparison_result is not None
        return (
            f"BenchmarkComparison("
            f"strategy={self.strategy_name!r}, "
            f"benchmark={self.benchmark_name!r}, "
            f"has_result={has_result})"
        )


__all__ = [
    "BenchmarkComparison",
    "tracking_error",
    "up_capture_ratio",
    "down_capture_ratio",
    "rolling_correlation",
]
